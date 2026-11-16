// Suite de la logique : base des aéroports, scènes par défaut, carte des scènes, relais et serveur des pages,
// détection de l'avion au parking, lancement de MSFS.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    partial class Hangar
    {
        // ---------------------------------------------------------------- base des aéroports
        public Dictionary<string, AirportRec> AirportsDb;
        Dictionary<string, List<KeyValuePair<string, AirportRec>>> cityIdx = new Dictionary<string, List<KeyValuePair<string, AirportRec>>>();
        readonly Dictionary<string, List<string>> icaoCache = new Dictionary<string, List<string>>();
        int airportsLoading;

        public bool LoadAirports(bool interactive)
        {
            if (Interlocked.Exchange(ref airportsLoading, 1) == 1) return false;
            try
            {
                Status(L("Chargement de la base des aéroports…", "Loading the airport database…"));
                var db = Airports.Load();
                var idx = Airports.CityIndex(db);
                lock (Gate) { AirportsDb = db; cityIdx = idx; icaoCache.Clear(); }
                Status(string.Format(L("Base des aéroports chargée : {0} terrains.", "Airport database loaded: {0} airfields."), db.Count));
                AirportsStatus = string.Format(L("Base des aéroports chargée : {0} terrains", "Airport database loaded: {0} airfields"), db.Count);
                Changed();
                return true;
            }
            catch (Exception e)
            {
                lock (Gate) { if (AirportsDb == null) AirportsDb = new Dictionary<string, AirportRec>(); }
                if (interactive) Log(L("Base des aéroports indisponible : ", "Airport database unavailable: ") + e.Message);
                return false;
            }
            finally { Interlocked.Exchange(ref airportsLoading, 0); }
        }
        public string AirportsStatus = "";

        // codes OACI vérifiés avec la base (appelé par AirportIcaos)
        List<string> ResolveWithDb(Pkg p)
        {
            var db = AirportsDb;
            if (db == null || db.Count == 0 || p.Icao.Count == 0) return new List<string>(p.Icao);
            string key = p.FullPath + "|" + string.Join(",", p.Icao);
            List<string> r;
            lock (icaoCache)
            {
                if (!icaoCache.TryGetValue(key, out r))
                {
                    r = Airports.ResolveCodes(p.Icao, p.Name + " " + p.Title, db, cityIdx);
                    icaoCache[key] = r;
                }
            }
            return new List<string>(r);
        }

        // ---------------------------------------------------------------- scènes par défaut (StreamedPackages)
        public static string DetectStreamed(string community)
        {
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            var c = new List<string>();
            if (!string.IsNullOrEmpty(community)) { try { c.Add(Path.Combine(Path.GetDirectoryName(Scanner.NormDir(community)), "StreamedPackages")); } catch (Exception) { } }
            foreach (var b in PackagesPaths()) c.Add(Path.Combine(b, "StreamedPackages"));
            c.Add(Path.Combine(local, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalState", "StreamedPackages"));
            c.Add(Path.Combine(local, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "StreamedPackages"));
            c.Add(Path.Combine(local, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "Packages", "StreamedPackages"));
            c.Add(Path.Combine(roaming, "Microsoft Flight Simulator 2024", "Packages", "StreamedPackages"));
            c.Add(Path.Combine(roaming, "Microsoft Flight Simulator 2024", "StreamedPackages"));
            foreach (var d in c) { try { if (Directory.Exists(d)) return Path.GetFullPath(d); } catch (Exception) { } }
            return "";
        }

        static List<string> PackagesPaths()
        {
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            var outp = new List<string>();
            foreach (var opt in new[] { Path.Combine(local, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "UserCfg.opt"),
                                        Path.Combine(roaming, "Microsoft Flight Simulator 2024", "UserCfg.opt") })
            {
                try
                {
                    if (!File.Exists(opt)) continue;
                    foreach (var raw in File.ReadAllLines(opt))
                    {
                        string line = raw.Trim();
                        if (!line.StartsWith("InstalledPackagesPath")) continue;
                        var parts = line.Split(new[] { ' ', '\t' }, 2, StringSplitOptions.RemoveEmptyEntries);
                        if (parts.Length == 2) outp.Add(parts[1].Trim().Trim('"'));
                    }
                }
                catch (Exception) { }
            }
            return outp;
        }

        public static List<string> StreamedIcao(string name, string title)
        {
            var parts = Regex.Split(name.ToLowerInvariant(), "[-_ .]+").Where(x => x != "").ToList();
            int i = parts.IndexOf("airport");
            if (i >= 0 && i + 1 < parts.Count && parts[i + 1].Length == 4 && parts[i + 1].All(char.IsLetterOrDigit) && char.IsLetter(parts[i + 1][0]))
                return new List<string> { parts[i + 1].ToUpperInvariant() };
            var outp = new List<string>();
            foreach (var t in Scanner.Tokens4(name).Concat(Scanner.Tokens4(title, true))) if (!outp.Contains(t)) outp.Add(t);
            return outp;
        }

        public static JArray ScanStreamed(string folder)
        {
            var outp = new JArray();
            string[] dirs;
            try { dirs = Directory.GetDirectories(folder); } catch (Exception) { return outp; }
            Array.Sort(dirs, StringComparer.OrdinalIgnoreCase);
            foreach (var d in dirs)
            {
                string name = Path.GetFileName(d);
                if (name.ToLowerInvariant().IndexOf("airport") < 0) continue;
                string title = "";
                try { title = JsonStore.Str(JObject.Parse(File.ReadAllText(Path.Combine(d, "manifest.json"), Encoding.UTF8))["title"]); } catch (Exception) { }
                var icao = StreamedIcao(name, title);
                if (icao.Count > 0) outp.Add(new JObject { ["name"] = name, ["title"] = title, ["icao"] = new JArray(icao), ["path"] = d });
            }
            return outp;
        }

        public JArray DupStreamed;   // scènes par défaut trouvées dans StreamedPackages (null = pas encore lues)
        public string DupTime = "";

        public string StreamedFolder()
        {
            string f = CfgS("streamed");
            if (f == "" || !Directory.Exists(f)) f = DetectStreamed(CfgS("community"));
            return f;
        }

        public void ScanStreamedNow()
        {
            string folder = StreamedFolder();
            if (folder == "") return;
            var res = ScanStreamed(folder);
            lock (Gate) { DupStreamed = res; DupTime = DateTime.Now.ToString("dd/MM/yyyy HH:mm:ss"); }
            PushMap();
        }

        // ---------------------------------------------------------------- carte des scènes (page /, données /data.json)
        public int MapVer;
        string mapJson = "{}";
        public string MapJson { get { return mapJson; } }

        static string MapCategory(string rel, AirportRec a)
        {
            if (rel.ToLowerInvariant().Contains("vfr") || rel.ToLowerInvariant().Contains("ulm") || a.Type == "heliport" || a.Type == "seaplane_base" || a.Type == "balloonport" || a.Type == "closed")
                return "vfr";
            return a.Type == "large_airport" ? "large" : a.Type == "medium_airport" ? "medium" : "small";
        }

        public void PushMap()
        {
            try
            {
                string js = MapSnapshot();
                if (js != mapJson) { mapJson = js; MapVer++; }
            }
            catch (Exception e) { Log(L("Carte : ", "Map: ") + e.Message); }
        }

        string MapSnapshot()
        {
            lock (Gate)
            {
                var db = AirportsDb ?? new Dictionary<string, AirportRec>();
                string lib = CfgS("library");
                var off = St["default_off"] as JObject ?? new JObject();
                var defaults = (DupStreamed ?? new JArray()).OfType<JObject>().ToList();
                var known = new HashSet<string>(defaults.Select(d => JsonStore.Str(d["name"])));
                foreach (var prop in off.Properties())
                    if (!known.Contains(prop.Name))
                    {
                        var ic = prop.Value["icao"] as JArray;
                        defaults.Add(new JObject { ["name"] = prop.Name, ["title"] = "", ["icao"] = ic != null && ic.Count > 0 ? ic : new JArray(StreamedIcao(prop.Name, "")) });
                    }
                var defByIcao = new Dictionary<string, List<JObject>>();
                foreach (var d in defaults)
                    foreach (var c in (d["icao"] as JArray ?? new JArray()).Select(x => JsonStore.Str(x)))
                    {
                        List<JObject> l;
                        if (!defByIcao.TryGetValue(c, out l)) { l = new List<JObject>(); defByIcao[c] = l; }
                        l.Add(d);
                    }
                var addonByIcao = new Dictionary<string, List<Tuple<Pkg, bool>>>();
                var pts = new JArray();
                var nopos = new JArray();
                foreach (var p in Packages)
                {
                    var codes = AirportIcaos(p);
                    if (codes.Count == 0) continue;
                    bool active = CommStatus(p) != "none" && CommStatus(p) != "?";
                    string rel = p.Group ?? "";
                    if (db.Count > 0 && codes.Any(c => !db.ContainsKey(c)))
                    {
                        var kn = codes.Where(db.ContainsKey).ToList();
                        if (kn.Count == 0)
                            kn = Regex.Matches((p.Name + " " + p.Title).ToUpperInvariant(), @"\b[A-Z0-9]{4}\b").Cast<Match>().Select(m => m.Value).Where(db.ContainsKey).Take(1).ToList();
                        if (kn.Count > 0) codes = kn.Distinct().ToList();
                    }
                    foreach (var c in codes)
                    {
                        List<Tuple<Pkg, bool>> l;
                        if (!addonByIcao.TryGetValue(c, out l)) { l = new List<Tuple<Pkg, bool>>(); addonByIcao[c] = l; }
                        l.Add(Tuple.Create(p, active));
                        AirportRec a;
                        if (!db.TryGetValue(c, out a)) { nopos.Add(new JObject { ["icao"] = c, ["pkg"] = p.Name, ["title"] = p.Title }); continue; }
                        string also = "";
                        List<JObject> dl;
                        if (defByIcao.TryGetValue(c, out dl))
                            also = string.Format(L("Scène par défaut MSFS {0}", "MSFS default scenery {0}"),
                                dl.All(d => off[JsonStore.Str(d["name"])] != null) ? L("désactivée", "disabled") : L("active", "active"));
                        pts.Add(new JObject { ["kind"] = "addon", ["cat"] = MapCategory(rel, a), ["icao"] = c, ["lat"] = a.Lat, ["lon"] = a.Lon, ["name"] = a.Name,
                            ["city"] = a.City, ["country"] = a.Country, ["pkg"] = p.Name, ["title"] = p.Title, ["folder"] = rel, ["active"] = active,
                            ["pinned"] = p.Pinned, ["also"] = also });
                    }
                }
                foreach (var d in defaults)
                    foreach (var c in (d["icao"] as JArray ?? new JArray()).Select(x => JsonStore.Str(x)))
                    {
                        AirportRec a;
                        if (!db.TryGetValue(c, out a)) continue;
                        string also = "";
                        List<Tuple<Pkg, bool>> al;
                        if (addonByIcao.TryGetValue(c, out al))
                            also = string.Join("; ", al.Select(x => string.Format("Add-on {0} ({1})", x.Item1.Title != "" ? x.Item1.Title : x.Item1.Name, x.Item2 ? L("actif", "active") : L("inactif", "inactive"))));
                        pts.Add(new JObject { ["kind"] = "default", ["cat"] = "default", ["icao"] = c, ["lat"] = a.Lat, ["lon"] = a.Lon, ["name"] = a.Name,
                            ["city"] = a.City, ["country"] = a.Country, ["pkg"] = JsonStore.Str(d["name"]), ["title"] = JsonStore.Str(d["title"]),
                            ["active"] = off[JsonStore.Str(d["name"])] == null, ["also"] = also });
                    }
                JToken route = null;
                var plan = Plan;
                if (plan != null)
                {
                    var rp = new JArray();
                    foreach (var ap in plan["airports"] as JArray ?? new JArray())
                    {
                        AirportRec a;
                        if (db.TryGetValue(JsonStore.Str(ap["icao"]), out a))
                            rp.Add(new JObject { ["icao"] = ap["icao"], ["role"] = ap["role"], ["primary"] = ap["primary"], ["lat"] = a.Lat, ["lon"] = a.Lon });
                    }
                    route = new JObject { ["name"] = (JsonStore.Str(plan["flight"]) + " " + JsonStore.Str(plan["route"])).Trim(), ["points"] = rp };
                }
                return new JObject { ["points"] = pts, ["nopos"] = nopos, ["route"] = route, ["dbReady"] = db.Count > 0 }.ToString(Formatting.None);
            }
        }

        // ---------------------------------------------------------------- relais (8765) et serveur des pages (47620…)
        public readonly RelayState Relay = new RelayState();
        MiniHttp relayServer, pageServer;
        CancellationTokenSource relayStop;
        public bool RelayPortBusy, RelayManualOff, RelayDllMissing;
        public Func<string, bool> CloseWebWindow = w => false;   // fourni par la fenêtre principale
        public Action<string> OpenUrl = u => { };

        public void InitRelay()
        {
            Relay.Log = m => Log(L("Relais : ", "Relay: ") + m);
            Relay.Fshub = new FshubFeed(() => CfgS("fshub_token"), () => CfgS("fshub_va"));
            Relay.PlanInfo = () => Plan;
            for (int i = 0; i < 3; i++)
            {
                if (RelayStart(true, i < 2)) return;
                Thread.Sleep(1500);
            }
        }

        public bool RelayRunning { get { return relayServer != null && relayServer.Running; } }

        public bool RelayStart(bool quiet, bool silentBusy)
        {
            if (RelayRunning) return true;
            Relay.SetConnected(false);
            var srv = new MiniHttp(RelayHandle);
            if (!srv.Start(8765))
            {
                if (!RelayPortBusy && !silentBusy)
                    Log(L("Relais : le port 8765 est déjà pris, sans doute par l'ancien relais (ou la version Python de Hangar FS 2024). Clique sur « ⏻ Fermer l'ancien relais » en bas à droite.",
                          "Relay: port 8765 is already taken, probably by the old relay (or the Python version of Hangar FS 2024). Click \"⏻ Close the old relay\" at the bottom right."));
                RelayPortBusy = true;
                LauncherChanged();
                return false;
            }
            RelayPortBusy = false;
            relayServer = srv;
            relayStop = new CancellationTokenSource();
            RelayDllMissing = false;
            string dll = RelayState.FindSimConnectDll(CfgS("simconnect_dir"), CfgS("launch_target"));
            if (dll != null && SimConnectClient.Load(dll))
            {
                var tok = relayStop.Token;
                new Thread(() => Relay.SimConnectLoop(dll, tok, () => SimOn)) { IsBackground = true, Name = "simconnect" }.Start();
            }
            else
            {
                RelayDllMissing = true;
                Log(L("Relais : SimConnect.dll introuvable. Le trafic IA est désactivé ; SimBrief et la météo fonctionnent. Indique son dossier dans Réglages (ligne SimConnect).",
                      "Relay: SimConnect.dll not found. AI traffic is disabled; SimBrief and weather work. Set its folder in Settings (SimConnect line)."));
            }
            if (!quiet) Log(L("Relais : démarré.", "Relay: started."));
            LauncherChanged();
            return true;
        }

        public void RelayStopNow(string reason)
        {
            if (!RelayRunning) return;
            if (relayStop != null) relayStop.Cancel();
            var srv = relayServer; relayServer = null;
            srv.Stop();
            Relay.SetConnected(false);
            Log(L("Relais : arrêté", "Relay: stopped") + reason + ".");
            LauncherChanged();
        }

        public void RelayToggle()
        {
            if (RelayRunning) { RelayManualOff = true; RelayStopNow(L(" (à ta demande)", " (at your request)")); }
            else if (RelayPortBusy) KillOldRelay();
            else { RelayManualOff = false; RelayStart(false, false); }
        }

        // programme qui occupe le port 8765 (ancien relais) : fermé puis relais redémarré
        public string KillOldRelay()
        {
            int pid = PidOnPort(8765);
            if (pid <= 0 || pid == Process.GetCurrentProcess().Id)
            {
                if (RelayStart(false, false)) return "";
                return L("Impossible de trouver le programme qui occupe le port 8765.", "Unable to find the program using port 8765.");
            }
            string name = "?";
            try { using (var p = Process.GetProcessById(pid)) name = p.ProcessName; } catch (Exception) { }
            try { using (var p = Process.GetProcessById(pid)) { p.Kill(); p.WaitForExit(5000); } }
            catch (Exception e) { Log(L("Relais : impossible de fermer l'ancien relais (", "Relay: unable to close the old relay (") + e.Message + ")."); return e.Message; }
            Log(L("Relais : ancien relais fermé (", "Relay: old relay closed (") + name + ").");
            RelayManualOff = false;
            Thread.Sleep(1200);
            RelayStart(false, false);
            return "";
        }

        static int PidOnPort(int port)
        {
            try
            {
                var psi = new ProcessStartInfo("netstat.exe", "-ano -p TCP") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true };
                using (var p = Process.Start(psi))
                {
                    string o = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(10000);
                    foreach (var line in o.Split('\n'))
                    {
                        var parts = line.Split(new[] { ' ', '\t', '\r' }, StringSplitOptions.RemoveEmptyEntries);
                        int pid;
                        if (parts.Length >= 5 && parts[1].EndsWith(":" + port) && (parts[2] == "0.0.0.0:0" || parts[2] == "[::]:0") && int.TryParse(parts[parts.Length - 1], out pid))
                            return pid;
                    }
                }
            }
            catch (Exception) { }
            return 0;
        }

        public string RelayText()
        {
            if (!RelayRunning) return RelayPortBusy ? L("Relais : port 8765 pris par l'ancien relais", "Relay: port 8765 taken by the old relay") : L("Relais : arrêté", "Relay: stopped");
            if (RelayDllMissing) return L("Relais : actif · trafic IA indisponible (SimConnect.dll)", "Relay: active · AI traffic unavailable (SimConnect.dll)");
            if (Relay.Connected)
            {
                int n = Relay.Count();
                return string.Format(L("Relais : MSFS connecté · {0} avion(s) IA", "Relay: MSFS connected · {0} AI aircraft"), n);
            }
            return L("Relais : actif · en attente de MSFS", "Relay: active · waiting for MSFS");
        }

        public string RelayButton()
        {
            return RelayRunning ? L("⏻  Arrêter le relais", "⏻  Stop the relay") : RelayPortBusy ? L("⏻  Fermer l'ancien relais", "⏻  Close the old relay") : L("⏻  Démarrer le relais", "⏻  Start the relay");
        }

        void RelayHandle(string path, string query, MiniHttp.Response r)
        {
            r.Cors = true;
            switch (path)
            {
                case "/traffic": r.Json(200, Relay.Snapshot()); break;
                case "/simbrief": RelayApi.SimBrief(query, r); break;
                case "/metar": RelayApi.Metar(query, r); break;
                case "/aeroway": RelayApi.Aeroway(query, r); break;
                case "/fshub-all": RelayApi.FshubAll(r); break;
                case "/fshub-flight": RelayApi.FshubFlight(query, r); break;
                case "/plan-current": RelayApi.PlanCurrent(Plan, r); break;
                case "/fshub": r.Json(200, Relay.Fshub != null ? Relay.Fshub.Snapshot() : new JObject { ["enabled"] = false, ["pilots"] = new JArray() }); break;
                default:
                    r.Text("Relais Avionics Dispatch (Hangar FS 2024) actif : /traffic, /simbrief, /metar, /aeroway, /fshub, /fshub-all, /fshub-flight", "text/plain; charset=utf-8");
                    break;
            }
        }

        // ---- pages web (carte, Plan & suivi de vol, tutoriel)
        static Dictionary<string, string> webRes;
        public static byte[] WebResource(string name)
        {
            var asm = Assembly.GetExecutingAssembly();
            if (webRes == null)
            {
                var d = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                foreach (var n in asm.GetManifestResourceNames()) d[n.Replace('\\', '/')] = n;
                webRes = d;
            }
            string real;
            if (!webRes.TryGetValue("web/" + name, out real)) return null;
            using (var st = asm.GetManifestResourceStream(real))
            using (var ms = new MemoryStream()) { st.CopyTo(ms); return ms.ToArray(); }
        }
        public static string WebText(string name) { var b = WebResource(name); return b == null ? "" : Encoding.UTF8.GetString(b); }

        public static JObject Titles() { try { return JObject.Parse(WebText("titles.json")); } catch (Exception) { return new JObject(); } }

        public int PagePort()
        {
            if (pageServer != null && pageServer.Running) return pageServer.Port;
            for (int port = 47620; port < 47630; port++)
            {
                var s = new MiniHttp(PageHandle);
                if (s.Start(port)) { pageServer = s; return port; }
            }
            var any = new MiniHttp(PageHandle);
            any.Start(0);
            pageServer = any;
            return any.Port;
        }

        void PageHandle(string path, string query, MiniHttp.Response r)
        {
            string lang = Lang;
            var q = MiniHttp.ParseQuery(query);
            byte[] b;
            switch (path)
            {
                case "/": case "/index.html":
                    {
                        string page = WebText("map_" + lang + ".html");
                        if (CfgB("colorblind", false)) { int i = page.IndexOf("const CB = false;"); if (i >= 0) page = page.Substring(0, i) + "const CB = true;" + page.Substring(i + 17); }
                        r.Text(page, "text/html; charset=utf-8");
                        return;
                    }
                case "/close":
                    {
                        string w; q.TryGetValue("w", out w);
                        bool ok = (w == "map" || w == "dispatch" || w == "tuto") && CloseWebWindow(w);
                        r.Text(ok ? "ok" : "no", "text/plain");
                        return;
                    }
                case "/version": r.Text(MapVer.ToString(), "text/plain"); return;
                case "/data.json": r.Text(mapJson ?? "{}", "application/json; charset=utf-8"); return;
                case "/tutorial": r.Text(WebText("tutorial_" + lang + ".html"), "text/html; charset=utf-8"); return;
                case "/dispatch":
                    {
                        string html = WebText("dispatch_" + lang + ".html");
                        string user = CfgS("simbrief_user");
                        string inj = user != "" ? "<script>try{if(!localStorage.getItem('avd_simbrief_user'))localStorage.setItem('avd_simbrief_user'," + JsonConvert.ToString(user) + ")}catch(e){}</script>" : "";
                        html = html.Replace("<!--HANGAR_USER-->", inj).Replace("<!--HANGAR_CB-->", CfgB("colorblind", false) ? WebText("dispatch_cb_" + lang + ".js") : "");
                        r.Text(html, "text/html; charset=utf-8");
                        return;
                    }
                case "/open":
                    {
                        string url; q.TryGetValue("url", out url);
                        if (url == null || !Regex.IsMatch(url, "^https?://", RegexOptions.IgnoreCase)) { r.Status = 400; r.Text("bad", "text/plain"); return; }
                        OpenUrl(url);
                        r.Text("ok", "text/plain");
                        return;
                    }
                case "/favicon.png": case "/favicon.ico":
                    r.ContentType = "image/png"; r.Body = WebResource("favicon.png"); return;
            }
            if (path.StartsWith("/tuto/") && path.EndsWith(".jpg") && (b = WebResource(path.Substring(1))) != null) { r.ContentType = "image/jpeg"; r.Body = b; return; }
            if ((path == "/logo.svg" || path == "/bg_map.svg" || path == "/bg_dispatch.svg" || path == "/bg_modal.svg") && (b = WebResource(path.Substring(1))) != null)
            { r.ContentType = "image/svg+xml"; r.Body = b; return; }
            if ((path == "/icon_map.png" || path == "/icon_dispatch.png") && (b = WebResource(path.Substring(1))) != null) { r.ContentType = "image/png"; r.Body = b; return; }
            r.Status = 404; r.Text("not found", "text/plain");
        }

        // ---------------------------------------------------------------- avion au parking (applications 🅿)
        double parkingSince = -1, userLostSince = -1;
        double[] parkingPos;
        bool parkingWarned;

        void CheckParking(bool running)
        {
            List<JObject> apps;
            lock (Gate) apps = (Cfg["launcher"] as JArray ?? new JArray()).OfType<JObject>()
                .Where(a => (a["enabled"] == null || a["enabled"].Type != JTokenType.Boolean || (bool)a["enabled"]) && JsonStore.Str(a["trigger"]) == "parking").ToList();
            Launcher.RelayConnected = Relay.Connected;
            if (!running) { parkingSince = -1; Launcher.ParkingFired = false; userLostSince = -1; parkingWarned = false; return; }
            if (apps.Count == 0 || !CfgB("launcher_auto", true)) return;
            if (!Relay.Connected)
            {
                if (!RelayRunning && !parkingWarned)
                {
                    parkingWarned = true;
                    Log(L("Démarrage auto : le relais est arrêté, l'avion au parking ne peut pas être détecté. Démarre-le avec le bouton ⏻ en bas à droite.",
                          "Auto launch: the relay is stopped, the aircraft at parking cannot be detected. Start it with the ⏻ button at the bottom right."));
                }
                return;
            }
            var user = Relay.User();
            double now = RelayState.Now();
            if (user == null)
            {
                parkingSince = -1;
                if (userLostSince < 0) userLostSince = now;
                else if (Launcher.ParkingFired && now - userLostSince >= 30)
                {
                    Launcher.ParkingFired = false;
                    Log(L("Démarrage auto : avion retiré (retour au menu) — détection du parking réarmée.", "Auto launch: aircraft removed (back to menu) — parking detection re-armed."));
                }
                return;
            }
            userLostSince = -1;
            if (Launcher.ParkingFired) return;
            if (!(bool)user["ground"] || Math.Abs((int)user["gs"]) > 2) { parkingSince = -1; return; }
            double lat = (double)user["lat"], lon = (double)user["lon"];
            bool moved = parkingPos == null || Math.Abs(lat - parkingPos[0]) > 0.002 || Math.Abs(lon - parkingPos[1]) > 0.002;
            if (parkingSince < 0 || moved) { parkingSince = now; parkingPos = new[] { lat, lon }; return; }
            if (now - parkingSince < 8) return;
            string where = "";
            var db = AirportsDb;
            if (db != null && db.Count > 0)
            {
                string code = Airports.Nearest(db, lat, lon, 4);
                if (CfgB("parking_need_airport", true) && code == null) return;   // au sol mais loin de tout aéroport (menu, hangar…)
                if (code != null) where = L(" à ", " at ") + code;
            }
            else if (db == null && File.Exists(Airports.FilePath)) Task.Run(() => LoadAirports(false));
            Launcher.ParkingFired = true;
            Launcher.Schedule("parking", where);
        }

        // ---------------------------------------------------------------- lancement de MSFS 2024
        public static string DetectMsfsLaunch()
        {
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            if (Directory.Exists(Path.Combine(local, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe"))) return "shell:AppsFolder\\Microsoft.Limitless_8wekyb3d8bbwe!App";
            if (Directory.Exists(Path.Combine(roaming, "Microsoft Flight Simulator 2024"))) return "steam://rungameid/2537590";
            return "";
        }

        public void LaunchMsfs()
        {
            if (SimOn || SimRunning()) throw new Exception(L("MSFS 2024 est déjà lancé.", "MSFS 2024 is already running."));
            string target = CfgS("msfs_launch");
            if (target == "")
            {
                target = DetectMsfsLaunch();
                if (target == "") throw new Exception(L("MSFS 2024 introuvable automatiquement. Indique son raccourci ou son programme dans l'onglet Réglages, ligne « Lancement de MSFS 2024 ».",
                                                        "MSFS 2024 not found automatically. Set its shortcut or program in the Settings tab, \"MSFS 2024 launch\" line."));
                lock (Gate) { Cfg["msfs_launch"] = target; SaveCfg(); }
            }
            if (target.StartsWith("shell:", StringComparison.OrdinalIgnoreCase)) Process.Start("explorer.exe", target);
            else Process.Start(new ProcessStartInfo(target) { UseShellExecute = true });
            Log(L("MSFS 2024 lancé depuis Hangar FS 2024.", "MSFS 2024 launched from Hangar FS 2024."));
            Status(L("MSFS 2024 démarre… le démarrage auto des applis et le relais suivront automatiquement.", "MSFS 2024 is starting… auto launch and the relay will follow automatically."));
        }
    }
}
