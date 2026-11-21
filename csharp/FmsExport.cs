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

        /// <summary>Fabrique le .PLN (format MSFS) à partir du plan du FMS.</summary>
        public static string Pln(JObject plan, out string dep, out string arr)
        {
            var route = plan["route"] as JArray ?? new JArray();
            var pts = route.OfType<JObject>().Where(w => !(Num(w["lat"]) == 0 && Num(w["lon"]) == 0)).ToList();
            dep = pts.Count > 0 ? JsonStore.Str(pts[0]["ident"]) : ""; arr = pts.Count > 1 ? JsonStore.Str(pts[pts.Count - 1]["ident"]) : "";
            string sid = JsonStore.Str(plan["departure"]), star = JsonStore.Str(plan["arrival"]), appr = JsonStore.Str(plan["approach"]);
            bool ifr = sid != "" || star != "" || appr != "";
            int cruise = (int)Num(plan["cruiseAlt"]); if (cruise <= 0) cruise = 5000;
            var sb = new StringBuilder();
            sb.Append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\r\n<SimBase.Document Type=\"AceXML\" version=\"1,0\">\r\n    <Descr>AceXML Document</Descr>\r\n    <FlightPlan.FlightPlan>\r\n");
            sb.Append("        <Title>").Append(Esc(dep + " to " + arr)).Append("</Title>\r\n");
            sb.Append("        <FPType>").Append(ifr ? "IFR" : "VFR").Append("</FPType>\r\n");
            sb.Append("        <RouteType>").Append(ifr ? "HighAlt" : "VOR").Append("</RouteType>\r\n");
            sb.Append("        <CruisingAlt>").Append(cruise).Append("</CruisingAlt>\r\n");
            sb.Append("        <DepartureID>").Append(Esc(dep)).Append("</DepartureID>\r\n");
            sb.Append("        <DestinationID>").Append(Esc(arr)).Append("</DestinationID>\r\n");
            if (pts.Count > 1)
            {
                sb.Append("        <DepartureLLA>").Append(Dms(Num(pts[0]["lat"]), true) + "," + Dms(Num(pts[0]["lon"]), false) + ",+000000.00").Append("</DepartureLLA>\r\n");
                sb.Append("        <DestinationLLA>").Append(Dms(Num(pts[pts.Count - 1]["lat"]), true) + "," + Dms(Num(pts[pts.Count - 1]["lon"]), false) + ",+000000.00").Append("</DestinationLLA>\r\n");
            }
            sb.Append("        <AppVersion>\r\n            <AppVersionMajor>12</AppVersionMajor>\r\n            <AppVersionBuild>282174</AppVersionBuild>\r\n        </AppVersion>\r\n");
            string rwyArr = JsonStore.Str((plan["dest"] as JObject ?? new JObject())["rwy"]);
            for (int i = 0; i < pts.Count; i++)
            {
                var w = pts[i];
                string id = JsonStore.Str(w["ident"]).ToUpperInvariant(), type = JsonStore.Str(w["type"]), via = JsonStore.Str(w["via"]);
                bool apt = type == "apt" && (i == 0 || i == pts.Count - 1);
                bool named = apt || Named(id);
                string wt = apt ? "Airport" : !named ? "User" : type == "vor" ? "VOR" : type == "ndb" ? "NDB" : "Intersection";
                double alt = Num(w["alt"]);
                sb.Append("        <ATCWaypoint id=\"").Append(Esc(id)).Append("\">\r\n");
                sb.Append("            <ATCWaypointType>").Append(wt).Append("</ATCWaypointType>\r\n");
                sb.Append("            <WorldPosition>").Append(Dms(Num(w["lat"]), true) + "," + Dms(Num(w["lon"]), false) + "," + (alt >= 0 ? "+" : "-") + Math.Abs(alt).ToString("000000.00", CI)).Append("</WorldPosition>\r\n");
                if (!apt && via != "" && via == sid) sb.Append("            <DepartureFP>").Append(Esc(sid)).Append("</DepartureFP>\r\n");
                else if (!apt && via != "" && via == star) sb.Append("            <ArrivalFP>").Append(Esc(star)).Append("</ArrivalFP>\r\n");
                else if (!apt && (JsonStore.Str(w["ap"]) == "True" || JsonStore.Str(w["ap"]) == "true") && appr != "")
                {
                    var m = Regex.Match(appr, "^([A-Z/ ]+?)\\s+(\\d{2})([LRC]?)");
                    if (m.Success)
                    {
                        sb.Append("            <ApproachTypeFP>").Append(Esc(m.Groups[1].Value.Trim())).Append("</ApproachTypeFP>\r\n");
                        sb.Append("            <RunwayNumberFP>").Append(m.Groups[2].Value).Append("</RunwayNumberFP>\r\n");
                        string des = m.Groups[3].Value == "L" ? "LEFT" : m.Groups[3].Value == "R" ? "RIGHT" : m.Groups[3].Value == "C" ? "CENTER" : "";
                        if (des != "") sb.Append("            <RunwayDesignatorFP>").Append(des).Append("</RunwayDesignatorFP>\r\n");
                    }
                }
                else if (via != "" && Regex.IsMatch(via, "^[A-Z]{1,2}\\d{1,4}$")) sb.Append("            <ATCAirway>").Append(Esc(via)).Append("</ATCAirway>\r\n");
                if (named) sb.Append("            <ICAO>\r\n                <ICAOIdent>").Append(Esc(id)).Append("</ICAOIdent>\r\n            </ICAO>\r\n");
                sb.Append("        </ATCWaypoint>\r\n");
            }
            sb.Append("    </FlightPlan.FlightPlan>\r\n</SimBase.Document>\r\n");
            return sb.ToString();
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
                if (full != "" && File.Exists(full) && full.StartsWith(Path.GetFullPath(Dir), StringComparison.OrdinalIgnoreCase))
                    System.Diagnostics.Process.Start("explorer.exe", "/select,\"" + full + "\"");
                else System.Diagnostics.Process.Start("explorer.exe", "\"" + Dir + "\"");
                return true;
            }
            catch (Exception) { return false; }
        }

        /// <summary>Envoie le plan du FMS : renvoie ce qui a été fait, cible par cible.</summary>
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
            }
            catch (Exception e) { targets.Add(new JObject { ["id"] = "msfs", ["ok"] = false, ["why"] = e.Message }); }

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

            res["ok"] = targets.OfType<JObject>().Any(t => (bool?)t["ok"] == true);
            return res;
        }
    }
}
