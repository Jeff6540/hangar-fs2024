using System;
using System.Threading;
using System.Windows.Forms;

namespace HangarFS2024
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            var args = Environment.GetCommandLineArgs();
            bool has(string a) { return Array.IndexOf(args, a) >= 0; }
            // démarrage avec Windows en mode administrateur : relance par la tâche planifiée, sans confirmation
            if (!has("--from-task") && !has("--wait-mutex") && !Win.IsAdmin())
            {
                try
                {
                    var cfg = JsonStore.Load(AppInfo.ConfigFile, new Newtonsoft.Json.Linq.JObject());
                    var t = cfg["startup_admin"];
                    if (t != null && t.Type == Newtonsoft.Json.Linq.JTokenType.Boolean && (bool)t && SystemTools.TaskIsOurs() && SystemTools.RunAdminTask()) return;
                }
                catch (Exception) { }
            }
            bool created;
            using (var mutex = new Mutex(true, "Jeff40.HangarFS2024.CSharp", out created))
            {
                if (!created && (has("--wait-mutex") || has("--from-task")))
                {
                    try { created = mutex.WaitOne(15000); } catch (AbandonedMutexException) { created = true; }
                }
                if (!created)
                {
                    MessageBox.Show(Hangar.L("Hangar FS 2024 est déjà ouvert.", "Hangar FS 2024 is already open."),
                                    AppInfo.Name, MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return;
                }
                Updater.CleanupOld();   // fichiers .old d'une mise à jour précédente
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                var form = new MainForm();
                if (has("--minimized") || (has("--from-task") && SystemTools.StartWithWindows && Environment.TickCount < 5 * 60 * 1000))
                    form.WindowState = FormWindowState.Minimized;
                Application.Run(form);
            }
        }
    }
}
