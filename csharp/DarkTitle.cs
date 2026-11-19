using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace HangarFS2024
{
    /// <summary>Barre de titre Windows en sombre (mêmes boutons réduire / agrandir / fermer, seule la couleur change).</summary>
    static class DarkTitle
    {
        [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);

        public static void Apply(Form f)
        {
            try
            {
                if (Environment.OSVersion.Version.Major < 10) return;
                int on = 1;
                if (DwmSetWindowAttribute(f.Handle, 20, ref on, 4) != 0) DwmSetWindowAttribute(f.Handle, 19, ref on, 4);   // mode sombre (Windows 10 1809+ / 11)
                int caption = 0x00191210;   // #101219 : fond de la barre (Windows 11), couleur de l'appli
                DwmSetWindowAttribute(f.Handle, 35, ref caption, 4);
                int text = 0x00F0EDE6;      // #E6EDF0 : texte du titre
                DwmSetWindowAttribute(f.Handle, 36, ref text, 4);
            }
            catch (Exception) { }
        }
    }
}
