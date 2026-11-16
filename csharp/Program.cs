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
            bool created;
            using (var mutex = new Mutex(true, "Jeff40.HangarFS2024.CSharp", out created))
            {
                if (!created)
                {
                    MessageBox.Show(Hangar.L("Hangar FS 2024 est déjà ouvert.", "Hangar FS 2024 is already open."),
                                    AppInfo.Name, MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return;
                }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new MainForm());
            }
        }
    }
}
