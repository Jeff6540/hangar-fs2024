// Fenêtre principale : l'interface est une page web (dossier ui) affichée par WebView2, le moteur d'Edge
// déjà présent dans Windows 10/11. La page envoie des commandes, le C# fait le travail et répond.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    class MainForm : Form
    {
        readonly WebView2 web = new WebView2();
        readonly Hangar hangar = new Hangar();
        readonly Timer monitor = new Timer();
        bool ticking;
        bool ready;

        public MainForm()
        {
            Text = AppInfo.Name + " — " + AppInfo.Sub + " " + AppInfo.Version + (IsAdmin() ? "  —  🛡 " + Hangar.L("Administrateur", "Administrator") : "");
            BackColor = ColorTranslator.FromHtml("#15181e");
            Size = new Size(1320, 860);
            MinimumSize = new Size(1050, 640);
            StartPosition = FormStartPosition.CenterScreen;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
            web.Dock = DockStyle.Fill;
            web.DefaultBackgroundColor = ColorTranslator.FromHtml("#15181e");
            Controls.Add(web);

            hangar.OnLog += m => Push("log", new JValue(DateTime.Now.ToString("HH:mm:ss") + "  " + m));
            hangar.OnStatus += m => Push("status", new JValue(m));
            hangar.OnChanged += () => Push("changed", JValue.CreateNull());

            monitor.Interval = 4000;
            monitor.Tick += async (s, e) =>
            {
                if (ticking || !ready) return;
                ticking = true;
                try
                {
                    await Task.Run(() => hangar.Tick());
                    Push("sim", new JValue(hangar.SimOn));
                }
                catch (Exception) { }
                finally { ticking = false; }
            };
            Load += async (s, e) => await InitWeb();
        }

        async Task InitWeb()
        {
            try
            {
                var env = await CoreWebView2Environment.CreateAsync(null, Path.Combine(AppInfo.BaseDir, "webview2-cs"));
                await web.EnsureCoreWebView2Async(env);
            }
            catch (Exception ex)
            {
                var r = MessageBox.Show(this,
                    Hangar.L("Le moteur d'affichage WebView2 de Microsoft est introuvable sur ce PC.\n\nIl est gratuit et se trouve normalement déjà dans Windows 10/11. Ouvrir la page de téléchargement de Microsoft ?\n\n(",
                             "Microsoft's WebView2 display engine was not found on this PC.\n\nIt is free and is normally already part of Windows 10/11. Open Microsoft's download page?\n\n(") + ex.Message + ")",
                    AppInfo.Name, MessageBoxButtons.YesNo, MessageBoxIcon.Warning);
                if (r == DialogResult.Yes) OpenUrl("https://developer.microsoft.com/microsoft-edge/webview2/");
                Close();
                return;
            }
            var cw = web.CoreWebView2;
            cw.Settings.AreDevToolsEnabled = false;
            cw.Settings.IsStatusBarEnabled = false;
            cw.Settings.AreDefaultContextMenusEnabled = false;
            cw.Settings.IsZoomControlEnabled = false;
            cw.NewWindowRequested += (s, e) => { e.Handled = true; OpenUrl(e.Uri); };
            cw.WebMessageReceived += OnMessage;
            web.NavigateToString(BuildPage());
        }

        static bool IsAdmin()
        {
            try
            {
                var id = System.Security.Principal.WindowsIdentity.GetCurrent();
                return new System.Security.Principal.WindowsPrincipal(id).IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
            }
            catch (Exception) { return false; }
        }

        static string Resource(string name)
        {
            using (var st = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            using (var sr = new StreamReader(st, System.Text.Encoding.UTF8))
                return sr.ReadToEnd();
        }

        static string ResourceDataUri(string name, string mime)
        {
            using (var st = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            using (var ms = new MemoryStream())
            {
                st.CopyTo(ms);
                return "data:" + mime + ";base64," + Convert.ToBase64String(ms.ToArray());
            }
        }

        static string BuildPage()
        {
            return Resource("ui.index.html")
                .Replace("{{BANNER_FR}}", ResourceDataUri("ui.banner_fr.png", "image/png"))
                .Replace("{{BANNER_EN}}", ResourceDataUri("ui.banner_en.png", "image/png"))
                .Replace("{{FLAG_FR}}", ResourceDataUri("ui.flag_fr.png", "image/png"))
                .Replace("{{FLAG_EN}}", ResourceDataUri("ui.flag_en.png", "image/png"))
                .Replace("{{VERSION}}", AppInfo.Version);
        }

        // ---------------------------------------------------------------- échanges avec la page
        void Push(string evt, JToken data)
        {
            if (IsDisposed) return;
            if (InvokeRequired)
            {
                try { BeginInvoke((Action)(() => Push(evt, data))); } catch (Exception) { }
                return;
            }
            if (web.CoreWebView2 == null) return;
            var o = new JObject { ["event"] = evt, ["data"] = data };
            try { web.CoreWebView2.PostWebMessageAsJson(o.ToString(Formatting.None)); } catch (Exception) { }
        }

        void Reply(JToken id, bool ok, JToken data, string error)
        {
            if (web.CoreWebView2 == null) return;
            var o = new JObject { ["id"] = id, ["ok"] = ok };
            if (ok) o["data"] = data ?? JValue.CreateNull();
            else o["error"] = error ?? "";
            try { web.CoreWebView2.PostWebMessageAsJson(o.ToString(Formatting.None)); } catch (Exception) { }
        }

        async void OnMessage(object sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            JObject msg;
            try { msg = JObject.Parse(e.WebMessageAsJson); }
            catch (Exception) { return; }
            JToken id = msg["id"];
            string cmd = JsonStore.Str(msg["cmd"]);
            var args = msg["args"] as JObject ?? new JObject();
            try
            {
                JToken data = await HandleCommand(cmd, args);
                Reply(id, true, data, null);
            }
            catch (Exception ex)
            {
                Reply(id, false, null, ex.Message);
            }
        }

        static List<string> StrList(JToken t)
        {
            var a = t as JArray;
            return a == null ? new List<string>() : a.Select(x => JsonStore.Str(x)).ToList();
        }

        async Task<JToken> HandleCommand(string cmd, JObject a)
        {
            switch (cmd)
            {
                case "init":
                    ready = true;
                    monitor.Start();
                    var info = new JObject
                    {
                        ["version"] = AppInfo.Version, ["lang"] = Hangar.Lang,
                        ["settings"] = hangar.SettingsView(), ["sim"] = hangar.SimRunning(),
                    };
                    var _ = Task.Run(() =>
                    {
                        try { hangar.Rescan(); }
                        catch (Exception ex) { hangar.Status(ex.Message); }
                    });
                    return info;
                case "library":
                    return await Task.Run(() => (JToken)hangar.LibraryView());
                case "rescan":
                    await Task.Run(() => hangar.Rescan());
                    return null;
                case "activate":
                    return await Task.Run(() => (JToken)hangar.Activate(StrList(a["paths"])));
                case "remove":
                    return await Task.Run(() => (JToken)hangar.Remove(StrList(a["paths"])));
                case "pin":
                    await Task.Run(() => hangar.SetPinned(StrList(a["paths"]), (bool)a["on"]));
                    return null;
                case "setIcao":
                    hangar.SetIcao(JsonStore.Str(a["path"]), StrList(a["codes"]));
                    return null;
                case "undo":
                    await Task.Run(() => hangar.Undo());
                    return null;
                case "communitySize":
                    {
                        var tops = StrList(a["paths"]);
                        long n = await Task.Run(() => Hangar.FolderSize(tops));
                        return new JValue(Hangar.FmtSize(n));
                    }
                case "removeCommunity":
                    await Task.Run(() => hangar.RemoveCommunityLinks(StrList(a["links"])));
                    return null;
                case "flight":
                    return await Task.Run(() => (JToken)hangar.FlightView());
                case "fetchPlan":
                    await Task.Run(() => hangar.FetchPlan(JsonStore.Str(a["user"])));
                    return null;
                case "prepareFlight":
                    {
                        var choices = a["choices"] as JObject;
                        return await Task.Run(() => (JToken)hangar.PrepareFlight(choices, false));
                    }
                case "endFlight":
                    await Task.Run(() => hangar.EndFlight(false));
                    return null;
                case "setOption":
                    hangar.SetOption(JsonStore.Str(a["key"]), (bool)a["value"]);
                    return null;
                case "saveSettings":
                    hangar.SaveSettings(a);
                    var __ = Task.Run(() => hangar.Rescan());
                    return null;
                case "detectCommunity":
                    return new JValue(Scanner.DetectCommunity());
                case "browse":
                    {
                        using (var dlg = new FolderBrowserDialog())
                        {
                            dlg.Description = JsonStore.Str(a["title"]);
                            string cur = JsonStore.Str(a["current"]);
                            if (cur != "" && Directory.Exists(cur)) dlg.SelectedPath = cur;
                            return dlg.ShowDialog(this) == DialogResult.OK ? new JValue(dlg.SelectedPath) : JValue.CreateNull();
                        }
                    }
                case "setLang":
                    hangar.SetLang(JsonStore.Str(a["lang"]));
                    return null;
                case "reload":
                    web.NavigateToString(BuildPage());
                    return null;
                case "openUrl":
                    OpenUrl(JsonStore.Str(a["url"]));
                    return null;
                case "openFolder":
                    {
                        string p = JsonStore.Str(a["path"]);
                        if (p != "" && Directory.Exists(p)) Process.Start("explorer.exe", "\"" + p + "\"");
                        return null;
                    }
                case "quit":
                    Close();
                    return null;
                default:
                    throw new Exception("commande inconnue : " + cmd);
            }
        }

        static void OpenUrl(string url)
        {
            if (string.IsNullOrEmpty(url)) return;
            if (!(url.StartsWith("https://") || url.StartsWith("http://"))) return;
            try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); } catch (Exception) { }
        }
    }
}
