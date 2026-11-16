// Raccourcis, démarrage avec Windows (normal ou administrateur sans confirmation), relance, sauvegarde des réglages.
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security;
using System.Text;
using System.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class SystemTools
    {
        public const string TaskName = "Hangar FS 2024";
        public static string ExePath { get { return Path.GetFullPath(System.Windows.Forms.Application.ExecutablePath); } }
        public static string StartupShortcut
        {
            get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Startup), "Hangar FS 2024.lnk"); }
        }

        public static void WriteShortcut(string lnk, string target, string args, string workdir, string description)
        {
            var t = Type.GetTypeFromProgID("WScript.Shell");
            object sh = Activator.CreateInstance(t);
            object sc = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, sh, new object[] { lnk });
            var st = sc.GetType();
            st.InvokeMember("TargetPath", BindingFlags.SetProperty, null, sc, new object[] { target });
            st.InvokeMember("Arguments", BindingFlags.SetProperty, null, sc, new object[] { args });
            st.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, sc, new object[] { workdir });
            st.InvokeMember("Description", BindingFlags.SetProperty, null, sc, new object[] { description });
            st.InvokeMember("IconLocation", BindingFlags.SetProperty, null, sc, new object[] { target + ",0" });
            st.InvokeMember("Save", BindingFlags.InvokeMethod, null, sc, null);
        }

        public static void CreateDesktopShortcut()
        {
            string lnk = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Hangar FS 2024.lnk");
            WriteShortcut(lnk, ExePath, "", Path.GetDirectoryName(ExePath), "Hangar FS 2024");
        }

        public static bool StartWithWindows { get { return File.Exists(StartupShortcut); } }

        public static void SetStartWithWindows(bool on)
        {
            if (on) WriteShortcut(StartupShortcut, ExePath, "--minimized", Path.GetDirectoryName(ExePath), "Hangar FS 2024");
            else if (File.Exists(StartupShortcut)) File.Delete(StartupShortcut);
        }

        static int Run(string exe, string args, int timeout = 20000)
        {
            var psi = new ProcessStartInfo(exe, args) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
            using (var p = Process.Start(psi))
            {
                p.StandardOutput.ReadToEnd(); p.StandardError.ReadToEnd();
                p.WaitForExit(timeout);
                return p.HasExited ? p.ExitCode : -1;
            }
        }

        public static bool TaskExists()
        {
            try { return Run("schtasks.exe", "/Query /TN \"" + TaskName + "\"") == 0; } catch (Exception) { return false; }
        }

        // schtasks avec les droits administrateur (une confirmation Windows si l'appli n'est pas déjà admin)
        static bool SchtasksAdmin(string args)
        {
            try
            {
                if (Win.IsAdmin()) return Run("schtasks.exe", args) == 0;
                var psi = new ProcessStartInfo("schtasks.exe", args) { UseShellExecute = true, Verb = "runas", WindowStyle = ProcessWindowStyle.Hidden };
                using (var p = Process.Start(psi)) { if (p == null) return false; p.WaitForExit(20000); return p.ExitCode == 0; }
            }
            catch (Exception) { return false; }
        }

        static string X(string s) { return SecurityElement.Escape(s ?? ""); }

        // tâche « à la demande » : passe Hangar FS 2024 en administrateur sans confirmation Windows
        public static bool CreateAdminTask()
        {
            string user = Environment.UserDomainName + "\\" + Environment.UserName;
            string xml = "<?xml version=\"1.0\" encoding=\"UTF-16\"?>\n<Task version=\"1.2\" xmlns=\"http://schemas.microsoft.com/windows/2004/02/mit/task\">\n" +
                "  <RegistrationInfo><Description>Hangar FS 2024 - passage en mode administrateur, a la demande de l'application</Description></RegistrationInfo>\n  <Triggers />\n" +
                "  <Principals><Principal id=\"Author\"><UserId>" + X(user) + "</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>\n" +
                "  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>" +
                "<AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>false</StartWhenAvailable><RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>" +
                "<IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings><AllowStartOnDemand>true</AllowStartOnDemand><Enabled>true</Enabled>" +
                "<Hidden>false</Hidden><RunOnlyIfIdle>false</RunOnlyIfIdle><WakeToRun>false</WakeToRun><ExecutionTimeLimit>PT0S</ExecutionTimeLimit><Priority>7</Priority></Settings>\n" +
                "  <Actions Context=\"Author\"><Exec><Command>" + X(ExePath) + "</Command><Arguments>--from-task</Arguments><WorkingDirectory>" + X(Path.GetDirectoryName(ExePath)) + "</WorkingDirectory></Exec></Actions>\n</Task>\n";
            Directory.CreateDirectory(AppInfo.BaseDir);
            string path = Path.Combine(AppInfo.BaseDir, "tache_hangar_fs2024.xml");
            File.WriteAllText(path, xml, Encoding.Unicode);
            if (!SchtasksAdmin("/Create /TN \"" + TaskName + "\" /XML \"" + path + "\" /F")) return false;
            for (int i = 0; i < 20; i++) { if (TaskExists()) return true; Thread.Sleep(500); }
            return false;
        }

        public static bool DeleteAdminTask()
        {
            if (!TaskExists()) return true;
            if (!SchtasksAdmin("/Delete /TN \"" + TaskName + "\" /F")) return false;
            for (int i = 0; i < 20; i++) { if (!TaskExists()) return true; Thread.Sleep(500); }
            return false;
        }

        // la tâche lance-t-elle bien CE programme ? (la 11.8 Python crée une tâche du même nom qui lance l'ancienne version)
        public static bool TaskIsOurs()
        {
            try
            {
                var psi = new ProcessStartInfo("schtasks.exe", "/Query /TN \"" + TaskName + "\" /XML") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
                using (var p = Process.Start(psi))
                {
                    string xml = p.StandardOutput.ReadToEnd();
                    p.StandardError.ReadToEnd();
                    p.WaitForExit(15000);
                    if (p.ExitCode != 0) return false;
                    var m = System.Text.RegularExpressions.Regex.Match(xml, "<Command>(.*?)</Command>", System.Text.RegularExpressions.RegexOptions.Singleline);
                    if (!m.Success) return false;
                    string cmd = System.Net.WebUtility.HtmlDecode(m.Groups[1].Value).Trim().Trim('"');
                    return string.Equals(Path.GetFullPath(cmd), ExePath, StringComparison.OrdinalIgnoreCase);
                }
            }
            catch (Exception) { return false; }
        }

        public static bool RunAdminTask()
        {
            try { return Run("schtasks.exe", "/Run /TN \"" + TaskName + "\"") == 0; } catch (Exception) { return false; }
        }

        // relance : même mode (ou administrateur si demandé)
        public static bool Relaunch(bool admin, bool minimized)
        {
            try
            {
                if (admin && !Win.IsAdmin() && TaskIsOurs() && RunAdminTask()) return true;
                var psi = new ProcessStartInfo(ExePath, "--wait-mutex" + (minimized ? " --minimized" : "")) { UseShellExecute = true, WorkingDirectory = Path.GetDirectoryName(ExePath) };
                if (admin && !Win.IsAdmin()) psi.Verb = "runas";
                Process.Start(psi);
                return true;
            }
            catch (Exception) { return false; }
        }

        // ---- sauvegarde des réglages (même format que la 11.8)
        public static void Export(string path, JObject cfg)
        {
            var info = new JObject { ["app"] = AppInfo.Name, ["version"] = AppInfo.Version, ["date"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm"), ["kind"] = "hangar_fs2024_settings" };
            if (File.Exists(path)) File.Delete(path);
            using (var z = ZipFile.Open(path, ZipArchiveMode.Create))
            {
                Write(z, "hangar_backup.json", info.ToString(Formatting.Indented));
                Write(z, "config.json", cfg.ToString(Formatting.Indented));
            }
        }

        static void Write(ZipArchive z, string name, string text)
        {
            var e = z.CreateEntry(name, CompressionLevel.Optimal);
            using (var s = new StreamWriter(e.Open(), new UTF8Encoding(false))) s.Write(text);
        }

        static string Read(ZipArchive z, string name)
        {
            var e = z.GetEntry(name);
            if (e == null) throw new Exception(name + " ?");
            using (var s = new StreamReader(e.Open(), Encoding.UTF8)) return s.ReadToEnd();
        }

        public static JObject[] ReadBackup(string path)
        {
            using (var z = ZipFile.OpenRead(path))
            {
                var info = JObject.Parse(Read(z, "hangar_backup.json"));
                var cfg = JObject.Parse(Read(z, "config.json"));
                if (JsonStore.Str(info["kind"]) != "hangar_fs2024_settings") throw new Exception(Hangar.L("fichier non reconnu", "file not recognised"));
                return new[] { info, cfg };
            }
        }
    }
}
