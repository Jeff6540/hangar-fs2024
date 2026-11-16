// Démarrage auto : applications lancées avec MSFS 2024 (ou avion au parking), fermées avec lui.
// Même liste que la 11.8 (clé « launcher » de config.json).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class Win
    {
        [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
        delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lp);
        [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
        [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
        [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int idx);
        [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
        [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
        [DllImport("user32.dll")] static extern bool IsZoomed(IntPtr h);
        [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
        [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
        [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int ht, uint flags);
        [DllImport("shell32.dll")] static extern bool IsUserAnAdmin();

        [StructLayout(LayoutKind.Sequential)]
        public struct RECT { public int Left, Top, Right, Bottom; }

        public static bool IsAdmin()
        {
            try { return IsUserAnAdmin(); } catch (Exception) { return false; }
        }

        // Écrans : principal d'abord, puis de gauche à droite
        public static List<Screen> Monitors()
        {
            return Screen.AllScreens.OrderBy(s => !s.Primary).ThenBy(s => s.Bounds.X).ThenBy(s => s.Bounds.Y).ToList();
        }

        public static string MonitorLabel(Screen s, int num)
        {
            return string.Format(Hangar.L("Écran {0}{1} · {2} × {3}", "Screen {0}{1} · {2} × {3}"), num,
                s.Primary ? Hangar.L(" — principal", " — primary") : "", s.Bounds.Width, s.Bounds.Height);
        }

        // "auto" = premier écran secondaire, sinon le principal ; écran débranché -> principal
        public static Screen Resolve(string choice)
        {
            var mons = Monitors();
            if (mons.Count == 0 || string.IsNullOrEmpty(choice)) return null;
            if (choice == "auto") return mons.FirstOrDefault(m => !m.Primary) ?? mons[0];
            return mons.FirstOrDefault(m => m.DeviceName == choice) ?? mons[0];
        }

        public static HashSet<string> RunningImages()
        {
            var set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            try
            {
                foreach (var p in Process.GetProcesses())
                {
                    try { set.Add(p.ProcessName + ".exe"); } catch (Exception) { }
                    p.Dispose();
                }
            }
            catch (Exception) { }
            return set;
        }

        // fenêtres principales visibles des programmes dont le nom est dans images
        public static List<IntPtr> WindowsOf(IEnumerable<string> images)
        {
            var wanted = new HashSet<string>(images, StringComparer.OrdinalIgnoreCase);
            var names = new Dictionary<uint, string>();
            var found = new List<IntPtr>();
            if (wanted.Count == 0) return found;
            EnumWindows((h, lp) =>
            {
                if (!IsWindowVisible(h) || GetWindow(h, 4) != IntPtr.Zero) return true;
                if ((GetWindowLong(h, -20) & 0x80) != 0) return true;
                RECT rc;
                GetWindowRect(h, out rc);
                if (rc.Right - rc.Left < 200 || rc.Bottom - rc.Top < 120) return true;
                uint pid;
                GetWindowThreadProcessId(h, out pid);
                string name;
                if (!names.TryGetValue(pid, out name))
                {
                    name = "";
                    try { using (var p = Process.GetProcessById((int)pid)) name = p.ProcessName + ".exe"; } catch (Exception) { }
                    names[pid] = name;
                }
                if (wanted.Contains(name)) found.Add(h);
                return true;
            }, IntPtr.Zero);
            return found;
        }

        public static string MonitorOf(IntPtr h)
        {
            try { return Screen.FromHandle(h).DeviceName; } catch (Exception) { return null; }
        }

        // centre la fenêtre sur l'écran (sans dépasser sa zone de travail)
        public static bool MoveTo(IntPtr h, Screen mon)
        {
            try
            {
                if (IsZoomed(h) || IsIconic(h)) ShowWindow(h, 9);
                RECT rc;
                GetWindowRect(h, out rc);
                var wa = mon.WorkingArea;
                int w = Math.Max(200, Math.Min(rc.Right - rc.Left, wa.Width));
                int ht = Math.Max(150, Math.Min(rc.Bottom - rc.Top, wa.Height));
                int x = wa.X + (wa.Width - w) / 2, y = wa.Y + (wa.Height - ht) / 2;
                bool ok = SetWindowPos(h, IntPtr.Zero, x, y, w, ht, 0x0004 | 0x0010);
                return ok && MonitorOf(h) == mon.DeviceName;
            }
            catch (Exception) { return false; }
        }

        // cible, arguments et dossier d'un raccourci .lnk
        public static string[] ResolveShortcut(string lnk)
        {
            try
            {
                var t = Type.GetTypeFromProgID("WScript.Shell");
                object sh = Activator.CreateInstance(t);
                object sc = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, sh, new object[] { lnk });
                var st = sc.GetType();
                string target = (string)st.InvokeMember("TargetPath", BindingFlags.GetProperty, null, sc, null);
                string args = (string)st.InvokeMember("Arguments", BindingFlags.GetProperty, null, sc, null);
                string cwd = (string)st.InvokeMember("WorkingDirectory", BindingFlags.GetProperty, null, sc, null);
                return new[] { target ?? "", args ?? "", cwd ?? "" };
            }
            catch (Exception) { return new[] { "", "", "" }; }
        }
    }

    class Launcher
    {
        readonly Hangar h;
        readonly object gate = new object();
        readonly Dictionary<string, DateTime> pending = new Dictionary<string, DateTime>();
        readonly Dictionary<string, CancellationTokenSource> pendingCts = new Dictionary<string, CancellationTokenSource>();
        readonly Dictionary<string, Process> procs = new Dictionary<string, Process>();
        readonly Dictionary<string, string> lstatus = new Dictionary<string, string>();
        HashSet<string> images = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        public bool ParkingFired;     // détection « avion au parking » (arrivera avec le relais)
        public bool RelayConnected;

        public Launcher(Hangar hangar) { h = hangar; }

        static string L(string fr, string en) { return Hangar.L(fr, en); }

        JArray Apps
        {
            get
            {
                var a = h.Cfg["launcher"] as JArray;
                if (a == null) { a = new JArray(); h.Cfg["launcher"] = a; }
                return a;
            }
        }

        JObject AppById(string id)
        {
            return Apps.OfType<JObject>().FirstOrDefault(a => JsonStore.Str(a["id"]) == id);
        }

        static bool B(JObject a, string key, bool def)
        {
            var t = a[key];
            return t != null && t.Type == JTokenType.Boolean ? (bool)t : def;
        }

        static int I(JObject a, string key)
        {
            double d;
            return double.TryParse(JsonStore.Str(a[key]), System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out d) ? (int)d : 0;
        }

        public static List<string> SplitProcs(string text)
        {
            return (text ?? "").Split(new[] { ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(x => x.Trim().Replace("\"", "")).Where(x => x != "").ToList();
        }

        public void RefreshImages() { images = Win.RunningImages(); }

        // état affiché : (texte, catégorie run / wait / err / off / "")
        string[] State(JObject app)
        {
            string key = JsonStore.Str(app["id"]);
            lock (gate)
            {
                DateTime when;
                if (pending.TryGetValue(key, out when))
                {
                    int left = Math.Max(0, (int)Math.Round((when - DateTime.Now).TotalSeconds));
                    return new[] { string.Format(L("⏳ démarrage dans {0} s", "⏳ starting in {0} s"), left), "wait" };
                }
                if (SplitProcs(JsonStore.Str(app["proc"])).Any(images.Contains))
                    return new[] { L("● en cours", "● running"), "run" };
                Process p;
                if (procs.TryGetValue(key, out p))
                {
                    bool alive = false;
                    try { alive = !p.HasExited; } catch (Exception) { }
                    if (alive) return new[] { L("● en cours", "● running"), "run" };
                }
                string txt;
                if (lstatus.TryGetValue(key, out txt)) return new[] { txt, txt.StartsWith("🛡") ? "wait" : "err" };
            }
            if (JsonStore.Str(app["trigger"]) == "parking" && B(app, "enabled", true) && h.SimOn && h.CfgB("launcher_auto", true) && !ParkingFired)
                return RelayConnected ? new[] { L("🅿 attend l'avion au parking", "🅿 waiting for the aircraft at parking"), "wait" }
                                      : new[] { L("🅿 attend le relais (MSFS)", "🅿 waiting for the relay (MSFS)"), "wait" };
            return new[] { L("arrêtée", "stopped"), B(app, "enabled", true) ? "" : "off" };
        }

        public JObject View()
        {
            RefreshImages();
            var arr = new JArray();
            lock (h.Gate)
            {
                foreach (var app in Apps.OfType<JObject>())
                {
                    var st = State(app);
                    arr.Add(new JObject
                    {
                        ["id"] = app["id"], ["name"] = JsonStore.Str(app["name"]), ["path"] = JsonStore.Str(app["path"]),
                        ["args"] = JsonStore.Str(app["args"]), ["cwd"] = JsonStore.Str(app["cwd"]), ["proc"] = JsonStore.Str(app["proc"]),
                        ["delay"] = I(app, "delay"), ["trigger"] = JsonStore.Str(app["trigger"]) == "parking" ? "parking" : "sim",
                        ["close_with_sim"] = B(app, "close_with_sim", true), ["enabled"] = B(app, "enabled", true),
                        ["admin"] = B(app, "admin", false), ["screen"] = JsonStore.Str(app["screen"]),
                        ["state"] = st[0], ["tag"] = st[1],
                    });
                }
            }
            bool anyPending;
            lock (gate) anyPending = pending.Count > 0;
            return new JObject
            {
                ["apps"] = arr, ["auto"] = h.CfgB("launcher_auto", true), ["parkApt"] = h.CfgB("parking_need_airport", true),
                ["pending"] = anyPending, ["screens"] = Screens(),
            };
        }

        public static JArray Screens()
        {
            var arr = new JArray();
            int i = 0;
            foreach (var s in Win.Monitors())
                arr.Add(new JObject { ["dev"] = s.DeviceName, ["label"] = Win.MonitorLabel(s, ++i) });
            return arr;
        }

        public void SetOptions(bool auto, bool parkApt)
        {
            lock (h.Gate)
            {
                h.Cfg["launcher_auto"] = auto;
                h.Cfg["parking_need_airport"] = parkApt;
                h.SaveCfg();
            }
        }

        // ajout (id vide) ou modification d'une application
        public void Save(JObject a)
        {
            string path = JsonStore.Str(a["path"]).Trim();
            if (path == "") throw new Exception(L("Indique le programme à lancer.", "Enter the program to launch."));
            lock (h.Gate)
            {
                string id = JsonStore.Str(a["id"]);
                JObject app = id != "" ? AppById(id) : null;
                if (app == null)
                {
                    app = new JObject { ["id"] = "app" + DateTime.UtcNow.Ticks };
                    Apps.Add(app);
                }
                foreach (var k in new[] { "name", "path", "args", "cwd", "proc" })
                    app[k] = JsonStore.Str(a[k]).Trim();
                if (JsonStore.Str(app["name"]) == "") app["name"] = Path.GetFileNameWithoutExtension(path);
                app["delay"] = Math.Max(0, Math.Min(3600, I(a, "delay")));
                app["trigger"] = JsonStore.Str(a["trigger"]) == "parking" ? "parking" : "sim";
                app["close_with_sim"] = B(a, "close_with_sim", true);
                app["enabled"] = B(a, "enabled", true);
                app["admin"] = B(a, "admin", false);
                app["screen"] = JsonStore.Str(a["screen"]);
                h.SaveCfg();
            }
        }

        public void Delete(List<string> ids)
        {
            lock (h.Gate)
            {
                foreach (var id in ids)
                {
                    CancelPending(id);
                    var app = AppById(id);
                    if (app != null) app.Remove();
                }
                h.SaveCfg();
            }
        }

        public void Move(string id, int step)
        {
            lock (h.Gate)
            {
                var list = Apps;
                var app = AppById(id);
                if (app == null) return;
                int i = list.IndexOf(app), j = i + step;
                if (j < 0 || j >= list.Count) return;
                app.Remove();
                list.Insert(j, app);
                h.SaveCfg();
            }
        }

        // ---------------------------------------------------------------- lancement
        void CancelPending(string id)
        {
            lock (gate)
            {
                pending.Remove(id);
                CancellationTokenSource cts;
                if (pendingCts.TryGetValue(id, out cts)) { cts.Cancel(); pendingCts.Remove(id); }
            }
        }

        public void Schedule(string trigger, string where)
        {
            int n = 0;
            List<JObject> apps;
            lock (h.Gate) apps = Apps.OfType<JObject>().ToList();
            foreach (var app in apps)
            {
                string id = JsonStore.Str(app["id"]);
                bool isPending;
                lock (gate) isPending = pending.ContainsKey(id);
                if (!B(app, "enabled", true) || isPending || (JsonStore.Str(app["trigger"]) == "parking" ? "parking" : "sim") != trigger) continue;
                int delay = I(app, "delay");
                var cts = new CancellationTokenSource();
                lock (gate)
                {
                    pending[id] = DateTime.Now.AddSeconds(delay);
                    pendingCts[id] = cts;
                }
                var captured = app;
                Task.Delay(delay * 1000, cts.Token).ContinueWith(t =>
                {
                    if (t.IsCanceled) return;
                    LaunchApp(captured);
                });
                n++;
            }
            if (n > 0)
                h.Log(string.Format(trigger == "sim"
                    ? L("Démarrage auto : {0} application(s) programmée(s) après le démarrage de MSFS 2024.", "Auto launch: {0} application(s) scheduled after MSFS 2024 starts.")
                    : L("Démarrage auto : {0} application(s) programmée(s) — avion au parking{1}.", "Auto launch: {0} application(s) scheduled — aircraft at parking{1}."), n, where));
        }

        public void LaunchApp(JObject app)
        {
            string key = JsonStore.Str(app["id"]), name = JsonStore.Str(app["name"]);
            lock (gate)
            {
                pending.Remove(key);
                pendingCts.Remove(key);
                lstatus.Remove(key);
            }
            var ps = SplitProcs(JsonStore.Str(app["proc"]));
            if (ps.Count > 0 && ps.Any(Win.RunningImages().Contains))
            {
                h.Log(string.Format(L("Démarrage auto : {0} est déjà ouverte, pas de second lancement.", "Auto launch: {0} is already open, no second launch."), name));
                h.LauncherChanged();
                return;
            }
            string path = JsonStore.Str(app["path"]);
            if (!File.Exists(path) && !Directory.Exists(path))
            {
                lock (gate) lstatus[key] = L("✖ programme introuvable", "✖ program not found");
                h.Log(string.Format(L("Démarrage auto : {0} introuvable ({1}).", "Auto launch: {0} not found ({1})."), name, path));
                h.LauncherChanged();
                return;
            }
            string cwd = JsonStore.Str(app["cwd"]);
            if (cwd == "" || !Directory.Exists(cwd)) cwd = Path.GetDirectoryName(path);
            bool elevate = B(app, "admin", false) && !Win.IsAdmin();
            if (elevate)
            {
                lock (gate) lstatus[key] = L("🛡 confirmation Windows…", "🛡 Windows confirmation…");
                h.LauncherChanged();
            }
            try
            {
                var psi = new ProcessStartInfo(path, JsonStore.Str(app["args"]))
                {
                    UseShellExecute = true,
                    WorkingDirectory = cwd ?? "",
                };
                if (elevate) psi.Verb = "runas";
                var p = Process.Start(psi);
                lock (gate)
                {
                    lstatus.Remove(key);
                    if (p != null) procs[key] = p;
                }
                h.Log(string.Format(elevate ? L("Démarrage auto : {0} lancée en administrateur.", "Auto launch: {0} launched as administrator.")
                                            : L("Démarrage auto : {0} lancée.", "Auto launch: {0} launched."), name));
                PlaceLater(app);
            }
            catch (System.ComponentModel.Win32Exception e)
            {
                string why = e.NativeErrorCode == 1223 ? L("confirmation Windows refusée ou restée sans réponse", "Windows confirmation refused or left unanswered")
                           : e.NativeErrorCode == 2 || e.NativeErrorCode == 3 ? L("programme introuvable", "program not found")
                           : e.Message;
                lock (gate) lstatus[key] = "✖ " + why;
                h.Log(string.Format(L("Démarrage auto : {0} n'a pas été lancée — {1}.", "Auto launch: {0} was not launched — {1}."), name, why));
            }
            catch (Exception e)
            {
                lock (gate) lstatus[key] = L("✖ erreur au lancement", "✖ launch error");
                h.Log(string.Format(L("Démarrage auto : impossible de lancer {0} ({1}).", "Auto launch: unable to launch {0} ({1})."), name, e.Message));
            }
            h.LauncherChanged();
        }

        // place les fenêtres de l'application sur l'écran choisi (pendant 45 s)
        void PlaceLater(JObject app)
        {
            string choice = JsonStore.Str(app["screen"]);
            if (choice == "") return;
            var imgs = SplitProcs(JsonStore.Str(app["proc"]));
            string path = JsonStore.Str(app["path"]);
            if (path.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)) imgs.Add(Path.GetFileName(path));
            string name = JsonStore.Str(app["name"]);
            Task.Run(async () =>
            {
                var moved = new HashSet<IntPtr>();
                bool warned = false;
                for (int i = 0; i < 45; i++)
                {
                    var mon = Win.Resolve(choice);
                    if (mon == null) return;
                    foreach (var hw in Win.WindowsOf(imgs))
                    {
                        if (moved.Contains(hw)) continue;
                        if (Win.MonitorOf(hw) == mon.DeviceName || Win.MoveTo(hw, mon))
                        {
                            moved.Add(hw);
                            if (moved.Count == 1)
                                h.Log(string.Format(L("Démarrage auto : {0} affichée sur l'écran {1}.", "Auto launch: {0} shown on screen {1}."),
                                    name, Win.Monitors().IndexOf(Win.Monitors().First(m => m.DeviceName == mon.DeviceName)) + 1));
                        }
                        else if (!warned)
                        {
                            warned = true;
                            h.Log(string.Format(L("Démarrage auto : impossible de déplacer {0} sur l'écran choisi{1}.", "Auto launch: unable to move {0} to the chosen screen{1}."), name,
                                Win.IsAdmin() ? "" : L(" (elle tourne en administrateur : relance Hangar FS 2024 en administrateur pour pouvoir la déplacer)",
                                                      " (it runs as administrator: restart Hangar FS 2024 as administrator to be able to move it)")));
                        }
                    }
                    await Task.Delay(1000);
                }
            });
        }

        // ---------------------------------------------------------------- arrêt
        static void RunHidden(string exe, string args, bool elevate)
        {
            var psi = new ProcessStartInfo(exe, args) { CreateNoWindow = true, WindowStyle = ProcessWindowStyle.Hidden };
            if (elevate) { psi.UseShellExecute = true; psi.Verb = "runas"; }
            else psi.UseShellExecute = false;
            using (var p = Process.Start(psi)) { if (p != null) p.WaitForExit(15000); }
        }

        static bool AnyRunning(List<string> ps)
        {
            var imgs = Win.RunningImages();
            return ps.Any(imgs.Contains);
        }

        // fermeture d'applications lancées en administrateur : une seule confirmation Windows
        static string ElevatedKill(List<string> ps, bool force)
        {
            string ims = string.Join(" ", ps.Select(x => "/IM \"" + x + "\""));
            try { RunHidden("taskkill.exe", ims + " /T" + (force ? " /F" : ""), true); }
            catch (Exception) { return L("non fermée (confirmation Windows refusée)", "not closed (Windows confirmation refused)"); }
            for (int i = 0; i < 16; i++) { Thread.Sleep(500); if (!AnyRunning(ps)) return L("fermée", "closed"); }
            if (force) return L("fermeture demandée", "closing requested");
            try { RunHidden("taskkill.exe", ims + " /T /F", true); }
            catch (Exception) { return L("non fermée (confirmation Windows refusée)", "not closed (Windows confirmation refused)"); }
            for (int i = 0; i < 10; i++) { Thread.Sleep(500); if (!AnyRunning(ps)) return L("fermée de force (ne répondait pas)", "force-closed (not responding)"); }
            return L("fermeture demandée", "closing requested");
        }

        string StopOne(JObject app, bool force)
        {
            string key = JsonStore.Str(app["id"]);
            CancelPending(key);
            var ps = SplitProcs(JsonStore.Str(app["proc"]));
            Process p;
            lock (gate) { procs.TryGetValue(key, out p); procs.Remove(key); }
            bool elevated = B(app, "admin", false) && !Win.IsAdmin();
            if (elevated && ps.Count > 0) return ElevatedKill(ps, force);
            string target = null;
            if (ps.Count > 0) target = string.Join(" ", ps.Select(x => "/IM \"" + x + "\"")) + " /T";
            else
            {
                bool alive = false;
                try { alive = p != null && !p.HasExited; } catch (Exception) { }
                if (alive) target = "/PID " + p.Id + " /T";
            }
            if (target == null) return L("rien à fermer", "nothing to close");
            RunHidden("taskkill.exe", target + (force ? " /F" : ""), false);
            if (force) return L("arrêtée", "stopped");
            for (int i = 0; i < 12; i++)
            {
                Thread.Sleep(500);
                if (ps.Count > 0 && !AnyRunning(ps)) return L("fermée", "closed");
                if (ps.Count == 0)
                {
                    bool alive = false;
                    try { alive = p != null && !p.HasExited; } catch (Exception) { }
                    if (!alive) return L("fermée", "closed");
                }
            }
            RunHidden("taskkill.exe", target + " /F", false);
            return L("fermée de force (ne répondait pas)", "force-closed (not responding)");
        }

        public void Stop(List<JObject> apps, bool force)
        {
            var elev = apps.Where(a => B(a, "admin", false) && !Win.IsAdmin() && SplitProcs(JsonStore.Str(a["proc"])).Count > 0).ToList();
            var normal = apps.Where(a => !elev.Contains(a)).ToList();
            var tasks = new List<Task>();
            foreach (var a in normal)
            {
                var app = a;
                tasks.Add(Task.Run(() =>
                {
                    string r;
                    try { r = StopOne(app, force); } catch (Exception e) { r = L("— erreur : ", "— error: ") + e.Message; }
                    h.Log(string.Format(L("Démarrage auto : {0} {1}.", "Auto launch: {0} {1}."), JsonStore.Str(app["name"]), r));
                }));
            }
            if (elev.Count == 1)
            {
                var app = elev[0];
                tasks.Add(Task.Run(() => h.Log(string.Format(L("Démarrage auto : {0} {1}.", "Auto launch: {0} {1}."), JsonStore.Str(app["name"]), StopOne(app, force)))));
            }
            else if (elev.Count > 1)
            {
                var ps = new List<string>();
                foreach (var a in elev)
                {
                    string key = JsonStore.Str(a["id"]);
                    CancelPending(key);
                    lock (gate) procs.Remove(key);
                    ps.AddRange(SplitProcs(JsonStore.Str(a["proc"])));
                }
                string names = string.Join(", ", elev.Select(a => JsonStore.Str(a["name"])));
                tasks.Add(Task.Run(() => h.Log(string.Format(L("Démarrage auto : {0} {1} (une seule confirmation Windows).", "Auto launch: {0} {1} (a single Windows confirmation)."),
                    names, ElevatedKill(ps, force)))));
            }
            Task.WhenAll(tasks).ContinueWith(_ => h.LauncherChanged());
        }

        public List<JObject> ByIds(List<string> ids)
        {
            lock (h.Gate) return ids.Select(AppById).Where(a => a != null).ToList();
        }

        public void StartNow(List<string> ids)
        {
            foreach (var a in ByIds(ids))
            {
                CancelPending(JsonStore.Str(a["id"]));
                var app = a;
                Task.Run(() => LaunchApp(app));
            }
        }

        public int StopAll()
        {
            RefreshImages();
            List<JObject> apps;
            lock (h.Gate) apps = Apps.OfType<JObject>().Where(a => { bool p; lock (gate) p = pending.ContainsKey(JsonStore.Str(a["id"])); return p || State(a)[1] == "run"; }).ToList();
            if (apps.Count > 0) Stop(apps, true);
            return apps.Count;
        }

        public void CloseWithSim()
        {
            RefreshImages();
            var todo = new List<JObject>();
            List<JObject> apps;
            lock (h.Gate) apps = Apps.OfType<JObject>().ToList();
            foreach (var app in apps)
            {
                CancelPending(JsonStore.Str(app["id"]));
                if (B(app, "close_with_sim", true) && State(app)[1] == "run") todo.Add(app);
            }
            if (todo.Count > 0)
            {
                Stop(todo, false);
                h.Log(string.Format(L("Démarrage auto : fermeture de {0} application(s) avec MSFS 2024.", "Auto launch: closing {0} application(s) with MSFS 2024."), todo.Count));
            }
        }

        // programmes ouverts, ceux qui ressemblent à l'application d'abord (★)
        public static JObject RunningList(string hint)
        {
            var imgs = Win.RunningImages().Select(x => x.ToLowerInvariant()).Distinct().OrderBy(x => x).ToList();
            var stop = new HashSet<string> { "program", "files", "updater", "launcher", "users", "appdata", "local" };
            var words = System.Text.RegularExpressions.Regex.Matches((hint ?? "").ToLowerInvariant(), "[a-z]{4,}")
                .Cast<System.Text.RegularExpressions.Match>().Select(m => m.Value).Where(w => !stop.Contains(w)).ToList();
            var sugg = imgs.Where(i => words.Any(w => i.Contains(w))).ToList();
            var others = imgs.Where(i => !sugg.Contains(i)).ToList();
            return new JObject { ["sugg"] = new JArray(sugg), ["others"] = new JArray(others) };
        }

        // grand numéro affiché 3 s sur chaque écran
        public static void IdentifyScreens()
        {
            int i = 0;
            foreach (var s in Win.Monitors())
            {
                i++;
                var f = new Form
                {
                    FormBorderStyle = FormBorderStyle.None, TopMost = true, ShowInTaskbar = false,
                    BackColor = ColorTranslator.FromHtml("#3b82f6"), StartPosition = FormStartPosition.Manual,
                    Size = new Size(320, 260),
                };
                f.Location = new Point(s.Bounds.X + (s.Bounds.Width - f.Width) / 2, s.Bounds.Y + (s.Bounds.Height - f.Height) / 2);
                var big = new Label { Text = i.ToString(), ForeColor = Color.White, Font = new Font("Segoe UI", 96, FontStyle.Bold),
                    Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter };
                var small = new Label { Text = (s.Primary ? Hangar.L("Principal · ", "Primary · ") : "") + s.Bounds.Width + " × " + s.Bounds.Height,
                    ForeColor = Color.White, Font = new Font("Segoe UI", 13), Dock = DockStyle.Bottom, Height = 40, TextAlign = ContentAlignment.MiddleCenter };
                f.Controls.Add(big);
                f.Controls.Add(small);
                var t = new System.Windows.Forms.Timer { Interval = 3000 };
                t.Tick += (o, e) => { t.Stop(); f.Close(); };
                f.Shown += (o, e) => t.Start();
                f.Show();
            }
        }
    }
}
