// Profils, doublons ICAO et scènes par défaut (Content.xml), vérification / réparation, quarantaine,
// actions des menus (liens invalides, déplacer vers la bibliothèque, layout.json, propriétés).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    partial class Hangar
    {
        static string NormRel(string s) { return (s ?? "").Replace('/', '\\').Trim('\\'); }
        string PkgFolder(Pkg p) { return NormRel(p.Group); }
        static bool UnderFolder(string f, string g) { return f.Equals(g, StringComparison.OrdinalIgnoreCase) || f.StartsWith(g + "\\", StringComparison.OrdinalIgnoreCase); }
        JArray PinSuspended { get { var a = St["pin_suspended"] as JArray; if (a == null) { a = new JArray(); St["pin_suspended"] = a; } return a; } }
        JObject DefaultOff { get { var d = St["default_off"] as JObject; if (d == null) { d = new JObject(); St["default_off"] = d; } return d; } }

        // ================================================================ profils
        JArray Profiles { get { var a = Cfg["profiles"] as JArray; if (a == null) { a = new JArray(); Cfg["profiles"] = a; } return a; } }

        Tuple<List<Pkg>, List<string>> ProfileResolve(JObject prof)
        {
            var names = new HashSet<string>((prof["addons"] as JArray ?? new JArray()).Select(x => JsonStore.Str(x)));
            var folders = (prof["folders"] as JArray ?? new JArray()).Select(x => NormRel(JsonStore.Str(x))).Where(x => x != "").ToList();
            var outp = Packages.Where(q => names.Contains(q.Name) || folders.Any(g => UnderFolder(PkgFolder(q), g))).ToList();
            var found = new HashSet<string>(outp.Select(q => q.Name));
            return Tuple.Create(outp, names.Where(n => !found.Contains(n)).OrderBy(n => n).ToList());
        }

        bool IsAirportPkg(Pkg q)
        {
            if (AirportIcaos(q).Count == 0) return false;
            var ov = Overrides[q.FullPath] as JObject;
            return (ov != null && ov["icao"] != null) || !Scanner.IsDecorPack(q.Name + " " + q.Title);
        }

        // ce que l'activation va faire : (à lier, à retirer [package, ancien type], manquants)
        Tuple<List<Pkg>, List<Tuple<Pkg, string>>, List<string>> ProfilePlan(JObject prof)
        {
            var r = ProfileResolve(prof);
            var want = new HashSet<string>(r.Item1.Select(q => q.FullPath), StringComparer.OrdinalIgnoreCase);
            bool all = JsonStore.Str(prof["scope"]) == "all";
            bool ignorePin = prof["ignore_pinned"] != null && prof["ignore_pinned"].Type == JTokenType.Boolean && (bool)prof["ignore_pinned"];
            var toUnlink = new List<Tuple<Pkg, string>>();
            foreach (var prop in LinksObj.Properties().ToList())
            {
                var v = prop.Value as JObject;
                if (v == null) continue;
                var q = ByPath(JsonStore.Str(v["target"]));
                if (q == null || want.Contains(q.FullPath)) continue;
                string kind = JsonStore.Str(v["kind"]);
                if (kind == "pinned" || q.Pinned) { if (!ignorePin) continue; }
                else if (kind != "manual") continue;
                if (!all && !IsAirportPkg(q)) continue;
                toUnlink.Add(Tuple.Create(q, kind));
            }
            return Tuple.Create(r.Item1.Where(q => CommStatus(q) == "none").ToList(), toUnlink, r.Item2);
        }

        public JObject ProfilesView()
        {
            var arr = new JArray();
            lock (Gate)
            {
                int i = 0;
                foreach (var pr in Profiles.OfType<JObject>())
                {
                    var r = ProfileResolve(pr);
                    arr.Add(new JObject { ["index"] = i++, ["name"] = JsonStore.Str(pr["name"]), ["active"] = JsonStore.Str(Cfg["active_profile"]) == JsonStore.Str(pr["name"]),
                        ["count"] = r.Item1.Count, ["missing"] = new JArray(r.Item2), ["scope"] = JsonStore.Str(pr["scope"]) == "all" ? "all" : "scenes",
                        ["ignore_pinned"] = pr["ignore_pinned"] != null && pr["ignore_pinned"].Type == JTokenType.Boolean && (bool)pr["ignore_pinned"],
                        ["folders"] = pr["folders"] ?? new JArray(), ["addons"] = new JArray(r.Item1.Select(q => q.Name).Take(12)) });
                }
            }
            return new JObject { ["profiles"] = arr, ["suspended"] = PinSuspended.Count };
        }

        Tuple<List<string>, List<string>> ProfileCapture(List<Pkg> pkgs)
        {
            var sel = new HashSet<string>(pkgs.Select(q => q.FullPath));
            var byFolder = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
            foreach (var q in Packages)
            {
                var parts = PkgFolder(q).Split(new[] { '\\' }, StringSplitOptions.RemoveEmptyEntries);
                for (int i = 1; i <= parts.Length; i++)
                {
                    string f = string.Join("\\", parts.Take(i));
                    List<string> l;
                    if (!byFolder.TryGetValue(f, out l)) { l = new List<string>(); byFolder[f] = l; }
                    l.Add(q.FullPath);
                }
            }
            var full = byFolder.Where(kv => kv.Value.Count > 0 && kv.Value.All(sel.Contains)).Select(kv => kv.Key).OrderBy(f => f.Count(c => c == '\\')).ToList();
            var folders = new List<string>();
            foreach (var f in full) if (!folders.Any(g => UnderFolder(f, g))) folders.Add(f);
            var covered = new HashSet<string>(folders.SelectMany(f => byFolder[f]));
            return Tuple.Create(folders, pkgs.Where(q => !covered.Contains(q.FullPath)).Select(q => q.Name).OrderBy(n => n).ToList());
        }

        public void ProfileSave(string name, List<string> paths, int replaceIndex)
        {
            lock (Gate)
            {
                var pkgs = paths.Select(ByPath).Where(q => q != null).ToList();
                if (pkgs.Count == 0) throw new Exception(L("Sélectionne d'abord des add-ons dans la Bibliothèque (cases), puis reviens ici.", "Select some add-ons in the Library first (boxes), then come back here."));
                var cap = ProfileCapture(pkgs);
                JObject pr = replaceIndex >= 0 && replaceIndex < Profiles.Count ? (JObject)Profiles[replaceIndex] : Profiles.OfType<JObject>().FirstOrDefault(x => JsonStore.Str(x["name"]).ToLowerInvariant() == name.ToLowerInvariant());
                if (pr == null) { pr = new JObject { ["name"] = name, ["scope"] = "scenes", ["ignore_pinned"] = false }; Profiles.Add(pr); }
                pr["folders"] = new JArray(cap.Item1); pr["addons"] = new JArray(cap.Item2);
                SaveCfg();
            }
        }

        public bool ProfileExists(string name)
        {
            lock (Gate) return Profiles.OfType<JObject>().Any(x => JsonStore.Str(x["name"]).ToLowerInvariant() == (name ?? "").Trim().ToLowerInvariant());
        }

        public void ProfileEdit(int index, JObject change)
        {
            lock (Gate)
            {
                if (index < 0 || index >= Profiles.Count) return;
                var pr = (JObject)Profiles[index];
                if (change["delete"] != null)
                {
                    if (JsonStore.Str(Cfg["active_profile"]) == JsonStore.Str(pr["name"])) Cfg.Remove("active_profile");
                    pr.Remove();
                }
                else
                {
                    if (change["name"] != null)
                    {
                        string n = JsonStore.Str(change["name"]).Trim();
                        if (n != "")
                        {
                            if (JsonStore.Str(Cfg["active_profile"]) == JsonStore.Str(pr["name"])) Cfg["active_profile"] = n;
                            pr["name"] = n;
                        }
                    }
                    if (change["scope"] != null) pr["scope"] = JsonStore.Str(change["scope"]) == "all" ? "all" : "scenes";
                    if (change["ignore_pinned"] != null) pr["ignore_pinned"] = (bool)change["ignore_pinned"];
                }
                SaveCfg();
            }
        }

        // 1er appel : ce que le profil va faire (à confirmer) ; 2e appel avec confirm=true : on le fait
        public JObject ProfileActivate(int index, bool confirm)
        {
            CheckUnlocked();
            string comm = Community;
            lock (Gate)
            {
                if (index < 0 || index >= Profiles.Count) throw new Exception("?");
                var prof = (JObject)Profiles[index];
                string name = JsonStore.Str(prof["name"]);
                if (Flight != null || (St["parked"] as JArray ?? new JArray()).Count > 0)
                    throw new Exception(L("Un vol SimBrief est préparé : termine-le d'abord (onglet Vol SimBrief, « Terminer le vol »), puis active le profil.",
                                          "A SimBrief flight is prepared: end it first (SimBrief flight tab, \"End the flight\"), then activate the profile."));
                var plan = ProfilePlan(prof);
                if (plan.Item1.Count == 0 && plan.Item2.Count == 0)
                {
                    Cfg["active_profile"] = name; SaveCfg();
                    Status(string.Format(L("Profil « {0} » : rien à changer, tout est déjà en place.", "Profile \"{0}\": nothing to change, everything is already in place."), name));
                    return new JObject { ["nothing"] = true };
                }
                if (!confirm)
                    return new JObject { ["name"] = name, ["link"] = new JArray(plan.Item1.Select(q => q.Name)), ["unlink"] = new JArray(plan.Item2.Select(t => t.Item1.Name)),
                        ["missing"] = new JArray(plan.Item3) };
                var suspBefore = new JArray(PinSuspended.Select(x => JsonStore.Str(x)));
                bool ignorePin = prof["ignore_pinned"] != null && prof["ignore_pinned"].Type == JTokenType.Boolean && (bool)prof["ignore_pinned"];
                var susp = new HashSet<string>(ignorePin ? suspBefore.Select(x => JsonStore.Str(x)) : new string[0]);
                var items = new JArray();
                int errors = 0, n = 0;
                foreach (var t in plan.Item2)
                {
                    try
                    {
                        Unlink(LinkPath(t.Item1));
                        items.Add(new JObject { ["path"] = t.Item1.FullPath, ["op"] = "unlink", ["kind"] = t.Item2 });
                        if (t.Item1.Pinned) susp.Add(t.Item1.FullPath);
                        Log(string.Format(L("Profil « {0} » : retiré {1}", "Profile \"{0}\": removed {1}"), name, t.Item1.Name));
                    }
                    catch (Exception e) { errors++; Log(string.Format(L("Erreur en retirant {0} : {1}", "Error removing {0}: {1}"), t.Item1.Name, e.Message)); }
                }
                St["pin_suspended"] = new JArray(susp.OrderBy(x => x));
                if (!ignorePin) errors += SyncPinned();
                foreach (var q in plan.Item1)
                {
                    try { if (DoLink(q, "manual") == L("lié", "linked")) { n++; items.Add(new JObject { ["path"] = q.FullPath, ["op"] = "link" }); } }
                    catch (Exception e) { errors++; Log(string.Format(L("Erreur pour {0} : {1}", "Error for {0}: {1}"), q.Name, e.Message)); }
                }
                undo = new JObject { ["kind"] = "profile", ["name"] = name, ["items"] = items, ["suspended_before"] = suspBefore };
                Cfg["active_profile"] = name;
                SaveCfg(); SaveSt();
                string m = string.Format(L("Profil « {0} » activé : {1} activé(s), {2} retiré(s).", "Profile \"{0}\" activated: {1} activated, {2} removed."), name, n, plan.Item2.Count);
                if (errors > 0) m += string.Format(L(" {0} erreur(s) — voir le journal (onglet Vol).", " {0} error(s) — see the log (Flight tab)."), errors);
                Status(m); Log(m);
            }
            Changed();
            return new JObject { ["done"] = true };
        }

        void UndoProfile(JObject u)
        {
            int errors = 0;
            var items = ((JArray)u["items"]).Reverse().ToList();
            foreach (var it in items)
            {
                var q = ByPath(JsonStore.Str(it["path"]));
                if (q == null) { errors++; continue; }
                try
                {
                    if (JsonStore.Str(it["op"]) == "link")
                    {
                        string link = LinkPath(q);
                        if (LinksObj[link] != null && Links.IsLink(link)) Unlink(link);
                    }
                    else DoLink(q, JsonStore.Str(it["kind"]) != "" ? JsonStore.Str(it["kind"]) : "manual");
                }
                catch (Exception e) { errors++; Log(string.Format(L("Annulation impossible pour {0} : {1}", "Undo failed for {0}: {1}"), q.Name, e.Message)); }
            }
            St["pin_suspended"] = u["suspended_before"] ?? new JArray();
            errors += SyncPinned();
            Cfg.Remove("active_profile");
            undo = null;
            SaveCfg(); SaveSt();
            string m = string.Format(L("Profil « {0} » annulé : Community est revenu comme avant.", "Profile \"{0}\" undone: Community is back as before."), JsonStore.Str(u["name"]));
            if (errors > 0) m += string.Format(L(" {0} erreur(s) — voir le journal.", " {0} error(s) — see the log."), errors);
            Log(m); Status(m);
        }

        public void RestorePins()
        {
            CheckUnlocked();
            lock (Gate)
            {
                if (PinSuspended.Count == 0) throw new Exception(L("Aucun add-on protégé n'est mis de côté.", "No protected add-on is set aside."));
                St["pin_suspended"] = new JArray();
                int errs = SyncPinned();
                SaveSt();
                Status(L("Add-ons ★ protégés remis dans Community.", "★ Protected add-ons put back in Community.") + (errs > 0 ? string.Format(L(" {0} erreur(s).", " {0} error(s)."), errs) : ""));
            }
            Changed();
        }

        // ================================================================ scènes par défaut et Content.xml
        public static string FindContentXml(string community)
        {
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            var bases = new List<string>();
            if (!string.IsNullOrEmpty(community)) { try { bases.Add(Path.GetDirectoryName(Path.GetDirectoryName(Scanner.NormDir(community)))); } catch (Exception) { } }
            bases.Add(Path.Combine(local, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache"));
            bases.Add(Path.Combine(roaming, "Microsoft Flight Simulator 2024"));
            var found = new List<Tuple<DateTime, string>>();
            var skip = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "packages", "sceneryindexes", "simobjects", "pc", "$pcs" };
            foreach (var b in bases)
            {
                try
                {
                    if (string.IsNullOrEmpty(b) || !Directory.Exists(b)) continue;
                    var dirs = new List<string> { b };
                    foreach (var d in Directory.GetDirectories(b))
                        if (!skip.Contains(Path.GetFileName(d)) && (File.GetAttributes(d) & FileAttributes.ReparsePoint) == 0) dirs.Add(d);
                    foreach (var d in dirs)
                    {
                        string f = Path.Combine(d, "Content.xml");
                        if (File.Exists(f)) found.Add(Tuple.Create(File.GetLastWriteTimeUtc(f), Path.GetFullPath(f)));
                    }
                }
                catch (Exception) { }
            }
            return found.Count > 0 ? found.OrderByDescending(x => x.Item1).First().Item2 : "";
        }

        string ContentBackupFolder()
        {
            string f = CfgS("content_backup_dir");
            return f != "" ? f : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "fs_2024_xml_backup");
        }

        // passe des contenus en « UserDisabled » ou les remet en « Activated » (seulement ces lignes) ; copie le fichier avant
        static List<string> ContentXmlSet(string path, List<string> names, bool disabled)
        {
            var raw = File.ReadAllBytes(path);
            bool bom = raw.Length >= 3 && raw[0] == 0xEF && raw[1] == 0xBB && raw[2] == 0xBF;
            string text = new UTF8Encoding(false, true).GetString(raw, bom ? 3 : 0, raw.Length - (bom ? 3 : 0));
            string src = disabled ? "Activated" : "UserDisabled", dst = disabled ? "UserDisabled" : "Activated";
            var changed = new List<string>();
            foreach (var n in names)
            {
                string esc = n.Replace("&", "&amp;").Replace("\"", "&quot;").Replace("<", "&lt;").Replace(">", "&gt;");
                var rx = new Regex("(<Package\\s+name=\"" + Regex.Escape(esc) + "\"\\s+active=\")" + src + "(\")", RegexOptions.IgnoreCase);
                int k = 0;
                text = rx.Replace(text, m => { k++; return m.Groups[1].Value + dst + m.Groups[2].Value; });
                if (k > 0) changed.Add(n);
            }
            if (changed.Count == 0) return changed;
            string folder = Path.GetDirectoryName(path);
            string bak = Path.Combine(folder, "Content.xml.hangar_" + DateTime.Now.ToString("yyyyMMdd") + ".bak");
            if (!File.Exists(bak))
            {
                File.WriteAllBytes(bak, raw);
                try
                {
                    var autos = Directory.GetFiles(folder).Where(f => Regex.IsMatch(Path.GetFileName(f), @"^Content\.xml\.hangar_\d{8}\.bak$", RegexOptions.IgnoreCase)).OrderBy(f => f).ToList();
                    foreach (var old in autos.Take(Math.Max(0, autos.Count - 2))) File.Delete(old);
                }
                catch (Exception) { }
            }
            var data = Encoding.UTF8.GetBytes(text);
            using (var fs = new FileStream(path + ".hangar_tmp", FileMode.Create))
            {
                if (bom) fs.Write(new byte[] { 0xEF, 0xBB, 0xBF }, 0, 3);
                fs.Write(data, 0, data.Length);
            }
            File.Copy(path + ".hangar_tmp", path, true);
            File.Delete(path + ".hangar_tmp");
            return changed;
        }

        void LibraryState(List<string> names, bool disabled)
        {
            if (names.Count == 0) return;
            string path = FindContentXml(CfgS("community"));
            if (path == "") { Log(L("My Library de MSFS : fichier Content.xml introuvable, seul le dossier vide de Community est utilisé.", "MSFS My Library: Content.xml not found, only the empty folder in Community is used.")); return; }
            try
            {
                foreach (var n in ContentXmlSet(path, names, disabled))
                    Log((disabled ? L("Désactivée aussi dans My Library de MSFS : ", "Also disabled in MSFS My Library: ") : L("Réactivée aussi dans My Library de MSFS : ", "Also re-enabled in MSFS My Library: ")) + n);
            }
            catch (Exception e) { Log(L("My Library de MSFS : modification impossible (", "MSFS My Library: change impossible (") + e.Message + ")."); }
        }

        // au démarrage, MSFS fermé : les scènes par défaut désactivées le restent dans My Library
        public void SyncLibraryState()
        {
            if (DefaultOff.Count > 0 && CfgB("content_used", false) && !SimRunning())
                lock (Gate) LibraryState(DefaultOff.Properties().Select(p => p.Name).ToList(), true);
        }

        // avant de modifier Content.xml : faut-il proposer la sauvegarde initiale ?
        public JObject ContentCheck()
        {
            string path = FindContentXml(CfgS("community"));
            string folder = ContentBackupFolder();
            bool need = path != "" && !File.Exists(Path.Combine(folder, "Content.xml")) && !CfgB("content_ok", false);
            return new JObject { ["need"] = need, ["path"] = path, ["backup"] = Path.Combine(folder, "Content.xml"), ["folder"] = folder };
        }

        public void ContentAnswer(bool backup, string folder, bool hide)
        {
            string path = FindContentXml(CfgS("community"));
            if (folder == "") folder = ContentBackupFolder();
            if (backup && path != "")
            {
                string dest = Path.Combine(folder, "Content.xml");
                if (!File.Exists(dest)) { Directory.CreateDirectory(folder); File.Copy(path, dest); }
                Log(L("Sauvegarde initiale de Content.xml : ", "Initial Content.xml backup: ") + dest);
            }
            lock (Gate)
            {
                Cfg["content_backup_dir"] = folder;
                Cfg["content_used"] = true;
                if (hide) Cfg["content_ok"] = true;
                SaveCfg();
            }
        }

        public void DisableDefaults(List<string> names)
        {
            CheckUnlocked();
            string comm = Community;
            lock (Gate)
            {
                var already = names.Where(n => DefaultOff[n] != null).ToList();
                var todo = names.Where(n => DefaultOff[n] == null).ToList();
                if (todo.Count == 0)
                {
                    if (already.Count > 0) { LibraryState(already, true); Status(L("Scène(s) déjà désactivée(s) : My Library de MSFS mis à jour.", "Scenery(ies) already disabled: MSFS My Library updated.")); }
                    return;
                }
                int done = 0;
                foreach (var n in todo)
                {
                    string path = Path.Combine(comm, n);
                    if (Links.Lexists(path)) { Log(string.Format(L("Impossible de désactiver {0} : un dossier ou lien du même nom existe déjà dans Community.", "Unable to disable {0}: a folder or link with the same name already exists in Community."), n)); continue; }
                    try { Directory.CreateDirectory(path); }
                    catch (Exception e) { Log(string.Format(L("Impossible de désactiver {0} : {1}", "Unable to disable {0}: {1}"), n, e.Message)); continue; }
                    DefaultOff[n] = new JObject { ["date"] = DateTime.Now.ToString("dd/MM/yyyy HH:mm"), ["icao"] = new JArray(StreamedIcao(n, "")) };
                    done++;
                    Log(L("Scène par défaut désactivée : ", "Default scenery disabled: ") + n);
                }
                LibraryState(todo.Where(n => DefaultOff[n] != null).ToList(), true);
                SaveSt();
                Status(string.Format(L("{0} scène(s) par défaut désactivée(s).", "{0} default scenery(ies) disabled."), done));
            }
            PushMap(); Changed();
        }

        public void EnableDefaults(List<string> names)
        {
            CheckUnlocked();
            string comm = CfgS("community");
            lock (Gate)
            {
                int done = 0;
                foreach (var n in names)
                {
                    if (DefaultOff[n] == null) continue;
                    string path = comm != "" ? Path.Combine(comm, n) : "";
                    if (path != "" && Directory.Exists(path) && !Links.IsLink(path))
                    {
                        try { Directory.Delete(path, false); }   // seulement un dossier vide : aucun risque pour un vrai add-on
                        catch (Exception e) { Log(string.Format(L("Impossible de réactiver {0} : le dossier n'est pas vide ({1}).", "Unable to re-enable {0}: the folder is not empty ({1})."), n, e.Message)); continue; }
                    }
                    DefaultOff.Remove(n);
                    done++;
                    Log(L("Scène par défaut réactivée : ", "Default scenery re-enabled: ") + n);
                }
                LibraryState(names.Where(n => DefaultOff[n] == null).ToList(), false);
                SaveSt();
                Status(string.Format(L("{0} scène(s) par défaut réactivée(s).", "{0} default scenery(ies) re-enabled."), done));
            }
            PushMap(); Changed();
        }

        public JObject ContentBackups()
        {
            string path = FindContentXml(CfgS("community"));
            if (path == "") throw new Exception(L("Fichier Content.xml de MSFS 2024 introuvable.", "MSFS 2024 Content.xml file not found."));
            string folder = ContentBackupFolder();
            var outp = new JArray();
            string ini = Path.Combine(folder, "Content.xml");
            if (File.Exists(ini)) outp.Add(new JObject { ["date"] = File.GetLastWriteTime(ini).ToString("dd/MM/yyyy HH:mm"), ["kind"] = L("initiale", "initial"), ["file"] = ini });
            var more = new List<Tuple<int, DateTime, string, string>>();
            var places = new[] { Tuple.Create(Path.GetDirectoryName(path), @"^Content\.xml\.hangar_\d{8}\.bak$", L("automatique", "automatic"), 0),
                                 Tuple.Create(folder, @"^Content_.+\.xml$", L("avant restauration", "before restore"), 1) };
            foreach (var pl in places)
            {
                try { foreach (var f in Directory.GetFiles(pl.Item1)) if (Regex.IsMatch(Path.GetFileName(f), pl.Item2, RegexOptions.IgnoreCase)) more.Add(Tuple.Create(pl.Item4, File.GetLastWriteTime(f), f, pl.Item3)); }
                catch (Exception) { }
            }
            foreach (var m in more.OrderBy(x => x.Item1).ThenByDescending(x => x.Item2))
                outp.Add(new JObject { ["date"] = m.Item2.ToString("dd/MM/yyyy HH:mm"), ["kind"] = m.Item4, ["file"] = m.Item3 });
            return new JObject { ["path"] = path, ["folder"] = folder, ["backups"] = outp };
        }

        public void ContentRestore(string src)
        {
            CheckUnlocked();
            string path = FindContentXml(CfgS("community"));
            if (path == "" || !File.Exists(src)) throw new Exception("?");
            string folder = ContentBackupFolder();
            Directory.CreateDirectory(folder);
            string keep = Path.Combine(folder, "Content_avant_restauration_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".xml");
            File.Copy(path, keep, true);
            File.Copy(src, path + ".hangar_tmp", true);
            File.Copy(path + ".hangar_tmp", path, true);
            File.Delete(path + ".hangar_tmp");
            lock (Gate) { Cfg["content_used"] = false; SaveCfg(); }
            Log(string.Format(L("Content.xml restauré depuis {0} (ancien fichier gardé : {1})", "Content.xml restored from {0} (old file kept: {1})"), src, keep));
        }

        // ================================================================ doublons ICAO
        public JObject Duplicates()
        {
            lock (Gate)
            {
                string comm = CfgS("community");
                foreach (var n in DefaultOff.Properties().Select(p => p.Name).ToList())
                    if (comm == "" || !Directory.Exists(Path.Combine(comm, n))) DefaultOff.Remove(n);
                var groups = new SortedDictionary<string, List<JObject>>(StringComparer.Ordinal);
                Action<string, JObject> add = (i, o) => { List<JObject> l; if (!groups.TryGetValue(i, out l)) { l = new List<JObject>(); groups[i] = l; } l.Add(o); };
                int nAddons = 0;
                foreach (var p in Packages)
                {
                    var codes = AirportIcaos(p);
                    bool on = CommStatus(p) != "none" && CommStatus(p) != "?";
                    if (codes.Count > 0 && on) nAddons++;
                    foreach (var i in codes)
                        add(i, new JObject { ["kind"] = "addon", ["key"] = p.FullPath, ["name"] = p.Name, ["title"] = p.Title, ["on"] = on });
                }
                var known = new HashSet<string>();
                foreach (var d in (DupStreamed ?? new JArray()).OfType<JObject>())
                {
                    string n = JsonStore.Str(d["name"]);
                    known.Add(n);
                    foreach (var i in (d["icao"] as JArray ?? new JArray()).Select(x => JsonStore.Str(x)))
                        add(i, new JObject { ["kind"] = "default", ["key"] = n, ["name"] = n, ["title"] = JsonStore.Str(d["title"]), ["on"] = DefaultOff[n] == null });
                }
                foreach (var prop in DefaultOff.Properties())
                {
                    if (known.Contains(prop.Name)) continue;
                    var ic = prop.Value["icao"] as JArray;
                    var codes = ic != null && ic.Count > 0 ? ic.Select(x => JsonStore.Str(x)).ToList() : StreamedIcao(prop.Name, "");
                    foreach (var i in codes) add(i, new JObject { ["kind"] = "default", ["key"] = prop.Name, ["name"] = prop.Name, ["title"] = "", ["on"] = false });
                }
                var outp = new JArray();
                int nConf = 0;
                foreach (var kv in groups)
                {
                    bool off = kv.Value.Any(o => JsonStore.Str(o["kind"]) == "default" && !(bool)o["on"]);
                    var act = kv.Value.Where(o => (bool)o["on"]).ToList();
                    List<JObject> items = off ? kv.Value : (act.Count >= 2 ? act : null);
                    if (items == null) continue;
                    int active = items.Count(o => (bool)o["on"]);
                    if (active >= 2) nConf++;
                    outp.Add(new JObject { ["icao"] = kv.Key, ["active"] = active, ["items"] = new JArray(items) });
                }
                return new JObject { ["groups"] = outp, ["scanned"] = DupStreamed != null, ["time"] = DupTime, ["defaults"] = DupStreamed != null ? DupStreamed.Count : 0,
                    ["addons"] = nAddons, ["conflicts"] = nConf, ["streamed"] = StreamedFolder() };
            }
        }

        // ================================================================ vérification et réparation
        List<JObject> HealthIssues()
        {
            var issues = new List<JObject>();
            string lib = CfgS("library");
            if (Packages.Count == 0 || lib == "" || !Directory.Exists(lib)) return issues;
            var byName = Packages.GroupBy(p => p.Name.ToLowerInvariant()).ToDictionary(g => g.Key, g => g.ToList());
            Func<Pkg, string> where = p => p.Group != "" ? p.Group : L("racine", "root");
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var prop in LinksObj.Properties().ToList())
            {
                var v = prop.Value as JObject;
                if (v == null) continue;
                string link = prop.Name, tgt = JsonStore.Str(v["target"]);
                if (Directory.Exists(tgt) && Links.Lexists(link)) continue;
                seen.Add(link);
                string name = Path.GetFileName(link);
                List<Pkg> l;
                var cands = byName.TryGetValue(name.ToLowerInvariant(), out l) ? l.Where(p => !Scanner.SamePath(p.FullPath, tgt)).ToList() : new List<Pkg>();
                if (!Links.Lexists(link) && Directory.Exists(tgt))
                    issues.Add(new JObject { ["kind"] = "forget", ["link"] = link, ["name"] = name, ["msg"] = L("Lien supprimé hors de l'appli", "Link deleted outside the app"), ["fix"] = L("Oublier ce lien", "Forget this link") });
                else if (cands.Count > 0)
                    issues.Add(new JObject { ["kind"] = "moved", ["link"] = link, ["name"] = name, ["new"] = cands[0].FullPath, ["link_kind"] = JsonStore.Str(v["kind"]),
                        ["msg"] = L("Add-on déplacé dans la bibliothèque", "Add-on moved in the library"), ["fix"] = string.Format(L("Refaire le lien (dossier « {0} »)", "Redo the link (folder \"{0}\")"), where(cands[0])) });
                else
                    issues.Add(new JObject { ["kind"] = "missing", ["link"] = link, ["name"] = name, ["msg"] = L("Dossier introuvable dans la bibliothèque", "Folder not found in the library"),
                        ["fix"] = L("Retirer le lien cassé de Community", "Remove the broken link from Community") });
            }
            string comm = CfgS("community");
            if (comm != "" && Directory.Exists(comm))
            {
                string[] entries;
                try { entries = Directory.GetDirectories(comm); } catch (Exception) { entries = new string[0]; }
                foreach (var e in entries)
                {
                    string path = Path.Combine(Scanner.NormDir(comm), Path.GetFileName(e));
                    if (seen.Contains(path) || LinksObj[path] != null || !Links.IsLink(path) || Links.TargetExists(path)) continue;
                    string name = Path.GetFileName(path);
                    List<Pkg> l;
                    if (byName.TryGetValue(name.ToLowerInvariant(), out l) && l.Count > 0)
                        issues.Add(new JObject { ["kind"] = "moved", ["link"] = path, ["name"] = name, ["new"] = l[0].FullPath, ["link_kind"] = "manual",
                            ["msg"] = L("Lien externe cassé, add-on retrouvé", "Broken external link, add-on found"), ["fix"] = string.Format(L("Refaire le lien (dossier « {0} »)", "Redo the link (folder \"{0}\")"), where(l[0])) });
                    else
                        issues.Add(new JObject { ["kind"] = "missing", ["link"] = path, ["name"] = name, ["msg"] = L("Lien externe cassé", "Broken external link"),
                            ["fix"] = L("Retirer le lien cassé de Community", "Remove the broken link from Community") });
                }
            }
            foreach (var prop in DefaultOff.Properties().ToList())
            {
                var ic = prop.Value["icao"] as JArray;
                var codes = new HashSet<string>(ic != null && ic.Count > 0 ? ic.Select(x => JsonStore.Str(x)) : StreamedIcao(prop.Name, ""));
                if (codes.Count > 0 && !Packages.Any(p => AirportIcaos(p).Any(codes.Contains)))
                    issues.Add(new JObject { ["kind"] = "default_orphan", ["name"] = prop.Name,
                        ["msg"] = string.Format(L("Scène par défaut {0} désactivée, mais plus d'add-on pour cet aéroport", "Default scenery {0} disabled, but no add-on left for this airport"), string.Join("/", codes.OrderBy(x => x))),
                        ["fix"] = L("Réactiver la scène par défaut", "Re-enable the default scenery") });
            }
            foreach (var prop in Overrides.Properties().ToList())
            {
                if (Directory.Exists(prop.Name)) continue;
                List<Pkg> l;
                if (byName.TryGetValue(Path.GetFileName(prop.Name).ToLowerInvariant(), out l) && l.Count > 0)
                    issues.Add(new JObject { ["kind"] = "settings", ["old"] = prop.Name, ["new"] = l[0].FullPath, ["name"] = Path.GetFileName(prop.Name),
                        ["msg"] = L("Réglages d'un add-on déplacé", "Settings of a moved add-on"), ["fix"] = L("Reporter la protection ★ et les codes ICAO", "Carry over the ★ protection and ICAO codes") });
            }
            return issues;
        }

        public JArray Health() { lock (Gate) return new JArray(HealthIssues()); }

        public void Repair()
        {
            CheckUnlocked();
            int fixedN = 0, errors = 0;
            lock (Gate)
            {
                foreach (var it in HealthIssues())
                {
                    string k = JsonStore.Str(it["kind"]), link = JsonStore.Str(it["link"]);
                    try
                    {
                        if (k == "forget") LinksObj.Remove(link);
                        else if (k == "missing") { Links.RemoveLink(link); LinksObj.Remove(link); }
                        else if (k == "moved")
                        {
                            Links.RemoveLink(link); LinksObj.Remove(link);
                            Links.MakeLink(JsonStore.Str(it["new"]), link);
                            LinksObj[link] = new JObject { ["target"] = it["new"], ["kind"] = it["link_kind"] };
                        }
                        else if (k == "default_orphan")
                        {
                            string comm = CfgS("community");
                            string path = comm != "" ? Path.Combine(comm, JsonStore.Str(it["name"])) : "";
                            if (path != "" && Directory.Exists(path) && !Links.IsLink(path)) Directory.Delete(path, false);
                            DefaultOff.Remove(JsonStore.Str(it["name"]));
                        }
                        else if (k == "settings")
                        {
                            var old = Overrides[JsonStore.Str(it["old"])] as JObject ?? new JObject();
                            Overrides.Remove(JsonStore.Str(it["old"]));
                            var merged = (JObject)old.DeepClone();
                            var cur = Overrides[JsonStore.Str(it["new"])] as JObject;
                            if (cur != null) foreach (var p in cur.Properties()) merged[p.Name] = p.Value;
                            Overrides[JsonStore.Str(it["new"])] = merged;
                        }
                        fixedN++;
                        Log(string.Format(L("Réparé : {0} — {1}", "Repaired: {0} — {1}"), JsonStore.Str(it["name"]), JsonStore.Str(it["fix"])));
                    }
                    catch (Exception e) { errors++; Log(string.Format(L("Réparation impossible pour {0} : {1}", "Repair failed for {0}: {1}"), JsonStore.Str(it["name"]), e.Message)); }
                }
                SaveCfg(); SaveSt();
            }
            Status(string.Format(L("{0} problème(s) réparé(s){1}.", "{0} problem(s) repaired{1}."), fixedN, errors > 0 ? string.Format(L(", {0} erreur(s) — voir le journal", ", {0} error(s) — see the log"), errors) : ""));
            Rescan();
        }

        // ================================================================ quarantaine
        string QuarDir { get { string lib = CfgS("library"); return lib != "" ? Path.Combine(lib, Scanner.QuarName) : ""; } }
        JObject Quar { get { var q = St["quarantine"] as JObject; if (q == null) { q = new JObject(); St["quarantine"] = q; } return q; } }

        static void MoveDir(string src, string dest)
        {
            try { Directory.Move(src, dest); return; }
            catch (IOException) { if (Path.GetPathRoot(Path.GetFullPath(src)).Equals(Path.GetPathRoot(Path.GetFullPath(dest)), StringComparison.OrdinalIgnoreCase)) throw; }
            CopyDir(src, dest);   // autre disque : copie puis suppression de l'original
            Directory.Delete(src, true);
        }

        static void CopyDir(string src, string dest)
        {
            Directory.CreateDirectory(dest);
            foreach (var f in Directory.GetFiles(src)) File.Copy(f, Path.Combine(dest, Path.GetFileName(f)));
            foreach (var d in Directory.GetDirectories(src)) CopyDir(d, Path.Combine(dest, Path.GetFileName(d)));
        }

        public JObject Quarantine(List<string> paths)
        {
            CheckUnlocked();
            string qdir = QuarDir;
            if (qdir == "") throw new Exception(L("Indique d'abord ta bibliothèque dans l'onglet Réglages.", "Set your library in the Settings tab first."));
            Directory.CreateDirectory(qdir);
            int moved = 0, errors = 0;
            lock (Gate)
            {
                foreach (var p in paths.Select(ByPath).Where(x => x != null).ToList())
                {
                    string link = CfgS("community") != "" ? LinkPath(p) : "";
                    if (link != "" && Links.IsLink(link) && Scanner.SamePath(Links.LinkTarget(link), p.FullPath))
                    {
                        try { Unlink(link); }
                        catch (Exception e) { errors++; Log(string.Format(L("Erreur en retirant {0} de Community : {1}", "Error removing {0} from Community: {1}"), p.Name, e.Message)); continue; }
                    }
                    string dest = Path.Combine(qdir, p.Name);
                    for (int i = 2; Links.Lexists(dest); i++) dest = Path.Combine(qdir, p.Name + " (" + i + ")");
                    try { MoveDir(p.FullPath, dest); }
                    catch (Exception e) { errors++; Log(string.Format(L("Impossible de déplacer {0} : {1}", "Unable to move {0}: {1}"), p.Name, e.Message)); continue; }
                    var entry = new JObject { ["origin"] = p.FullPath, ["date"] = DateTime.Now.ToString("dd/MM/yyyy HH:mm") };
                    var ov = Overrides[p.FullPath];
                    if (ov != null) { entry["override"] = ov.DeepClone(); Overrides.Remove(p.FullPath); }
                    Quar[Path.GetFullPath(dest)] = entry;
                    moved++;
                    Log(L("Mis en quarantaine : ", "Quarantined: ") + p.Name);
                }
                SaveCfg(); SaveSt();
            }
            Rescan();
            return new JObject { ["moved"] = moved, ["errors"] = errors };
        }

        public JObject QuarantineList()
        {
            string qdir = QuarDir, lib = CfgS("library");
            var arr = new JArray();
            if (qdir != "" && Directory.Exists(qdir))
            {
                var dirs = Directory.GetDirectories(qdir);
                Array.Sort(dirs, StringComparer.OrdinalIgnoreCase);
                foreach (var d in dirs)
                {
                    string path = Path.GetFullPath(d);
                    var info = Quar[path] as JObject ?? new JObject();
                    string origin = JsonStore.Str(info["origin"]), where = "?";
                    if (origin != "")
                    {
                        string parent = Path.GetDirectoryName(origin);
                        where = Scanner.SamePath(parent, lib) ? L("(racine)", "(root)") : (parent.StartsWith(Scanner.NormDir(lib), StringComparison.OrdinalIgnoreCase) ? parent.Substring(Scanner.NormDir(lib).Length).TrimStart('\\') : parent);
                    }
                    arr.Add(new JObject { ["path"] = path, ["name"] = Path.GetFileName(path), ["where"] = where, ["date"] = JsonStore.Str(info["date"]) });
                }
            }
            return new JObject { ["items"] = arr, ["folder"] = qdir };
        }

        public int QuarantineRestore(List<string> paths)
        {
            CheckUnlocked();
            int errors = 0;
            string lib = CfgS("library");
            lock (Gate)
            {
                foreach (var path in paths)
                {
                    var info = Quar[path] as JObject ?? new JObject();
                    string origin = JsonStore.Str(info["origin"]);
                    if (origin == "") origin = Path.Combine(lib, Path.GetFileName(path));
                    if (Links.Lexists(origin)) { errors++; Log(L("Restauration impossible, un dossier existe déjà : ", "Restore impossible, a folder already exists: ") + origin); continue; }
                    try { Directory.CreateDirectory(Path.GetDirectoryName(origin)); MoveDir(path, origin); }
                    catch (Exception e) { errors++; Log(string.Format(L("Restauration impossible pour {0} : {1}", "Restore failed for {0}: {1}"), Path.GetFileName(path), e.Message)); continue; }
                    if (info["override"] != null) Overrides[origin] = info["override"].DeepClone();
                    Quar.Remove(path);
                    Log(L("Restauré : ", "Restored: ") + Path.GetFileName(origin));
                }
                SaveCfg(); SaveSt();
            }
            Rescan();
            return errors;
        }

        // ================================================================ actions des menus
        public int DeleteBroken(List<string> paths)
        {
            CheckUnlocked();
            string comm = Community;
            int n = 0;
            lock (Gate)
            {
                if (paths == null || paths.Count == 0)
                {
                    paths = new List<string>();
                    foreach (var e in Directory.GetDirectories(comm))
                    {
                        string p = Path.Combine(comm, Path.GetFileName(e));
                        if (Links.IsLink(p) && !Links.TargetExists(p)) paths.Add(p);
                    }
                }
                foreach (var p in paths)
                {
                    try { Links.RemoveLink(p); LinksObj.Remove(p); n++; Log(L("Lien invalide supprimé : ", "Invalid link deleted: ") + Path.GetFileName(p)); }
                    catch (Exception e) { Log(string.Format(L("Impossible de supprimer {0} : {1}", "Unable to delete {0}: {1}"), Path.GetFileName(p), e.Message)); }
                }
                SaveSt();
            }
            Status(string.Format(L("{0} lien(s) invalide(s) supprimé(s).", "{0} invalid link(s) deleted."), n));
            Changed();
            return n;
        }

        public int CountBroken()
        {
            string comm = CfgS("community");
            if (comm == "" || !Directory.Exists(comm)) return 0;
            try { return Directory.GetDirectories(comm).Count(e => { string p = Path.Combine(comm, Path.GetFileName(e)); return Links.IsLink(p) && !Links.TargetExists(p); }); }
            catch (Exception) { return 0; }
        }

        public void MoveToLibrary(string path, string destDir)
        {
            CheckUnlocked();
            string lib = CfgS("library");
            if (lib == "" || !Directory.Exists(lib)) throw new Exception(L("Indique d'abord ta bibliothèque dans l'onglet Réglages.", "Set your library in the Settings tab first."));
            bool isL = Links.IsLink(path);
            string src = isL ? Links.LinkTarget(path) : path, name = Path.GetFileName(path);
            if (Scanner.Inside(destDir, CfgS("community")) || Scanner.Inside(destDir, src))
                throw new Exception(L("Choisis un dossier de ta bibliothèque, pas Community ni l'add-on lui-même.", "Choose a folder of your library, not Community nor the add-on itself."));
            string dest = Path.Combine(destDir, name);
            if (Scanner.SamePath(dest, src)) throw new Exception(L("L'add-on est déjà dans ce dossier.", "The add-on is already in this folder."));
            if (Links.Lexists(dest)) throw new Exception(string.Format(L("Un dossier « {0} » existe déjà à cet endroit.", "A folder \"{0}\" already exists there."), name));
            string kind;
            lock (Gate) { var v = LinksObj[path] as JObject; kind = v != null ? JsonStore.Str(v["kind"]) : "manual"; }
            Status(string.Format(L("Déplacement de « {0} » en cours…", "Moving \"{0}\"…"), name));
            if (isL) Links.RemoveLink(path);
            try { MoveDir(src, dest); }
            catch (Exception)
            {
                if (isL && Directory.Exists(src) && !Links.Lexists(path)) Links.MakeLink(src, path);
                throw;
            }
            Links.MakeLink(dest, path);
            lock (Gate)
            {
                LinksObj[path] = new JObject { ["target"] = dest, ["kind"] = kind };
                var ov = Overrides[src];
                if (ov != null) { Overrides[dest] = ov.DeepClone(); Overrides.Remove(src); }
                SaveCfg(); SaveSt();
            }
            Log(string.Format(L("Déplacé dans la bibliothèque : {0} → {1}", "Moved to the library: {0} → {1}"), name, destDir));
            Status(string.Format(L("« {0} » est maintenant rangé dans ta bibliothèque.", "\"{0}\" is now stored in your library."), name));
            Rescan();
        }

        public string RealTarget(string path) { return Links.IsLink(path) ? Links.LinkTarget(path) : path; }

        public string RegenLayout(string pkg)
        {
            CheckUnlocked();
            if (!File.Exists(Path.Combine(pkg, "manifest.json")))
                throw new Exception(string.Format(L("« {0} » n'a pas de manifest.json : ce n'est pas un add-on MSFS.", "\"{0}\" has no manifest.json: it is not an MSFS add-on."), Path.GetFileName(pkg)));
            var exclude = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "layout.json", "manifest.json", "layout.json.bak", "manifest.json.bak", "msfslayoutgenerator.exe" };
            var files = new JArray();
            long total = 0;
            string root = Scanner.NormDir(pkg);
            Action<string> walk = null;
            walk = dir =>
            {
                var fs = Directory.GetFiles(dir); Array.Sort(fs, StringComparer.Ordinal);
                foreach (var f in fs)
                {
                    string rel = f.Substring(root.Length + 1).Replace('\\', '/');
                    if (exclude.Contains(rel) || rel.StartsWith("_CVT_")) continue;
                    var fi = new FileInfo(f);
                    files.Add(new JObject { ["path"] = rel, ["size"] = fi.Length, ["date"] = fi.LastWriteTimeUtc.ToFileTimeUtc() });
                    total += fi.Length;
                }
                var ds = Directory.GetDirectories(dir); Array.Sort(ds, StringComparer.Ordinal);
                foreach (var d in ds) walk(d);
            };
            walk(root);
            string layout = Path.Combine(root, "layout.json"), manifest = Path.Combine(root, "manifest.json");
            if (File.Exists(layout)) File.Copy(layout, layout + ".bak", true);
            File.WriteAllText(layout, new JObject { ["content"] = files }.ToString(Formatting.Indented).Replace("\r\n", "\n"), new UTF8Encoding(false));
            try
            {
                var m = JObject.Parse(File.ReadAllText(manifest, Encoding.UTF8));
                File.Copy(manifest, manifest + ".bak", true);
                m["total_package_size"] = total.ToString().PadLeft(20, '0');
                File.WriteAllText(manifest, m.ToString(Formatting.Indented).Replace("\r\n", "\n"), new UTF8Encoding(false));
            }
            catch (Exception) { }
            string msg = string.Format(L("layout.json régénéré : {0} ({1} fichiers, {2})", "layout.json regenerated: {0} ({1} files, {2})"), Path.GetFileName(root), files.Count, FmtSize(total));
            Log(msg); Status(msg);
            return msg;
        }

        public JObject Properties(string path)
        {
            string pkg = RealTarget(path);
            if (!Directory.Exists(pkg)) throw new Exception(L("Dossier introuvable.", "Folder not found."));
            JObject m;
            try { m = JObject.Parse(File.ReadAllText(Path.Combine(pkg, "manifest.json"), Encoding.UTF8)); } catch (Exception) { m = new JObject(); }
            long size = FolderSize(new[] { pkg });
            int n = 0;
            try { n = Directory.EnumerateFiles(pkg, "*", SearchOption.AllDirectories).Count(); } catch (Exception) { }
            var p = Packages.FirstOrDefault(x => Scanner.SamePath(x.FullPath, pkg));
            return new JObject
            {
                ["name"] = Path.GetFileName(pkg), ["path"] = pkg, ["link"] = Links.IsLink(path) ? path : "", ["title"] = JsonStore.Str(m["title"]), ["creator"] = JsonStore.Str(m["creator"]),
                ["type"] = JsonStore.Str(m["content_type"]), ["version"] = JsonStore.Str(m["package_version"]), ["minimum"] = JsonStore.Str(m["minimum_game_version"]),
                ["size"] = FmtSize(size), ["files"] = n, ["icao"] = p != null ? string.Join(", ", AirportIcaos(p)) : "", ["pinned"] = p != null && p.Pinned,
            };
        }
    }
}
