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
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); DarkTitle.Apply(this); }   // barre de titre sombre

        readonly WebView2 web = new WebView2();
        readonly Hangar hangar = new Hangar();
        readonly Timer monitor = new Timer();
        bool ticking;
        bool ready;
        readonly Dictionary<string, WebWindow> webWins = new Dictionary<string, WebWindow>();

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

            WebWindow.NavRequested += nav => { try { BeginInvoke((Action)(() => { var t = Nav(nav); })); } catch (Exception) { } };
            hangar.OnLog += m => Push("log", new JValue(DateTime.Now.ToString("HH:mm:ss") + "  " + m));
            hangar.OnStatus += m => Push("status", new JValue(m));
            hangar.OnChanged += () => Push("changed", JValue.CreateNull());
            hangar.OnLauncher += () => Push("launcher", JValue.CreateNull());

            monitor.Interval = 4000;
            monitor.Tick += async (s, e) =>
            {
                if (ticking || !ready) return;
                ticking = true;
                try
                {
                    await Task.Run(() => hangar.Tick());
                    Push("sim", new JValue(hangar.SimOn));
                    PushRelay();
                }
                catch (Exception) { }
                finally { ticking = false; }
            };
            hangar.CloseWebWindow = w =>
            {
                bool ok = false;
                try { Invoke((Action)(() => { WebWindow f; if (webWins.TryGetValue(w, out f) && !f.IsDisposed) { f.Close(); ok = true; } })); } catch (Exception) { }
                return ok;
            };
            hangar.ReloadWebWindows = () =>
            {
                try
                {
                    BeginInvoke((Action)(() =>
                    {
                        foreach (var kv in new List<KeyValuePair<string, WebWindow>>(webWins))
                            if (kv.Key != "tuto" && !kv.Value.IsDisposed) kv.Value.ReloadPage();
                    }));
                }
                catch (Exception) { }
            };
            hangar.OnLauncher += () => PushRelay();
            hangar.OpenUrl = WebWindow.OpenExternal;
            PlaceMain();
            FormClosing += (s, e) =>
            {
                monitor.Stop();
                foreach (var w in new List<WebWindow>(webWins.Values)) { try { w.Close(); } catch (Exception) { } }
                try { hangar.RelayStopNow(""); } catch (Exception) { }
            };
            Load += async (s, e) => await InitWeb();
            Shown += (s, e) =>
            {
                Task.Run(() => hangar.InitRelay());
                if (File.Exists(Airports.FilePath)) Task.Run(() => { System.Threading.Thread.Sleep(800); hangar.LoadAirports(false); });
                Task.Run(() => { System.Threading.Thread.Sleep(4000); try { hangar.SyncLibraryState(); } catch (Exception) { } });
            };
        }

        Screen ScreenFor(string which)
        {
            if (!hangar.CfgB("screen_" + which, true)) return null;
            string choice = hangar.CfgS("screen");
            return Win.Resolve(choice == "" ? "auto" : choice);
        }

        void PlaceMain()
        {
            var mon = ScreenFor("main");
            if (mon == null) return;
            var wa = mon.WorkingArea;
            int w = Math.Min(1320, wa.Width - 20), h = Math.Min(860, wa.Height - 40);
            StartPosition = FormStartPosition.Manual;
            Bounds = new Rectangle(wa.X + (wa.Width - w) / 2, wa.Y + Math.Max(0, (wa.Height - h) / 2 - 15), w, h);
        }

        void PushRelay()
        {
            Push("relay", new JObject { ["text"] = hangar.RelayText(), ["button"] = hangar.RelayButton(), ["airports"] = hangar.AirportsStatus, ["on"] = hangar.RelayRunning, ["connected"] = hangar.RelayRunning && hangar.Relay.Connected });
        }

        void OpenWeb(string which, string path, string title, Size size, bool maximize)
        {
            WebWindow f;
            if (webWins.TryGetValue(which, out f) && !f.IsDisposed) { f.BringUp(); return; }
            int port = hangar.PagePort();
            f = new WebWindow(title, "http://127.0.0.1:" + port + path, size);
            f.PlaceOn(ScreenFor(which == "tuto" ? "map" : which), maximize);
            f.FormClosed += (o, e) => webWins.Remove(which);
            webWins[which] = f;
            f.Show();
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

        /// <summary>Ouvre Avionics Dispatch sur le plan de vol, le suivi de vol ou le journal.</summary>
        async Task<JToken> OpenDispatchAt(string what)
        {
            if (!hangar.RelayRunning && !hangar.RelayManualOff && !hangar.RelayPortBusy) await Task.Run(() => hangar.RelayStart(false, false));
            WebWindow w;
            if (webWins.TryGetValue("dispatch", out w) && !w.IsDisposed) { w.BringUp(); w.PostJson("{\"open\":\"" + what + "\"}"); }
            else OpenWeb("dispatch", "/dispatch" + (what == "plan" ? "" : "#" + what), JsonStore.Str(Hangar.Titles()["dispatch_" + Hangar.Lang]), new Size(1500, 950), true);
            return null;
        }

        /// <summary>Navigation demandée par le menu repliable d'une autre fenêtre.</summary>
        async Task Nav(string nav)
        {
            switch (nav)
            {
                case "map": await HandleCommand("openMap", new JObject()); return;
                case "dispatch": case "plan": await HandleCommand("openPlan", new JObject()); return;
                case "track": await HandleCommand("openTracking", new JObject()); return;
                case "journal": await HandleCommand("openJournal", new JObject()); return;
                case "tuto": await HandleCommand("openTutorial", new JObject()); return;
                // 12.9 : carte « Plan de vol personnel » et radars FSHub depuis les menus
                case "perso": case "vfr": case "rva": case "rvradar": await OpenDispatchAt(nav); return;
                case "rglobal": OpenUrl("https://fshub.io/radar"); return;
                case "lib": case "launch": case "vol": case "set":
                    if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal;
                    Show(); Activate(); BringToFront();
                    Push("nav", new JObject { ["tab"] = nav });
                    return;
            }
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
                    if (hangar.CfgB("update_check", true))
                        Task.Run(() => { System.Threading.Thread.Sleep(4000); try { var found = Updater.Check(); if (found != null) Push("update", new JObject { ["available"] = found }); } catch (Exception) { } });
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
                case "launcher":
                    return await Task.Run(() => (JToken)hangar.Launcher.View());
                case "launcherOptions":
                    hangar.Launcher.SetOptions((bool)a["auto"], (bool)a["parkApt"]);
                    return null;
                case "launcherSave":
                    hangar.Launcher.Save(a);
                    return null;
                case "launcherDelete":
                    hangar.Launcher.Delete(StrList(a["ids"]));
                    return null;
                case "launcherMove":
                    hangar.Launcher.Move(JsonStore.Str(a["id"]), (int)a["step"]);
                    return null;
                case "launcherStart":
                    hangar.Launcher.StartNow(StrList(a["ids"]));
                    return null;
                case "launcherStop":
                    hangar.Launcher.Stop(hangar.Launcher.ByIds(StrList(a["ids"])), true);
                    return null;
                case "launcherStopAll":
                    return new JValue(await Task.Run(() => hangar.Launcher.StopAll()));
                case "runningList":
                    {
                        string hint = JsonStore.Str(a["hint"]);
                        return await Task.Run(() => (JToken)Launcher.RunningList(hint));
                    }
                case "identifyScreens":
                    Launcher.IdentifyScreens();
                    return null;
                case "pickProgram":
                    {
                        using (var dlg = new OpenFileDialog())
                        {
                            dlg.Title = JsonStore.Str(a["title"]);
                            dlg.Filter = Hangar.L("Programmes et raccourcis", "Programs and shortcuts") + "|*.exe;*.lnk;*.bat;*.cmd|" +
                                         Hangar.L("Tous les fichiers", "All files") + "|*.*";
                            if (dlg.ShowDialog(this) != DialogResult.OK) return JValue.CreateNull();
                            string path = Path.GetFullPath(dlg.FileName), args = "", cwd = "";
                            if (path.EndsWith(".lnk", StringComparison.OrdinalIgnoreCase) && JsonStore.Str(a["resolve"]) != "no")
                            {
                                var r = Win.ResolveShortcut(path);
                                if (r[0] != "") { path = r[0]; args = r[1]; cwd = r[2]; }
                            }
                            return new JObject { ["path"] = path, ["args"] = args, ["cwd"] = cwd };
                        }
                    }
                case "openMap":
                    {
                        if (hangar.AirportsDb == null) await Task.Run(() => hangar.LoadAirports(true));
                        if (hangar.DupStreamed == null) { var _s = Task.Run(() => hangar.ScanStreamedNow()); }
                        hangar.PushMap();
                        OpenWeb("map", "/", JsonStore.Str(Hangar.Titles()["map_window"]), new Size(1400, 900), false);
                        return null;
                    }
                case "openDispatch":
                    if (!hangar.RelayRunning && !hangar.RelayManualOff && !hangar.RelayPortBusy) await Task.Run(() => hangar.RelayStart(false, false));
                    OpenWeb("dispatch", "/dispatch", JsonStore.Str(Hangar.Titles()["dispatch_" + Hangar.Lang]), new Size(1500, 950), true);
                    return null;
                case "openNotes":
                    {   // liste complète des nouveautés, à côté de l'appli
                        string nf = Path.Combine(Updater.AppDir, "Nouveautes - What's new.txt");
                        if (File.Exists(nf)) Process.Start(new ProcessStartInfo(nf) { UseShellExecute = true });
                        else OpenUrl("https://github.com/Jeff6540/hangar-fs2024/releases/latest");
                        return null;
                    }
                case "openTracking": return await OpenDispatchAt("track");
                case "openPlan": return await OpenDispatchAt("plan");
                case "openPerso": return await OpenDispatchAt("perso");
                case "openVfr": return await OpenDispatchAt("vfr");
                case "openRadar":
                    {
                        var radarKey = JsonStore.Str(a["k"]);
                        if (radarKey == "rglobal") { OpenUrl("https://fshub.io/radar"); return null; }
                        if (radarKey == "rva" || radarKey == "rvradar") return await OpenDispatchAt(radarKey);
                        return null;
                    }
                case "openJournal":
                    {
                        if (!hangar.RelayRunning && !hangar.RelayManualOff && !hangar.RelayPortBusy) await Task.Run(() => hangar.RelayStart(false, false));
                        WebWindow jw;
                        if (webWins.TryGetValue("dispatch", out jw) && !jw.IsDisposed) { jw.BringUp(); jw.PostJson("{\"open\":\"journal\"}"); }
                        else OpenWeb("dispatch", "/dispatch#journal", JsonStore.Str(Hangar.Titles()["dispatch_" + Hangar.Lang]), new Size(1500, 950), true);
                        return null;
                    }
                case "openTutorial":
                    OpenWeb("tuto", "/tutorial", JsonStore.Str(Hangar.Titles()["tuto_" + Hangar.Lang]), new Size(1100, 900), false);
                    return null;
                case "relayToggle":
                    await Task.Run(() => hangar.RelayToggle());
                    PushRelay();
                    return null;
                case "relayInfo":
                    return new JObject { ["text"] = hangar.RelayText(), ["button"] = hangar.RelayButton(), ["airports"] = hangar.AirportsStatus, ["on"] = hangar.RelayRunning, ["connected"] = hangar.RelayRunning && hangar.Relay.Connected };
                case "launchMsfs":
                    hangar.LaunchMsfs();
                    return null;
                case "detectStreamed":
                    return new JValue(Hangar.DetectStreamed(JsonStore.Str(a["community"])));
                case "detectMsfs":
                    return new JValue(Hangar.DetectMsfsLaunch());
                case "setValue":
                    hangar.SetValue(JsonStore.Str(a["key"]), a["value"]);
                    return null;
                case "testFshub":
                    return new JValue(await Task.Run(() => hangar.TestFshub()));
                case "setStartup":
                    {
                        bool on = (bool)a["on"], adm = (bool)a["admin"];
                        string err = await Task.Run(() => hangar.SetStartup(on, adm));
                        if (err != "") throw new Exception(err);
                        return hangar.SettingsView();
                    }
                case "restartAdmin":
                    if (SystemTools.Relaunch(true, false)) Close();
                    return null;
                case "desktopShortcut":
                    SystemTools.CreateDesktopShortcut();
                    hangar.Status(Hangar.L("Raccourci créé sur le Bureau.", "Shortcut created on the Desktop."));
                    return null;
                case "screens":
                    {
                        var arr = new JArray();
                        int i = 0;
                        foreach (var s in Win.Monitors())
                            arr.Add(new JObject { ["dev"] = s.DeviceName, ["num"] = ++i, ["primary"] = s.Primary, ["x"] = s.Bounds.X, ["y"] = s.Bounds.Y,
                                ["w"] = s.Bounds.Width, ["h"] = s.Bounds.Height, ["label"] = Win.MonitorLabel(s, i) });
                        return arr;
                    }
                case "exportSettings":
                    {
                        using (var dlg = new SaveFileDialog())
                        {
                            dlg.Title = Hangar.L("Exporter mes réglages", "Export my settings");
                            dlg.Filter = Hangar.L("Sauvegarde Hangar FS 2024", "Hangar FS 2024 backup") + "|*.zip";
                            dlg.FileName = "Hangar_FS2024_reglages_" + DateTime.Now.ToString("yyyy-MM-dd") + ".zip";
                            dlg.InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                            if (dlg.ShowDialog(this) != DialogResult.OK) return JValue.CreateNull();
                            SystemTools.Export(dlg.FileName, hangar.Cfg);
                            hangar.Log(Hangar.L("Réglages exportés : ", "Settings exported: ") + Path.GetFileName(dlg.FileName));
                            return new JValue(dlg.FileName);
                        }
                    }
                case "pickBackup":
                    {
                        using (var dlg = new OpenFileDialog())
                        {
                            dlg.Title = Hangar.L("Restaurer mes réglages", "Restore my settings");
                            dlg.Filter = Hangar.L("Sauvegarde Hangar FS 2024", "Hangar FS 2024 backup") + "|*.zip";
                            if (dlg.ShowDialog(this) != DialogResult.OK) return JValue.CreateNull();
                            var r = SystemTools.ReadBackup(dlg.FileName);
                            return new JObject { ["path"] = dlg.FileName, ["date"] = r[0]["date"], ["version"] = r[0]["version"] };
                        }
                    }
                case "restoreBackup":
                    {
                        if (hangar.SimRunning()) throw new Exception(Hangar.L("Ferme d'abord MSFS 2024 : l'appli redémarre après la restauration.", "Close MSFS 2024 first: the app restarts after restoring."));
                        var r = SystemTools.ReadBackup(JsonStore.Str(a["path"]));
                        if (File.Exists(AppInfo.ConfigFile))
                            File.Copy(AppInfo.ConfigFile, Path.Combine(AppInfo.BaseDir, "config_avant_restauration_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".json"), true);
                        var cfg = r[1];
                        cfg["lang"] = Hangar.Lang;
                        JsonStore.Save(AppInfo.ConfigFile, cfg);
                        hangar.Cfg = cfg;
                        if (SystemTools.Relaunch(false, false)) Close();
                        return null;
                    }
                case "profiles":
                    return hangar.ProfilesView();
                case "profileExists":
                    return new JValue(hangar.ProfileExists(JsonStore.Str(a["name"])));
                case "profileSave":
                    hangar.ProfileSave(JsonStore.Str(a["name"]).Trim(), StrList(a["paths"]), a["index"] != null ? (int)a["index"] : -1);
                    return null;
                case "profileEdit":
                    hangar.ProfileEdit((int)a["index"], a["change"] as JObject ?? new JObject());
                    return null;
                case "profileActivate":
                    {
                        int idx = (int)a["index"]; bool conf = a["confirm"] != null && (bool)a["confirm"];
                        return await Task.Run(() => (JToken)hangar.ProfileActivate(idx, conf));
                    }
                case "restorePins":
                    await Task.Run(() => hangar.RestorePins());
                    return null;
                case "duplicates":
                    return await Task.Run(() => (JToken)hangar.Duplicates());
                case "scanStreamed":
                    {
                        string folder = JsonStore.Str(a["folder"]);
                        if (folder != "") { lock (hangar.Gate) { hangar.Cfg["streamed"] = folder; hangar.SaveCfg(); } }
                        await Task.Run(() => hangar.ScanStreamedNow());
                        return new JValue(hangar.DupStreamed != null ? hangar.DupStreamed.Count : -1);
                    }
                case "contentCheck":
                    return hangar.ContentCheck();
                case "contentAnswer":
                    hangar.ContentAnswer((bool)a["backup"], JsonStore.Str(a["folder"]), a["hide"] != null && (bool)a["hide"]);
                    return null;
                case "disableDefaults":
                    await Task.Run(() => hangar.DisableDefaults(StrList(a["names"])));
                    return null;
                case "enableDefaults":
                    await Task.Run(() => hangar.EnableDefaults(StrList(a["names"])));
                    return null;
                case "contentBackups":
                    return hangar.ContentBackups();
                case "contentRestore":
                    hangar.ContentRestore(JsonStore.Str(a["file"]));
                    return null;
                case "health":
                    return await Task.Run(() => (JToken)hangar.Health());
                case "repair":
                    await Task.Run(() => hangar.Repair());
                    return null;
                case "quarantine":
                    return await Task.Run(() => (JToken)hangar.Quarantine(StrList(a["paths"])));
                case "quarantineList":
                    return hangar.QuarantineList();
                case "quarantineRestore":
                    return new JValue(await Task.Run(() => hangar.QuarantineRestore(StrList(a["paths"]))));
                case "deleteBroken":
                    return new JValue(await Task.Run(() => hangar.DeleteBroken(a["paths"] != null ? StrList(a["paths"]) : null)));
                case "moveToLibrary":
                    {
                        string path = JsonStore.Str(a["path"]), dest = JsonStore.Str(a["dest"]);
                        await Task.Run(() => hangar.MoveToLibrary(path, dest));
                        return null;
                    }
                case "regenLayout":
                    {
                        string pkg = hangar.RealTarget(JsonStore.Str(a["path"]));
                        return new JValue(await Task.Run(() => hangar.RegenLayout(pkg)));
                    }
                case "properties":
                    {
                        string path = JsonStore.Str(a["path"]);
                        return await Task.Run(() => (JToken)hangar.Properties(path));
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
                    // les autres fenêtres (Avionics Dispatch, journal de vol, carte, tutoriel) passent aussi dans la nouvelle langue
                    foreach (var w in webWins.Values.ToList()) if (!w.IsDisposed) w.ReloadPage();
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
                case "updateCheck":
                    {
                        JObject updFound = null;
                        try { updFound = await Task.Run(() => Updater.Check()); }
                        catch (Exception ex) { return new JObject { ["error"] = Hangar.L("Impossible de vérifier les mises à jour (", "Unable to check for updates (") + ex.Message + ")." }; }
                        return updFound ?? new JObject { ["none"] = true, ["version"] = AppInfo.Version };
                    }
                case "updateApply":
                    {
                        var updInfo = a["info"] as JObject;
                        if (updInfo == null) return null;
                        if (hangar.SimRunning())
                            return new JObject { ["blocked"] = Hangar.L("Flight Simulator est ouvert. Ferme-le d'abord, puis clique à nouveau sur Mettre à jour.",
                                                                        "Flight Simulator is running. Close it first, then click Update again.") };
                        var updTask = Task.Run(() =>
                        {
                            try
                            {
                                Updater.Apply(updInfo, (pc, txt) => Push("update", new JObject { ["progress"] = pc, ["text"] = txt }));
                                BeginInvoke((Action)(() => Close()));
                            }
                            catch (Exception ex) { Push("update", new JObject { ["error"] = ex.Message }); }
                        });
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
