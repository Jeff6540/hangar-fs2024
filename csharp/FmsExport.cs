// FMS — « Envoyer à l'avion » : le plan du FMS est préparé pour les GPS de l'avion, sans passer par la tablette.
//  - MSFS (G1000 NXi, G3000… des avions de base) : fichier .PLN chargé comme plan actif par SimConnect (FlightPlanLoad).
//  - GTN 750 / 650 de PMS50 : fichier « fpl.pln » déposé dans le sous-dossier fpl\gtn750 (ou gtn650) du paquet,
//    puis dans le GTN : Flight Plan > Import.
//  - GTN 750 / 650 de TDS (GTNXi) : fichier .gfp déposé dans ProgramData\TDS\GTNXi\FPL,
//    puis dans le GTN : FPL > Menu > Catalog > Menu > Import.
// Aucun chemin propre à un PC n'est écrit en dur : tout vient des réglages (Community, bibliothèque) ou de Windows.
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class FmsExport
    {
        /// <summary>Fichiers .PLN à charger par la boucle SimConnect du relais (chemin sans extension).</summary>
        public static readonly ConcurrentQueue<string> PlanLoads = new ConcurrentQueue<string>();

        static string Dir { get { return Path.Combine(AppInfo.BaseDir, "fms"); } }
        static readonly CultureInfo CI = CultureInfo.InvariantCulture;

        static double Num(JToken t) { double d; double.TryParse(JsonStore.Str(t), NumberStyles.Float, CI, out d); return d; }
        static string Esc(string s) { return System.Security.SecurityElement.Escape(s ?? "") ?? ""; }

        static string Dms(double v, bool lat)
        {
            string h = lat ? (v >= 0 ? "N" : "S") : (v >= 0 ? "E" : "W");
            v = Math.Abs(v);
            int d = (int)v; double mf = (v - d) * 60; int m = (int)mf; double s = (mf - m) * 60;
            if (s >= 59.995) { s = 0; m++; } if (m >= 60) { m = 0; d++; }
            return h + d + "° " + m + "' " + s.ToString("0.00", CI) + "\"";
        }

        static bool Named(string id) { return Regex.IsMatch(id ?? "", "^[A-Z0-9]{2,5}$") && !Regex.IsMatch(id, "^WP\\d+$"); }

        /// <summary>Fabrique le .PLN au format minimal de Little Navmap pour MSFS 2024 (celui que le GTN PMS50 importe) :
        /// départ et arrivée par leur code OACI, seulement les points intermédiaires, texte en ASCII, degrés sans zéros devant.</summary>
        public static string Pln(JObject plan, out string dep, out string arr)
        {
            var route = plan["route"] as JArray ?? new JArray();
            var pts = route.OfType<JObject>().Where(w => !(Num(w["lat"]) == 0 && Num(w["lon"]) == 0)).ToList();
            var o = plan["origin"] as JObject ?? new JObject(); var d0 = plan["dest"] as JObject ?? new JObject();
            dep = JsonStore.Str(o["icao"]); arr = JsonStore.Str(d0["icao"]);
            if (dep == "" && pts.Count > 0) dep = JsonStore.Str(pts[0]["ident"]);
            if (arr == "" && pts.Count > 1) arr = JsonStore.Str(pts[pts.Count - 1]["ident"]);
            int cruise = (int)Num(plan["cruiseAlt"]); if (cruise <= 0) cruise = 3500;
            Func<string, string> asc = t => Regex.Replace(t ?? "", "[^\\x20-\\x7E]", "");
            Func<double, bool, string> dms = (v, lat) =>
            {
                double a = Math.Abs(v); long tt = (long)Math.Round(a * 360000); long dd = tt / 360000, mm = (tt % 360000) / 6000; double ss = (tt % 6000) / 100.0;
                return (lat ? (v < 0 ? "S" : "N") : (v < 0 ? "W" : "E")) + dd + "\u00b0 " + mm + "' " + ss.ToString("0.00", CI) + "\"";
            };
            string a1 = Esc(asc(dep)), a2 = Esc(asc(arr));
            string sid = JsonStore.Str(plan["departure"]), star = JsonStore.Str(plan["arrival"]), appr = JsonStore.Str(plan["approach"]);
            var sb = new StringBuilder();
            sb.Append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<SimBase.Document>\n    <FlightPlan.FlightPlan>\n");
            sb.Append("        <DepartureID>").Append(a1).Append("</DepartureID>\n        <DestinationID>").Append(a2).Append("</DestinationID>\n");
            sb.Append("        <Title>").Append(a1 + " - " + a2).Append("</Title>\n");
            sb.Append("        <Descr>").Append((sid != "" || star != "" || appr != "") ? "IFR" : "VFR").Append(" flight from ").Append(a1).Append(" to ").Append(a2).Append(" created by Hangar FS 2024 FMS</Descr>\n");
            sb.Append("        <FPType>").Append((sid != "" || star != "" || appr != "") ? "IFR" : "VFR").Append("</FPType>\n");
            sb.Append("        <CruisingAlt>").Append(cruise).Append(".000</CruisingAlt>\n");
            sb.Append("        <AppVersion>\n            <AppVersionMajor>12</AppVersionMajor>\n            <AppVersionMinor>1</AppVersionMinor>\n            <AppVersionBuild>282174</AppVersionBuild>\n        </AppVersion>\n");
            for (int i = 0; i < pts.Count; i++)
            {
                var w = pts[i];
                string id = Esc(asc(JsonStore.Str(w["ident"]).ToUpperInvariant()));
                bool endApt = JsonStore.Str(w["type"]) == "apt" && (i == 0 || i == pts.Count - 1) && (id == a1 || id == a2);
                if (endApt) continue;   // départ et arrivée : seulement par DepartureID / DestinationID
                int alt = (int)Num(w["alt"]); if (alt <= 0 || id.StartsWith("RW")) alt = cruise;
                sb.Append("        <ATCWaypoint id=\"").Append(id).Append("\">\n            <ATCWaypointType>User</ATCWaypointType>\n");
                sb.Append("            <WorldPosition>").Append(dms(Num(w["lat"]), true)).Append(",").Append(dms(Num(w["lon"]), false)).Append(",+").Append(alt.ToString("000000", CI)).Append(".00</WorldPosition>\n");
                sb.Append("            <ICAO>\n                <ICAOIdent>").Append(id).Append("</ICAOIdent>\n            </ICAO>\n        </ATCWaypoint>\n");
            }
            sb.Append("    </FlightPlan.FlightPlan>\n</SimBase.Document>\n");
            return sb.ToString();
        }

        // ---- aéroports (base OurAirports de l'appli) : position et altitude, pour un .PLN qui ne donne que le code OACI
        static Dictionary<string, double[]> aptCache;
        public static JObject Airport(string icao)
        {
            icao = (icao ?? "").Trim().ToUpperInvariant();
            if (icao == "") return new JObject { ["ok"] = false };
            if (aptCache == null)
            {
                var c = new Dictionary<string, double[]>(StringComparer.OrdinalIgnoreCase);
                try
                {
                    if (!File.Exists(Airports.FilePath)) Airports.Load();
                    using (var rd = new StreamReader(Airports.FilePath, Encoding.UTF8))
                    {
                        var head = SplitCsv(rd.ReadLine() ?? "");
                        int iId = head.IndexOf("ident"), iIcao = head.IndexOf("icao_code"), iGps = head.IndexOf("gps_code"), iLa = head.IndexOf("latitude_deg"), iLo = head.IndexOf("longitude_deg"), iEl = head.IndexOf("elevation_ft");
                        string line;
                        while ((line = rd.ReadLine()) != null)
                        {
                            var f = SplitCsv(line);
                            Func<int, string> g = k => k >= 0 && k < f.Count ? f[k] : "";
                            double la, lo, el;
                            if (!double.TryParse(g(iLa), NumberStyles.Float, CI, out la) || !double.TryParse(g(iLo), NumberStyles.Float, CI, out lo)) continue;
                            bool hasEl = double.TryParse(g(iEl), NumberStyles.Float, CI, out el);
                            var rec = new[] { la, lo, hasEl ? el : double.NaN };
                            foreach (var k in new[] { g(iIcao), g(iGps), g(iId) }) if (k.Length >= 3 && !c.ContainsKey(k)) c[k] = rec;
                        }
                    }
                }
                catch (Exception) { }
                aptCache = c;
            }
            double[] r;
            if (!aptCache.TryGetValue(icao, out r)) return new JObject { ["ok"] = false };
            var o = new JObject { ["ok"] = true, ["lat"] = r[0], ["lon"] = r[1] };
            if (!double.IsNaN(r[2]) && r[2] != 0) o["elev"] = Math.Round(r[2]);
            return o;
        }

        static List<string> SplitCsv(string line)
        {
            var res = new List<string>(); var sb = new StringBuilder(); bool q = false;
            for (int i = 0; i < line.Length; i++)
            {
                char ch = line[i];
                if (q) { if (ch == '"') { if (i + 1 < line.Length && line[i + 1] == '"') { sb.Append('"'); i++; } else q = false; } else sb.Append(ch); }
                else if (ch == '"') q = true;
                else if (ch == ',') { res.Add(sb.ToString()); sb.Clear(); }
                else sb.Append(ch);
            }
            res.Add(sb.ToString());
            return res;
        }

        /// <summary>Plan au format Garmin .gfp (GTN TDS) : FPN/RI:F:DEP:F:FIX:…:F:ARR (les points libres sont mis en coordonnées).</summary>
        public static string Gfp(JObject plan)
        {
            var route = plan["route"] as JArray ?? new JArray();
            var parts = new List<string>();
            foreach (var w in route.OfType<JObject>())
            {
                string id = JsonStore.Str(w["ident"]).ToUpperInvariant();
                if (Named(id)) { parts.Add("F:" + id); continue; }
                double la = Num(w["lat"]), lo = Num(w["lon"]);
                if (la == 0 && lo == 0) continue;
                // coordonnées Garmin : N/S + degrés + minutes au dixième, E/W + degrés sur 3 chiffres + minutes au dixième (ex. N4310.7E00000.4)
                Func<double, int, string, string, string> c = (v, dd, p, n) => { double a = Math.Abs(v); int d = (int)a; double m = Math.Round((a - d) * 60, 1); if (m >= 60) { m = 0; d++; } return (v >= 0 ? p : n) + d.ToString(new string('0', dd)) + m.ToString("00.0", CI); };
                parts.Add("F:" + c(la, 2, "N", "S") + c(lo, 3, "E", "W"));
            }
            return "FPN/RI:" + string.Join(":", parts);
        }

        static IEnumerable<string> PackageDirs(string root)
        {
            if (string.IsNullOrEmpty(root) || !Directory.Exists(root)) yield break;
            string[] dirs; try { dirs = Directory.GetDirectories(root); } catch (Exception) { yield break; }
            foreach (var d in dirs) yield return d;
            // bibliothèque rangée par dossiers (AVIONS, SOUND…) : un niveau de plus
            foreach (var d in dirs)
            {
                string[] sub; try { sub = Directory.GetDirectories(d); } catch (Exception) { continue; }
                foreach (var s in sub) yield return s;
            }
        }

        /// <summary>Ouvre le dossier des plans du FMS dans l'explorateur, le dernier fichier sélectionné.</summary>
        public static bool OpenFolder(string file)
        {
            try
            {
                Directory.CreateDirectory(Dir);
                string full = string.IsNullOrEmpty(file) ? "" : Path.GetFullPath(file);
                if (full != "" && File.Exists(full) && (full.StartsWith(Path.GetFullPath(Dir), StringComparison.OrdinalIgnoreCase) || string.Equals(full, Path.GetFullPath(EfbFile), StringComparison.OrdinalIgnoreCase)))
                    System.Diagnostics.Process.Start("explorer.exe", "/select,\"" + full + "\"");
                else System.Diagnostics.Process.Start("explorer.exe", "\"" + Dir + "\"");
                return true;
            }
            catch (Exception) { return false; }
        }

        /// <summary>Envoie le plan du FMS : renvoie ce qui a été fait, cible par cible.</summary>
        // ---- EFB de MSFS 2024 : le même fichier, au même endroit, réécrit à chaque changement de plan.
        // La fenêtre « Load from this PC » de l'EFB retient le dernier dossier : un double-clic suffit ensuite.
        public static string EfbDir { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Hangar FS 2024"); } }
        public static string EfbFile { get { return Path.Combine(EfbDir, "Plan FMS.pln"); } }
        // dossier où s'ouvre la fenêtre « Load from this PC » de l'EFB : le dossier de MSFS 2024 lui-même
        // (version Microsoft Store / Xbox, ou version Steam) : le fichier y est aussi déposé, pour l'avoir sous les yeux
        static IEnumerable<string> SimDirs()
        {
            string la = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), ra = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            foreach (var d in new[] { Path.Combine(la, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalState"), Path.Combine(ra, "Microsoft Flight Simulator 2024") })
                if (Directory.Exists(d)) yield return d;
        }
        static readonly object EfbGate = new object();
        static string efbLast;
        public static void WriteEfb(JObject state)
        {
            try
            {
                var plan = state["plan"] as JObject;
                var route = plan != null ? plan["route"] as JArray : null;
                if (route == null || route.Count < 2) return;
                string dep, arr, pln = Pln(plan, out dep, out arr);
                lock (EfbGate)
                {
                    if (pln == efbLast) return;
                    Directory.CreateDirectory(EfbDir);
                    File.WriteAllText(EfbFile, pln, new UTF8Encoding(false));
                    foreach (var d in SimDirs()) { try { File.WriteAllText(Path.Combine(d, "Plan FMS.pln"), pln, new UTF8Encoding(false)); } catch (Exception) { } }
                    efbLast = pln;
                }
                WriteGtnAuto(plan, pln, dep, arr);
            }
            catch (Exception) { }
        }

        /// <summary>GTN de PMS50 (fpl.pln dans son dossier fpl\gtn750 / gtn650) et GTN de TDS (.gfp dans ProgramData).</summary>
        static void WriteGtn(JObject plan, string pln, string name, string community, string library, JArray targets)
        {
                // 2) GTN de PMS50 : paquet qui contient fpl\gtn750 (ou gtn650), dans Community ou la bibliothèque
                var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (var root in new[] { community, library })
                    foreach (var pkg in PackageDirs(root))
                    {
                        string n = Path.GetFileName(pkg) ?? "";
                        if (n.IndexOf("pms50", StringComparison.OrdinalIgnoreCase) < 0) continue;
                        foreach (var model in new[] { "gtn750", "gtn650" })
                        {
                            string fd = Path.Combine(pkg, "fpl", model);
                            // le paquet du GTN 750 (ou 650), ou un paquet qui a déjà ce dossier
                            if (n.IndexOf(model, StringComparison.OrdinalIgnoreCase) < 0 && !Directory.Exists(fd)) continue;
                            try
                            {
                                string real = new DirectoryInfo(fd).FullName;
                                if (!seen.Add(real)) continue;
                                bool existed = File.Exists(Path.Combine(fd, "fpl.pln"));
                                Directory.CreateDirectory(fd);
                                File.WriteAllText(Path.Combine(fd, "fpl.pln"), pln, new UTF8Encoding(false));
                                targets.Add(new JObject { ["id"] = "pms50", ["ok"] = true, ["model"] = model.ToUpperInvariant(), ["pkg"] = n, ["existed"] = existed });
                            }
                            catch (Exception e) { targets.Add(new JObject { ["id"] = "pms50", ["ok"] = false, ["model"] = model.ToUpperInvariant(), ["why"] = e.Message }); }
                        }
                    }

                // 3) GTN de TDS (GTNXi) : dossier des plans de vol dans ProgramData
                try
                {
                    string tds = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "TDS", "GTNXi");
                    if (Directory.Exists(tds))
                    {
                        string fd = Path.Combine(tds, "FPL");
                        Directory.CreateDirectory(fd);
                        File.WriteAllText(Path.Combine(fd, "HANGAR_" + name + ".gfp"), Gfp(plan), new UTF8Encoding(false));
                        targets.Add(new JObject { ["id"] = "tds", ["ok"] = true, ["file"] = "HANGAR_" + name + ".gfp" });
                    }
                }
                catch (Exception e) { targets.Add(new JObject { ["id"] = "tds", ["ok"] = false, ["why"] = e.Message }); }

        }

        // ---- GTN mis à jour tout seul à chaque changement de plan (fichiers réécrits seulement s'ils changent)
        public static Func<string[]> Roots;
        static string gtnLast;
        static void WriteGtnAuto(JObject plan, string pln, string dep, string arr)
        {
            var r = Roots; if (r == null) return;
            string[] roots; try { roots = r(); } catch (Exception) { return; }
            if (roots == null || roots.Length < 2) return;
            string name = Regex.Replace(dep + "_" + arr, "[^A-Za-z0-9_-]", ""); if (name == "_") name = "FMS";
            lock (EfbGate)
            {
                if (pln == gtnLast) return;
                gtnLast = pln;
                // TDS : un seul fichier « HANGAR_FMS.gfp », toujours le même (pas un nouveau à chaque plan)
                WriteGtn(plan, pln, "FMS", roots[0], roots[1], new JArray());
            }
        }

        public static JObject Run(string community, string library, bool simConnected)
        {
            var res = new JObject { ["ok"] = false, ["targets"] = new JArray() };
            var plan = FlightStore.Get()["plan"] as JObject ?? new JObject();
            var route = plan["route"] as JArray;
            if (route == null || route.Count < 2) { res["error"] = Hangar.L("Pas de plan dans le FMS.", "No plan in the FMS."); return res; }
            string dep, arr, pln = Pln(plan, out dep, out arr);
            var targets = (JArray)res["targets"];
            string name = Regex.Replace(dep + "_" + arr, "[^A-Za-z0-9_-]", "");
            if (name == "_") name = "FMS";

            // 1) MSFS : .PLN chargé comme plan actif (le simulateur doit être en vol)
            try
            {
                Directory.CreateDirectory(Dir);
                string f = Path.Combine(Dir, "FMS_" + name + ".pln");
                File.WriteAllText(f, pln, new UTF8Encoding(false));
                if (simConnected) { PlanLoads.Enqueue(f.Substring(0, f.Length - 4)); targets.Add(new JObject { ["id"] = "msfs", ["ok"] = true }); }
                else targets.Add(new JObject { ["id"] = "msfs", ["ok"] = false, ["why"] = "nosim" });
                res["file"] = f;
                WriteEfb(FlightStore.Get());
                if (File.Exists(EfbFile)) res["efb"] = EfbFile;
            }
            catch (Exception e) { targets.Add(new JObject { ["id"] = "msfs", ["ok"] = false, ["why"] = e.Message }); }

            WriteGtn(plan, pln, name, community, library, targets);

            res["ok"] = targets.OfType<JObject>().Any(t => (bool?)t["ok"] == true);
            return res;
        }
    }
}
