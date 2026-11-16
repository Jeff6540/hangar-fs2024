// Fenêtres de la carte des scènes, de Plan & suivi de vol et du tutoriel : la page est servie par l'appli
// (http://127.0.0.1:47620…) et affichée par WebView2, comme les fenêtres dédiées de la 11.8.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace HangarFS2024
{
    class WebWindow : Form
    {
        readonly WebView2 web = new WebView2();
        readonly string url;

        public WebWindow(string title, string url, Size size)
        {
            this.url = url;
            Text = title;
            BackColor = ColorTranslator.FromHtml("#15181e");
            Size = size;
            StartPosition = FormStartPosition.CenterScreen;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
            web.Dock = DockStyle.Fill;
            web.DefaultBackgroundColor = ColorTranslator.FromHtml("#15181e");
            Controls.Add(web);
            Load += async (s, e) =>
            {
                try
                {
                    var env = await CoreWebView2Environment.CreateAsync(null, Path.Combine(AppInfo.BaseDir, "webview2-cs"));
                    await web.EnsureCoreWebView2Async(env);
                    var cw = web.CoreWebView2;
                    cw.Settings.IsStatusBarEnabled = false;
                    cw.NewWindowRequested += (o, a) => { a.Handled = true; OpenExternal(a.Uri); };
                    cw.DocumentTitleChanged += (o, a) => { if (!string.IsNullOrEmpty(cw.DocumentTitle) && !cw.DocumentTitle.StartsWith("http")) Text = cw.DocumentTitle; };
                    // F5 recharge la page, comme dans la 11.8
                    web.KeyDown += (o, a) => { if (a.KeyCode == Keys.F5) cw.Reload(); };
                    web.Source = new Uri(url);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(this, ex.Message, AppInfo.Name, MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    Close();
                }
            };
        }

        public static void OpenExternal(string u)
        {
            if (string.IsNullOrEmpty(u) || !(u.StartsWith("http://") || u.StartsWith("https://"))) return;
            try { Process.Start(new ProcessStartInfo(u) { UseShellExecute = true }); } catch (Exception) { }
        }

        public void PlaceOn(Screen mon, bool maximize)
        {
            if (mon == null) { if (maximize) WindowState = FormWindowState.Maximized; return; }
            StartPosition = FormStartPosition.Manual;
            var wa = mon.WorkingArea;
            int w = Math.Min(Width, wa.Width), h = Math.Min(Height, wa.Height);
            Bounds = new Rectangle(wa.X + (wa.Width - w) / 2, wa.Y + (wa.Height - h) / 2, w, h);
            if (maximize) WindowState = FormWindowState.Maximized;
        }

        public void BringUp()
        {
            if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal;
            Show();
            Activate();
        }
    }
}
