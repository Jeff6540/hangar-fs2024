// Logique de l'appli (bibliothèque, Community, vol SimBrief) — même fonctionnement que la 11.8 Python,
// avec les mêmes fichiers config.json / state.json.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    class Hangar
    {
        public static string Lang = "fr";
        public static string L(string fr, string en) { return Lang == "en" ? en : fr; }

        static readonly Dictionary<string, int> LinkRank = new Dictionary<string, int> {
            { "flight", 0 }, { "manual", 1 }, { "pinned", 2 } };

        public JObject Cfg;
        public JObject St;
        public List<Pkg> Packages = new List<Pkg>();
        public readonly object Gate = new object();

        public event Action<string> OnLog;
        public event Action<string> OnStatus;
        public event Action OnChanged;
        public event Action OnLauncher;
        public Launcher Launcher;
        public void LauncherChanged() { var h = OnLauncher; if (h != null) h(); }

        public bool SimOn;
        bool simWasRunning;
        bool skipNextExit;
        string libSig;
        bool scanning;
        JObject undo;   // dernière action Activer / Retirer, pour le bouton « ↶ Annuler »

        static JObject DefaultConfig()
        {
            return new JObject
            {
                ["library"] = "", ["community"] = "", ["simbrief_user"] = "",
                ["sim_exe"] = "FlightSimulator2024.exe", ["streamed"] = "", ["dispatch_file"] = "",
                ["include_alternates"] = true, ["auto_unlink"] = true, ["flight_only"] = false,
                ["relay_auto"] = true, ["launcher_auto"] = true, ["parking_need_airport"] = true,
                ["msfs_launch"] = "", ["launcher"] = new JArray(), ["overrides"] = new JObject(),
                ["screen"] = "auto", ["screen_main"] = true, ["screen_map"] = true, ["screen_dispatch"] = true,
                ["fshub_token"] = "", ["lang"] = "fr",
            };
        }

        static JObject DefaultState()
        {
            return new JObject { ["links"] = new JObject(), ["flight"] = null, ["plan"] = null };
        }

        public Hangar()
        {
            Cfg = JsonStore.Load(AppInfo.ConfigFile, DefaultConfig());
            St = JsonStore.Load(AppInfo.StateFile, DefaultState());
            if (!(St["links"] is JObject)) St["links"] = new JObject();
            if (!(Cfg["overrides"] is JObject)) Cfg["overrides"] = new JObject();
            if (CfgS("community") == "") Cfg["community"] = Scanner.DetectCommunity();
            Lang = CfgS("lang") == "en" ? "en" : "fr";
            Launcher = new Launcher(this);
        }

        // ---------------------------------------------------------------- petits outils
        public string CfgS(string key) { return JsonStore.Str(Cfg[key]); }
        public bool CfgB(string key, bool def)
        {
            var t = Cfg[key];
            if (t == null || t.Type != JTokenType.Boolean) return def;
            return (bool)t;
        }
        JObject LinksObj { get { return (JObject)St["links"]; } }
        JObject Overrides { get { return (JObject)Cfg["overrides"]; } }
        public JObject Plan { get { return St["plan"] as JObject; } }
        public JObject Flight { get { return St["flight"] as JObject; } }

        public void Log(string msg) { var h = OnLog; if (h != null) h(msg); }
        public void Status(string msg) { var h = OnStatus; if (h != null) h(msg); }
        void Changed() { var h = OnChanged; if (h != null) h(); }

        public void SaveCfg() { JsonStore.Save(AppInfo.ConfigFile, Cfg); }
        public void SaveSt() { JsonStore.Save(AppInfo.StateFile, St); }

        public bool SimRunning()
        {
            string exe = CfgS("sim_exe");
            if (exe == "") return false;
            try { return Process.GetProcessesByName(Path.GetFileNameWithoutExtension(exe)).Length > 0; }
            catch (Exception) { return false; }
        }

        void CheckUnlocked()
        {
            if (SimRunning())
                throw new Exception(L("Flight Simulator est ouvert.\n\nFerme-le avant de modifier tes add-ons : il ne lit le dossier Community qu'au démarrage, et changer les liens pendant qu'il tourne peut le perturber.",
                                      "Flight Simulator is running.\n\nClose it before changing your add-ons: it only reads the Community folder at startup, and changing links while it runs can disturb it."));
        }

        string Community
        {
            get
            {
                string c = CfgS("community");
                if (c == "" || !Directory.Exists(c))
                    throw new Exception(L("Dossier Community introuvable. Vérifie l'onglet Réglages.",
                                          "Community folder not found. Check the Settings tab."));
                return Scanner.NormDir(c);
            }
        }

        public string LinkPath(Pkg p) { return Path.Combine(Scanner.NormDir(CfgS("community")), p.Name); }

        Pkg ByPath(string path)
        {
            foreach (var p in Packages)
                if (Scanner.SamePath(p.FullPath, path)) return p;
            return null;
        }

        static string Base(string path) { return Path.GetFileName(path); }

        // ---------------------------------------------------------------- analyse de la bibliothèque
        public void Rescan()
        {
            string lib = CfgS("library");
            if (lib == "" || !Directory.Exists(lib))
            {
                lock (Gate) Packages = new List<Pkg>();
                Status(L("Indique le dossier de ta bibliothèque dans l'onglet Réglages.", "Set your library folder in the Settings tab."));
                Changed();
                return;
            }
            scanning = true;
            Status(L("Analyse de la bibliothèque…", "Scanning the library…"));
            try
            {
                var res = Scanner.FindPackages(lib).Select(p => Scanner.ScanPackage(p, lib)).ToList();
                string sig = Scanner.LibSignature(lib);
                lock (Gate)
                {
                    foreach (var p in res) ApplyOverride(p);
                    res.Sort((a, b) => string.Compare(a.Name, b.Name, StringComparison.OrdinalIgnoreCase));
                    Packages = res;
                    libSig = sig;
                }
                int nApt = res.Count(p => p.Icao.Count > 0);
                Status(string.Format(L("{0} add-ons trouvés, dont {1} scènes d'aéroport reconnues.",
                                       "{0} add-ons found, including {1} recognised airport sceneries."), res.Count, nApt));
            }
            finally { scanning = false; }
            Changed();
        }

        void ApplyOverride(Pkg p)
        {
            var ov = Overrides[p.FullPath] as JObject;
            p.IcaoAuto = new List<string>(p.Icao);
            if (ov != null && ov["icao"] is JArray)
                p.Icao = ((JArray)ov["icao"]).Select(x => JsonStore.Str(x)).Where(x => x != "").ToList();
            p.Pinned = ov != null && ov["pinned"] != null && ov["pinned"].Type == JTokenType.Boolean && (bool)ov["pinned"];
        }

        JObject OverrideFor(string path)
        {
            var ov = Overrides[path] as JObject;
            if (ov == null) { ov = new JObject(); Overrides[path] = ov; }
            return ov;
        }

        // Codes OACI d'un add-on s'il s'agit bien d'une scène d'aéroport (pas un pack saisons, maillage…)
        public List<string> AirportIcaos(Pkg p)
        {
            if (!(p.Type == "SCENERY" || p.Type == "")) return new List<string>();
            var ov = Overrides[p.FullPath] as JObject;
            if (ov != null && ov["icao"] != null) return new List<string>(p.Icao);
            string text = (p.Name + " " + p.Title).ToLowerInvariant();
            if (p.Icao.Count > 6 && !Scanner.AirportWords.Any(w => text.Contains(w))) return new List<string>();
            if (Scanner.IsDecorPack(text)) return new List<string>();
            return new List<string>(p.Icao);
        }

        public List<Pkg> PackagesFor(IEnumerable<string> icaos)
        {
            var s = new HashSet<string>(icaos);
            return Packages.Where(p => AirportIcaos(p).Any(s.Contains)).ToList();
        }

        // état dans Community : none / flight / linked / ext / real / ?
        public string CommStatus(Pkg p)
        {
            if (CfgS("community") == "") return "?";
            string link = LinkPath(p);
            if (!Links.Lexists(link)) return "none";
            var v = LinksObj[link] as JObject;
            if (v != null) return JsonStore.Str(v["kind"]) == "flight" ? "flight" : "linked";
            if (Links.IsLink(link)) return "ext";
            return "real";
        }

        // ---------------------------------------------------------------- liens
        string DoLink(Pkg p, string kind)
        {
            if (!Directory.Exists(p.FullPath))
                throw new IOException(L("dossier introuvable dans la bibliothèque (supprimé ou déplacé)",
                                        "folder not found in the library (deleted or moved)"));
            string link = LinkPath(p);
            if (Links.Lexists(link))
            {
                var v = LinksObj[link] as JObject;
                bool ours = v != null;
                if (Links.IsLink(link) && Scanner.SamePath(Links.LinkTarget(link), p.FullPath))
                {
                    if (ours)
                    {
                        string cur = JsonStore.Str(v["kind"]);
                        int a, b;
                        LinkRank.TryGetValue(kind, out a);
                        LinkRank.TryGetValue(cur, out b);
                        if (a > b) v["kind"] = kind;
                        return L("déjà lié", "already linked");
                    }
                    return L("déjà présent (lien externe, non géré)", "already present (external link, not managed)");
                }
                if (ours && Links.IsLink(link))
                    Unlink(link);   // notre ancien lien vers un autre emplacement : on le refait
                else
                    throw new IOException(L("un dossier du même nom existe déjà dans Community",
                                            "a folder with the same name already exists in Community"));
            }
            Links.MakeLink(p.FullPath, link);
            LinksObj[link] = new JObject { ["target"] = p.FullPath, ["kind"] = kind };
            return L("lié", "linked");
        }

        void Unlink(string link)
        {
            Links.RemoveLink(link);
            LinksObj.Remove(link);
        }

        int SyncPinned()
        {
            if (Packages.Count == 0) return 0;
            int errors = 0;
            var suspended = new HashSet<string>(
                (St["pin_suspended"] as JArray ?? new JArray()).Select(x => JsonStore.Str(x)));
            var pinned = new Dictionary<string, Pkg>(StringComparer.OrdinalIgnoreCase);
            foreach (var p in Packages)
                if (p.Pinned && !suspended.Contains(p.FullPath)) pinned[LinkPath(p)] = p;
            var fl = Flight;
            var flightLinks = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (fl != null)
                foreach (var p in PackagesFor(IcaoList(fl["icaos"]))) flightLinks.Add(LinkPath(p));
            foreach (var prop in LinksObj.Properties().ToList())
            {
                var v = prop.Value as JObject;
                if (v == null) continue;
                if (JsonStore.Str(v["kind"]) == "pinned" && !pinned.ContainsKey(prop.Name))
                {
                    v["kind"] = flightLinks.Contains(prop.Name) ? "flight" : "manual";
                    Log(L("Plus protégé (reste dans Community) : ", "No longer protected (stays in Community): ") + Base(prop.Name));
                }
            }
            foreach (var kv in pinned)
            {
                try
                {
                    if (DoLink(kv.Value, "pinned") == L("lié", "linked"))
                        Log(L("Protégé : ", "Protected: ") + kv.Value.Name + L(" — lié", " — linked"));
                }
                catch (Exception e)
                {
                    errors++;
                    Log(string.Format(L("Erreur pour {0} : {1}", "Error for {0}: {1}"), kv.Value.Name, e.Message));
                }
            }
            return errors;
        }

        static List<string> IcaoList(JToken t)
        {
            var a = t as JArray;
            return a == null ? new List<string>() : a.Select(x => JsonStore.Str(x)).ToList();
        }

        public JObject Activate(List<string> paths)
        {
            CheckUnlocked();
            string comm = Community;
            int ok = 0, errors = 0;
            var done = new JArray();
            lock (Gate)
            {
                foreach (var path in paths)
                {
                    var p = ByPath(path);
                    if (p == null) continue;
                    try
                    {
                        string r = DoLink(p, "manual");
                        ok++;
                        if (r == L("lié", "linked")) done.Add(new JObject { ["path"] = p.FullPath });
                        Log(p.Name + " — " + r);
                    }
                    catch (Exception e)
                    {
                        errors++;
                        Log(string.Format(L("Erreur pour {0} : {1}", "Error for {0}: {1}"), p.Name, e.Message));
                    }
                }
                SaveSt();
                if (done.Count > 0) undo = new JObject { ["kind"] = "activate", ["items"] = done };
            }
            string msg = string.Format(L("{0} add-on(s) activé(s) dans Community.", "{0} add-on(s) activated in Community."), ok);
            if (errors > 0) msg += string.Format(L(" {0} erreur(s) — voir le journal.", " {0} error(s) — see the log."), errors);
            Status(msg);
            Changed();
            return new JObject { ["ok"] = ok, ["errors"] = errors };
        }

        public JObject Remove(List<string> paths)
        {
            CheckUnlocked();
            string comm = Community;
            int removed = 0, skipped = 0, errors = 0;
            var gone = new JArray();
            lock (Gate)
            {
                foreach (var path in paths)
                {
                    var p = ByPath(path);
                    if (p == null) continue;
                    string link = LinkPath(p);
                    if (!Links.Lexists(link)) continue;
                    try
                    {
                        if (!Links.IsLink(link))
                        {
                            skipped++;
                            Log(L("Ignoré (vraie copie, pas un lien) : ", "Skipped (real copy, not a link): ") + p.Name);
                            continue;
                        }
                        Unlink(link);
                        gone.Add(new JObject { ["path"] = p.FullPath, ["pinned"] = p.Pinned });
                        if (p.Pinned)
                        {
                            p.Pinned = false;
                            OverrideFor(p.FullPath)["pinned"] = false;
                        }
                        removed++;
                        Log(L("Retiré : ", "Removed: ") + p.Name);
                    }
                    catch (Exception e)
                    {
                        errors++;
                        Log(string.Format(L("Erreur en retirant {0} : {1}", "Error removing {0}: {1}"), p.Name, e.Message));
                    }
                }
                SaveCfg();
                SaveSt();
                if (gone.Count > 0) undo = new JObject { ["kind"] = "remove", ["items"] = gone };
            }
            string msg = string.Format(L("{0} add-on(s) retiré(s) de Community.", "{0} add-on(s) removed from Community."), removed);
            if (skipped > 0) msg += string.Format(L(" {0} vraie(s) copie(s) ignorée(s), à déplacer à la main.", " {0} real copy(ies) skipped, to move by hand."), skipped);
            if (errors > 0) msg += string.Format(L(" {0} erreur(s) — voir le journal.", " {0} error(s) — see the log."), errors);
            Status(msg);
            Changed();
            return new JObject { ["removed"] = removed };
        }

        public void SetPinned(List<string> paths, bool on)
        {
            CheckUnlocked();
            lock (Gate)
            {
                foreach (var path in paths)
                {
                    var p = ByPath(path);
                    if (p == null) continue;
                    p.Pinned = on;
                    OverrideFor(p.FullPath)["pinned"] = on;
                    Log((on ? L("★ Protégé : ", "★ Protected: ") : L("Protection retirée : ", "Protection removed: ")) + p.Name);
                }
                SaveCfg();
                if (CfgS("community") != "" && Directory.Exists(CfgS("community"))) SyncPinned();
                SaveSt();
            }
            Changed();
        }

        // codes vides = retour à la détection automatique
        public void SetIcao(string path, List<string> codes)
        {
            lock (Gate)
            {
                var p = ByPath(path);
                if (p == null) return;
                var clean = codes.Select(c => c.Trim().ToUpperInvariant()).Where(c => c.Length == 4).Distinct().ToList();
                var ov = OverrideFor(p.FullPath);
                if (clean.Count == 0)
                {
                    ov.Remove("icao");
                    p.Icao = new List<string>(p.IcaoAuto);
                }
                else
                {
                    ov["icao"] = new JArray(clean);
                    p.Icao = clean;
                }
                if (!ov.HasValues) Overrides.Remove(p.FullPath);
                SaveCfg();
            }
            Changed();
        }

        public JObject UndoInfo()
        {
            if (undo == null) return null;
            return new JObject { ["kind"] = undo["kind"], ["n"] = ((JArray)undo["items"]).Count };
        }

        public void Undo()
        {
            CheckUnlocked();
            var u = undo;
            if (u == null) { Status(L("Rien à annuler.", "Nothing to undo.")); return; }
            bool act = JsonStore.Str(u["kind"]) == "activate";
            int ok = 0, errors = 0;
            lock (Gate)
            {
                foreach (var it in (JArray)u["items"])
                {
                    var p = ByPath(JsonStore.Str(it["path"]));
                    if (p == null) { errors++; continue; }
                    try
                    {
                        if (act)
                        {
                            string link = LinkPath(p);
                            if (LinksObj[link] != null && Links.IsLink(link)) { Unlink(link); ok++; }
                        }
                        else
                        {
                            bool pin = it["pinned"] != null && (bool)it["pinned"];
                            if (pin) { p.Pinned = true; OverrideFor(p.FullPath)["pinned"] = true; }
                            DoLink(p, pin ? "pinned" : "manual");
                            ok++;
                        }
                    }
                    catch (Exception e)
                    {
                        errors++;
                        Log(string.Format(L("Annulation impossible pour {0} : {1}", "Undo failed for {0}: {1}"), p.Name, e.Message));
                    }
                }
                undo = null;
                SaveCfg();
                SaveSt();
            }
            string msg = act ? string.Format(L("Activation annulée : {0} add-on(s) retiré(s).", "Activation undone: {0} add-on(s) removed."), ok)
                             : string.Format(L("Retrait annulé : {0} add-on(s) remis dans Community.", "Removal undone: {0} add-on(s) put back in Community."), ok);
            if (errors > 0) msg += string.Format(L(" {0} erreur(s) — voir le journal.", " {0} error(s) — see the log."), errors);
            Log(msg);
            Status(msg);
            Changed();
        }

        // taille totale de Community (liens suivis), calculée en arrière-plan
        public static long FolderSize(IEnumerable<string> tops)
        {
            long total = 0;
            foreach (var top in tops)
            {
                try
                {
                    if (!Directory.Exists(top)) continue;
                    var stack = new Stack<string>();
                    stack.Push(top);
                    while (stack.Count > 0)
                    {
                        string d = stack.Pop();
                        try
                        {
                            foreach (var f in new DirectoryInfo(d).EnumerateFiles())
                                try { total += f.Length; } catch (Exception) { }
                            foreach (var sub in Directory.EnumerateDirectories(d)) stack.Push(sub);
                        }
                        catch (Exception) { }
                    }
                }
                catch (Exception) { }
            }
            return total;
        }

        public static string FmtSize(double n)
        {
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            string to = L("To", "TB"), go = L("Go", "GB"), mo = L("Mo", "MB"), ko = L("Ko", "KB");
            string r;
            if (n >= 1e12) r = (n / 1e12).ToString("0.00", inv) + " " + to;
            else if (n >= 1e9) r = (n / 1e9).ToString("0.00", inv) + " " + go;
            else if (n >= 1e6) r = (n / 1e6).ToString("0.00", inv) + " " + mo;
            else r = (n / 1e3).ToString("0", inv) + " " + ko;
            return Lang == "en" ? r : r.Replace(".", ",");
        }

        public string FreeSpace()
        {
            try
            {
                string lib = CfgS("library");
                if (lib == "" || !Directory.Exists(lib)) return "";
                var d = new DriveInfo(Path.GetPathRoot(Path.GetFullPath(lib)));
                return ((double)d.AvailableFreeSpace / 1e9).ToString("0", System.Globalization.CultureInfo.InvariantCulture) + " " + L("Go", "GB");
            }
            catch (Exception) { return ""; }
        }

        // ---------------------------------------------------------------- volet Community
        public JArray CommunityList()
        {
            var arr = new JArray();
            string comm = CfgS("community");
            if (comm == "" || !Directory.Exists(comm)) return arr;
            string lib = CfgS("library");
            string[] entries;
            try { entries = Directory.GetDirectories(comm); }
            catch (Exception) { return arr; }
            Array.Sort(entries, StringComparer.OrdinalIgnoreCase);
            var defOff = St["default_off"] as JObject;
            foreach (var raw in entries)
            {
                string path = Path.Combine(Scanner.NormDir(comm), Path.GetFileName(raw));
                bool link = Links.IsLink(path);
                string cat, label, target = link ? Links.LinkTarget(path) : "";
                var v = LinksObj[path] as JObject;
                if (!link && defOff != null && defOff[Path.GetFileName(path)] != null) { cat = "defoff"; label = L("Défaut MSFS désactivé", "MSFS default disabled"); }
                else if (link && !Links.TargetExists(path)) { cat = "broken"; label = L("Lien cassé", "Broken link"); }
                else if (!link) { cat = "real"; label = L("Dossier réel", "Real folder"); }
                else if (v != null)
                {
                    cat = "ours";
                    string k = JsonStore.Str(v["kind"]);
                    label = k == "flight" ? L("Lien (vol)", "Link (flight)") : k == "pinned" ? L("★ Protégé", "★ Protected") : L("Lien", "Link");
                }
                else if (lib != "" && target != "" && Scanner.Inside(target, lib)) { cat = "ext"; label = L("Lien externe", "External link"); }
                else { cat = "off"; label = L("Hors bibliothèque", "Outside library"); }
                string title = "", version = "", creator = "";
                if (cat != "broken")
                {
                    try
                    {
                        var m = JObject.Parse(File.ReadAllText(Path.Combine(path, "manifest.json"), System.Text.Encoding.UTF8));
                        title = JsonStore.Str(m["title"]);
                        version = JsonStore.Str(m["package_version"]).Trim();
                        creator = JsonStore.Str(m["creator"]);
                    }
                    catch (Exception) { }
                }
                arr.Add(new JObject { ["name"] = Path.GetFileName(path), ["path"] = path, ["cat"] = cat,
                    ["label"] = label, ["target"] = target, ["link"] = link, ["title"] = title, ["version"] = version, ["creator"] = creator });
            }
            return arr;
        }

        // retire des liens de Community (jamais un vrai dossier)
        public void RemoveCommunityLinks(List<string> linkPaths)
        {
            CheckUnlocked();
            int n = 0;
            lock (Gate)
            {
                foreach (var link in linkPaths)
                {
                    try
                    {
                        if (!Links.IsLink(link))
                        {
                            Log(L("Ignoré (vrai dossier, jamais supprimé) : ", "Skipped (real folder, never deleted): ") + Base(link));
                            continue;
                        }
                        Unlink(link);
                        n++;
                        Log(L("Lien retiré : ", "Link removed: ") + Base(link));
                    }
                    catch (Exception e)
                    {
                        Log(string.Format(L("Erreur en retirant {0} : {1}", "Error removing {0}: {1}"), Base(link), e.Message));
                    }
                }
                SaveSt();
            }
            Status(string.Format(L("{0} lien(s) retiré(s) de Community.", "{0} link(s) removed from Community."), n));
            Changed();
        }

        // ---------------------------------------------------------------- vol SimBrief
        public void FetchPlan(string user)
        {
            lock (Gate)
            {
                Cfg["simbrief_user"] = (user ?? "").Trim();
                SaveCfg();
            }
            Status(L("Récupération du plan SimBrief…", "Fetching the SimBrief plan…"));
            JObject res;
            try { res = SimBrief.Fetch(user); }
            catch (Exception)
            {
                Status(L("Échec de la récupération SimBrief.", "SimBrief fetch failed."));
                throw;
            }
            res["fetched"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            lock (Gate)
            {
                St["plan"] = res;
                SaveSt();
            }
            Status(L("Plan de vol chargé.", "Flight plan loaded."));
            Log(L("Plan chargé : ", "Plan loaded: ") + JsonStore.Str(res["route"]) + " (" +
                string.Join(", ", ((JArray)res["airports"]).Select(a => JsonStore.Str(a["icao"]))) + ")");
            Changed();
        }

        public List<string> ActiveIcaos()
        {
            var plan = Plan;
            if (plan == null) return new List<string>();
            bool alt = CfgB("include_alternates", true);
            return (plan["airports"] as JArray ?? new JArray())
                .Where(a => (a["primary"] != null && (bool)a["primary"]) || alt)
                .Select(a => JsonStore.Str(a["icao"])).ToList();
        }

        public JObject FlightView()
        {
            var o = new JObject();
            var plan = Plan;
            bool alt = CfgB("include_alternates", true);
            if (plan != null)
            {
                var rows = new JArray();
                foreach (var a in plan["airports"] as JArray ?? new JArray())
                {
                    bool primary = a["primary"] != null && (bool)a["primary"];
                    var pk = PackagesFor(new[] { JsonStore.Str(a["icao"]) });
                    rows.Add(new JObject { ["role"] = JsonStore.Str(a["role"]), ["icao"] = JsonStore.Str(a["icao"]),
                        ["name"] = JsonStore.Str(a["name"]), ["used"] = primary || alt,
                        ["scenes"] = new JArray(pk.Select(x => x.Title != "" ? x.Title : x.Name)) });
                }
                o["plan"] = new JObject { ["route"] = plan["route"], ["flight"] = plan["flight"],
                    ["aircraft"] = plan["aircraft"], ["airports"] = rows };
            }
            var fl = Flight;
            int n = LinksObj.Properties().Count(pr => pr.Value is JObject && JsonStore.Str(pr.Value["kind"]) == "flight");
            if (fl != null)
            {
                int m = PackagesFor(IcaoList(fl["icaos"])).Count(p => LinksObj[LinkPath(p)] != null);
                if (m > 0) n = m;
                o["flight"] = new JObject { ["route"] = fl["route"], ["scenes"] = n };
            }
            o["parked"] = (St["parked"] as JArray ?? new JArray()).Count;
            return o;
        }

        // 1er appel sans choix : renvoie les aéroports qui ont plusieurs scènes ; 2e appel avec les choix
        public JObject PrepareFlight(JObject choices, bool force)
        {
            CheckUnlocked();
            var plan = Plan;
            if (plan == null) throw new Exception(L("Récupère d'abord ton plan de vol SimBrief.", "Fetch your SimBrief flight plan first."));
            string comm = Community;
            lock (Gate)
            {
                if (Packages.Count == 0)
                    throw new Exception(L("Aucun add-on dans la bibliothèque (ou analyse en cours). Vérifie l'onglet Réglages.",
                                          "No add-on in the library (or scan in progress). Check the Settings tab."));
                var icaos = ActiveIcaos();
                var wanted = PackagesFor(icaos);
                var memo = Cfg["scenery_choice"] as JObject;
                if (memo == null) { memo = new JObject(); Cfg["scenery_choice"] = memo; }

                // plusieurs scènes pour un même aéroport : on demande laquelle activer
                var multi = new List<KeyValuePair<string, List<Pkg>>>();
                foreach (var icao in icaos)
                {
                    var cands = wanted.Where(p => AirportIcaos(p).Contains(icao)).ToList();
                    if (cands.Count > 1) multi.Add(new KeyValuePair<string, List<Pkg>>(icao, cands));
                }
                if (multi.Count > 0 && choices == null)
                {
                    var names = (plan["airports"] as JArray ?? new JArray()).ToDictionary(
                        a => JsonStore.Str(a["icao"]), a => JsonStore.Str(a["name"]));
                    var need = new JArray();
                    foreach (var kv in multi)
                    {
                        string def = JsonStore.Str(memo[kv.Key]);
                        if (!kv.Value.Any(c => c.FullPath == def)) def = kv.Value[0].FullPath;
                        string nm;
                        names.TryGetValue(kv.Key, out nm);
                        need.Add(new JObject { ["icao"] = kv.Key, ["name"] = nm ?? "", ["default"] = def,
                            ["options"] = new JArray(kv.Value.Select(c => new JObject {
                                ["path"] = c.FullPath, ["title"] = c.Title != "" ? c.Title : c.Name, ["name"] = c.Name,
                                ["pinned"] = c.Pinned, ["active"] = CommStatus(c) != "none" && CommStatus(c) != "?" })) });
                    }
                    return new JObject { ["needChoice"] = need };
                }
                var setAside = new List<Pkg>();
                if (multi.Count > 0)
                {
                    var drop = new HashSet<string>();
                    var chosenPaths = new HashSet<string>();
                    foreach (var kv in multi)
                    {
                        string chosen = JsonStore.Str(choices[kv.Key]);
                        if (chosen == "") chosen = kv.Value[0].FullPath;
                        memo[kv.Key] = chosen;
                        chosenPaths.Add(chosen);
                        foreach (var c in kv.Value) if (c.FullPath != chosen) drop.Add(c.FullPath);
                    }
                    drop.ExceptWith(chosenPaths);
                    foreach (var p in wanted)
                        if (drop.Contains(p.FullPath) && !p.Pinned)
                        {
                            setAside.Add(p);
                            Log(string.Format(L("{0} : scène non choisie pour ce vol — {1}", "{0}: scenery not chosen for this flight — {1}"),
                                string.Join(", ", AirportIcaos(p).Where(icaos.Contains)), p.Name));
                        }
                    wanted = wanted.Where(p => !drop.Contains(p.FullPath)).ToList();
                    SaveCfg();
                }

                skipNextExit = false;
                var wantedLinks = new HashSet<string>(wanted.Select(LinkPath), StringComparer.OrdinalIgnoreCase);
                int errors = 0;
                if (setAside.Count > 0)
                    errors += ParkLinks(setAside, L("Mise de côté (autre scène choisie pour ce vol)", "Set aside (another scenery chosen for this flight)"));
                foreach (var prop in LinksObj.Properties().ToList())
                {
                    var v = prop.Value as JObject;
                    if (v != null && JsonStore.Str(v["kind"]) == "flight" && !wantedLinks.Contains(prop.Name))
                    {
                        try
                        {
                            Unlink(prop.Name);
                            Log(L("Retiré (vol précédent) : ", "Removed (previous flight): ") + Base(prop.Name));
                        }
                        catch (Exception e)
                        {
                            errors++;
                            Log(string.Format(L("Erreur en retirant {0} : {1}", "Error removing {0}: {1}"), Base(prop.Name), e.Message));
                        }
                    }
                }
                St["flight"] = new JObject { ["route"] = plan["route"], ["icaos"] = new JArray(icaos) };
                undo = null;
                foreach (var p in wanted)
                {
                    try
                    {
                        string r = DoLink(p, "flight");
                        string codes = string.Join(", ", icaos.Where(i => p.Icao.Contains(i)));
                        Log(codes + " : " + p.Name + " — " + r);
                    }
                    catch (Exception e)
                    {
                        errors++;
                        Log(string.Format(L("Erreur pour {0} : {1}", "Error for {0}: {1}"), p.Name, e.Message));
                    }
                }
                errors += SyncPinned();
                var missing = icaos.Where(i => PackagesFor(new[] { i }).Count == 0).ToList();
                if (missing.Count > 0)
                    Log(L("Sans scène add-on (scène par défaut) : ", "No add-on scenery (default scenery): ") + string.Join(", ", missing));
                SaveSt();
                Status(errors == 0 ? L("Vol prêt : tu peux lancer le simulateur.", "Flight ready: you can start the simulator.")
                                   : string.Format(L("Vol préparé avec {0} erreur(s) — voir le journal.", "Flight prepared with {0} error(s) — see the log."), errors));
            }
            Changed();
            return new JObject { ["done"] = true };
        }

        int ParkLinks(List<Pkg> packages, string why)
        {
            var parked = St["parked"] as JArray;
            if (parked == null) { parked = new JArray(); St["parked"] = parked; }
            var known = new HashSet<string>(parked.Select(e => JsonStore.Str(e["link"])));
            int errors = 0;
            foreach (var p in packages)
            {
                string link = LinkPath(p);
                var v = LinksObj[link] as JObject;
                if (v == null || JsonStore.Str(v["kind"]) != "manual") continue;
                string target = JsonStore.Str(v["target"]);
                try { Unlink(link); }
                catch (Exception e)
                {
                    errors++;
                    Log(string.Format(L("Erreur en mettant de côté {0} : {1}", "Error setting aside {0}: {1}"), Base(link), e.Message));
                    continue;
                }
                if (known.Add(link)) parked.Add(new JObject { ["link"] = link, ["target"] = target });
                Log(why + " : " + p.Name);
            }
            return errors;
        }

        int RestoreParked()
        {
            var parked = St["parked"] as JArray;
            if (parked == null || parked.Count == 0) return 0;
            if (SimRunning())
            {
                Log(string.Format(L("Simulateur ouvert : les {0} scènes mises de côté seront remises après sa fermeture.",
                                    "Simulator running: the {0} sceneries set aside will be put back after it closes."), parked.Count));
                return 0;
            }
            int back = 0, errors = 0;
            var keep = new JArray();
            foreach (var e in parked)
            {
                var p = ByPath(JsonStore.Str(e["target"]));
                if (p == null)
                {
                    if (Packages.Count == 0) keep.Add(e);
                    else
                    {
                        errors++;
                        Log(L("Introuvable dans la bibliothèque, non remis : ", "Not found in the library, not put back: ") + Base(JsonStore.Str(e["link"])));
                    }
                    continue;
                }
                try { DoLink(p, "manual"); back++; }
                catch (Exception ex)
                {
                    errors++;
                    Log(string.Format(L("Erreur en remettant {0} : {1}", "Error putting back {0}: {1}"), p.Name, ex.Message));
                }
            }
            St["parked"] = keep;
            if (back > 0)
                Log(string.Format(L("Remis dans Community : {0} scène(s) mise(s) de côté pour le vol", "Put back in Community: {0} scenery(ies) set aside for the flight"), back));
            return errors;
        }

        public void EndFlight(bool auto)
        {
            if (!auto) CheckUnlocked();
            lock (Gate)
            {
                var links = LinksObj.Properties().Where(pr => pr.Value is JObject && JsonStore.Str(pr.Value["kind"]) == "flight")
                    .Select(pr => pr.Name).ToList();
                var parked = St["parked"] as JArray;
                if (!auto && Flight == null && links.Count == 0 && (parked == null || parked.Count == 0) && Plan == null)
                {
                    Status(L("Aucun vol actif.", "No active flight."));
                    return;
                }
                int errors = 0;
                foreach (var link in links)
                {
                    try
                    {
                        Unlink(link);
                        Log(L("Retiré : ", "Removed: ") + Base(link));
                    }
                    catch (Exception e)
                    {
                        errors++;
                        Log(string.Format(L("Erreur en retirant {0} : {1}", "Error removing {0}: {1}"), Base(link), e.Message));
                    }
                }
                errors += RestoreParked();
                undo = null;
                St["flight"] = null;
                if (Plan != null) Log(L("Plan de vol effacé : ", "Flight plan cleared: ") + JsonStore.Str(Plan["route"]));
                St["plan"] = null;
                SaveSt();
                Status(errors == 0 ? L("Vol terminé : scènes retirées et plan de vol effacé.", "Flight ended: sceneries removed and flight plan cleared.")
                                   : string.Format(L("Vol terminé avec {0} erreur(s) — voir le journal.", "Flight ended with {0} error(s) — see the log."), errors));
            }
            Changed();
        }

        // ---------------------------------------------------------------- surveillance (toutes les 4 s)
        public void Tick()
        {
            bool running = SimRunning();
            bool changed = running != SimOn;
            SimOn = running;
            if (running)
            {
                if (!simWasRunning)
                {
                    Launcher.ParkingFired = false;
                    if (CfgB("launcher_auto", true)) Launcher.Schedule("sim", "");   // MSFS démarre : applications du lanceur
                    LauncherChanged();
                }
                simWasRunning = true;
            }
            else if (simWasRunning)
            {
                simWasRunning = false;
                Launcher.CloseWithSim();
                LauncherChanged();
                if (skipNextExit)
                {
                    skipNextExit = false;
                    Log(L("Simulateur fermé (vol préparé pendant qu'il tournait : scènes conservées).",
                          "Simulator closed (flight prepared while it was running: sceneries kept)."));
                }
                else if (CfgB("auto_unlink", true) && Flight != null)
                {
                    Log(L("Simulateur fermé : fin du vol détectée.", "Simulator closed: end of flight detected."));
                    EndFlight(true);
                }
                else if ((St["parked"] as JArray ?? new JArray()).Count > 0 && Flight == null)
                {
                    lock (Gate) { RestoreParked(); SaveSt(); }
                    Changed();
                }
            }
            if (!scanning)
            {
                string sig = Scanner.LibSignature(CfgS("library"));
                if (sig != null && libSig != null && sig != libSig)
                {
                    Log(L("Changement détecté dans la bibliothèque : actualisation.", "Change detected in the library: refreshing."));
                    Rescan();
                    return;
                }
            }
            if (changed) Changed();
        }

        // ---------------------------------------------------------------- données pour l'écran
        public JObject LibraryView()
        {
            var arr = new JArray();
            lock (Gate)
            {
                foreach (var p in Packages)
                {
                    arr.Add(new JObject
                    {
                        ["path"] = p.FullPath, ["name"] = p.Name, ["title"] = p.Title, ["type"] = p.Type,
                        ["creator"] = p.Creator, ["version"] = p.Version, ["group"] = p.Group,
                        ["icao"] = new JArray(AirportIcaos(p)), ["icaoManual"] = Overrides[p.FullPath] is JObject && Overrides[p.FullPath]["icao"] != null,
                        ["pinned"] = p.Pinned, ["status"] = CommStatus(p),
                    });
                }
            }
            return new JObject { ["packages"] = arr, ["community"] = CommunityList(), ["free"] = FreeSpace(),
                ["undo"] = UndoInfo(), ["communityPath"] = CfgS("community"), ["library"] = CfgS("library") };
        }

        public JObject SettingsView()
        {
            return new JObject
            {
                ["library"] = CfgS("library"), ["community"] = CfgS("community"),
                ["simbrief_user"] = CfgS("simbrief_user"), ["sim_exe"] = CfgS("sim_exe"),
                ["include_alternates"] = CfgB("include_alternates", true), ["auto_unlink"] = CfgB("auto_unlink", true),
                ["lang"] = Lang,
            };
        }

        public void SaveSettings(JObject s)
        {
            string lib = JsonStore.Str(s["library"]).Trim();
            string comm = JsonStore.Str(s["community"]).Trim();
            if (lib != "" && comm != "" && (Scanner.Inside(lib, comm) || Scanner.Inside(comm, lib)))
                throw new Exception(L("La bibliothèque et le dossier Community doivent être deux dossiers séparés (l'un ne peut pas être à l'intérieur de l'autre).",
                                      "The library and the Community folder must be two separate folders (one cannot be inside the other)."));
            lock (Gate)
            {
                Cfg["library"] = lib;
                Cfg["community"] = comm;
                Cfg["simbrief_user"] = JsonStore.Str(s["simbrief_user"]).Trim();
                string exe = JsonStore.Str(s["sim_exe"]).Trim();
                if (exe != "") Cfg["sim_exe"] = exe;
                if (s["include_alternates"] != null) Cfg["include_alternates"] = (bool)s["include_alternates"];
                if (s["auto_unlink"] != null) Cfg["auto_unlink"] = (bool)s["auto_unlink"];
                SaveCfg();
            }
            Status(L("Réglages enregistrés.", "Settings saved."));
        }

        public void SetOption(string key, bool value)
        {
            if (key != "include_alternates" && key != "auto_unlink") return;
            lock (Gate) { Cfg[key] = value; SaveCfg(); }
            Changed();
        }

        public void SetLang(string lang)
        {
            Lang = lang == "en" ? "en" : "fr";
            lock (Gate) { Cfg["lang"] = Lang; SaveCfg(); }
        }
    }
}
