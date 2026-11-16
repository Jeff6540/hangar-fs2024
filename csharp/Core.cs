// Hangar FS 2024 — version C# (portage de la 11.8 Python).
// Fonctions de base : réglages, analyse des add-ons, jonctions dans Community, SimBrief.
// Sécurité (comme la version Python) : l'appli ne supprime JAMAIS un vrai dossier, seulement des liens.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Win32.SafeHandles;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class AppInfo
    {
        public const string Name = "Hangar FS 2024";
        public const string Sub = "Addon Manager";
        public const string Version = "12.1";
        public const string UrlSimBrief = "https://dispatch.simbrief.com/";
        public const string UrlLfv = "https://lfv-planner.netlify.app/";
        public const string UrlGitHub = "https://github.com/jeff6540/hangar-fs2024";

        // mêmes fichiers de réglages que la version Python : on retrouve tout tel quel
        public static readonly string BaseDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "HangarFS2024");
        public static string ConfigFile { get { return Path.Combine(BaseDir, "config.json"); } }
        public static string StateFile { get { return Path.Combine(BaseDir, "state.json"); } }
    }

    static class JsonStore
    {
        public static JObject Load(string path, JObject defaults)
        {
            var data = (JObject)defaults.DeepClone();
            try
            {
                if (File.Exists(path))
                {
                    var loaded = JObject.Parse(File.ReadAllText(path, Encoding.UTF8));
                    foreach (var p in loaded.Properties())
                        data[p.Name] = p.Value;
                }
            }
            catch (Exception) { }
            return data;
        }

        public static void Save(string path, JObject data)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string tmp = path + ".tmp";
            File.WriteAllText(tmp, data.ToString(Formatting.Indented), new UTF8Encoding(false));
            if (File.Exists(path))
                File.Replace(tmp, path, null);
            else
                File.Move(tmp, path);
        }

        public static string Str(JToken t)
        {
            if (t == null || t.Type == JTokenType.Null || t.Type == JTokenType.Object || t.Type == JTokenType.Array)
                return "";
            // nombres toujours au format international (44.5), quel que soit le réglage de Windows (44,5 en français)
            var v = t as JValue;
            if (v != null && v.Value is IFormattable && !(v.Value is DateTime) && !(v.Value is DateTimeOffset))
                return ((IFormattable)v.Value).ToString(null, CultureInfo.InvariantCulture);
            return t.ToString();
        }
    }

    class Pkg
    {
        public string FullPath = "";
        public string Name = "";
        public string Title = "";
        public string Type = "";
        public string Creator = "";
        public string Version = "";
        public List<string> Icao = new List<string>();
        public List<string> IcaoAuto = new List<string>();
        public bool Pinned;
        public string Group = "";
    }

    static class Scanner
    {
        public const string QuarName = "_Quarantaine";
        static readonly HashSet<char> ValidFirst = new HashSet<char>("ABCDEFGHKLMNOPRSTUVWYZ");
        static readonly HashSet<string> Stop = new HashSet<string>((
            "MSFS MSFT PACK BETA FREE LIVE MESH LODS DEMO FULL LITE TEST MODS PATH CORE LIBS " +
            "DATA TEXT FILE MAIN BASE CITY PARK LAKE PORT ISLE WEST EAST HELI AREA ROAD TREE " +
            "LAND MODE GATE SIGN OBJS HIGH NEWS PLUS SIMS ANIM BLDG LIBR MATS TEXS GRAS ROCK " +
            "SNOW SAND HILL ZONE PADS POLY MISC GLOB COMM AIRP APRT HANG SHED WALL FENC LAMP " +
            "LGTS ROOF TAXI APRO VEHI CARS BOAT SHIP PLAN STAT EDIT TERR ELEV " +
            "VDGS MIDI USAW AVTO JETW SAFE DOCK PAPI VASI RAMP RUNW LINE POLE WIRE POWR SOLA FARM " +
            "FIRE TOWN LOGO MARK PEOP CREW GRND AIRS LIVR").Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries));
        static readonly Regex Token = new Regex("[A-Za-z0-9]+");

        public static readonly string[] AirportWords = { "airport", "aeroport", "aéroport", "airfield", "airstrip",
            "aerodrome", "aérodrome", "airbase", "heliport", "intl", "international" };
        static readonly string[] DecorWords = { "powerline", "power line", "pylon", "pylone", "pylône", "solar",
            "solaire", "wind", "eolien", "éolien", "turbine", "farm", "landmark", "bridge", "trees", "forest",
            "foret", "forêt", "vegetation", "végétation", "lights", "lighting", "lumiere", "lumière", "mesh",
            "ortho", "season", "saison", "library", "librairie", "objects", "objets", "traffic", "trafic",
            "building", "batiment", "bâtiment", "cloud", "weather", "texture", "environment", "railway", "patch",
            "liveries", "livery", "roads" };
        static readonly HashSet<string> DecorExact = new HashSet<string> { "poi", "pois", "lift", "lifts", "lib",
            "libs", "fix", "fixes", "pack", "packs" };

        static bool IsAsciiLetters(string t)
        {
            foreach (char c in t)
                if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z'))) return false;
            return true;
        }

        public static List<string> Tokens4(string text, bool upperOnly = false)
        {
            var result = new List<string>();
            foreach (Match m in Token.Matches(text ?? ""))
            {
                string t = m.Value;
                if (t.Length != 4 || !IsAsciiLetters(t)) continue;
                if (upperOnly && t != t.ToUpperInvariant()) continue;
                string u = t.ToUpperInvariant();
                if (ValidFirst.Contains(u[0]) && !Stop.Contains(u)) result.Add(u);
            }
            return result;
        }

        public static string NormDir(string p)
        {
            return Path.GetFullPath(p).TrimEnd('\\', '/');
        }

        // Un paquet MSFS = un dossier contenant manifest.json
        public static List<string> FindPackages(string lib, int maxDepth = 4)
        {
            var pkgs = new List<string>();
            lib = NormDir(lib);
            Walk(lib, lib, 0, maxDepth, pkgs);
            return pkgs;
        }

        static void Walk(string dir, string lib, int depth, int maxDepth, List<string> pkgs)
        {
            if (dir != lib && File.Exists(Path.Combine(dir, "manifest.json")))
            {
                pkgs.Add(dir);
                return;
            }
            if (depth >= maxDepth) return;
            string[] subs;
            try { subs = Directory.GetDirectories(dir); }
            catch (Exception) { return; }
            Array.Sort(subs, StringComparer.OrdinalIgnoreCase);
            foreach (var s in subs)
            {
                if (Path.GetFileName(s) == QuarName) continue;
                Walk(s, lib, depth + 1, maxDepth, pkgs);
            }
        }

        public static Pkg ScanPackage(string path, string lib)
        {
            var p = new Pkg { FullPath = path, Name = Path.GetFileName(path) };
            try
            {
                var m = JObject.Parse(File.ReadAllText(Path.Combine(path, "manifest.json"), Encoding.UTF8));
                p.Title = JsonStore.Str(m["title"]);
                p.Type = JsonStore.Str(m["content_type"]).ToUpperInvariant();
                p.Creator = JsonStore.Str(m["creator"]);
                p.Version = JsonStore.Str(m["package_version"]).Trim();
            }
            catch (Exception) { }

            if (p.Type == "SCENERY" || p.Type == "")
            {
                var found = Tokens4(p.Name);
                found.AddRange(Tokens4(p.Title, true));
                if (found.Count == 0)   // les fichiers BGL ne servent que si le nom et le titre ne disent rien
                {
                    int n = 0;
                    try
                    {
                        foreach (var f in Directory.EnumerateFiles(path, "*.bgl", SearchOption.AllDirectories))
                        {
                            found.AddRange(Tokens4(Path.GetFileNameWithoutExtension(f)));
                            if (++n > 3000) break;
                        }
                    }
                    catch (Exception) { }
                }
                var seen = new List<string>();
                foreach (var x in found)
                    if (!seen.Contains(x)) seen.Add(x);
                string vendor = Regex.Split(p.Name, "[-_ .]+")[0].ToUpperInvariant();
                if (seen.Count > 1 && seen.Contains(vendor)) seen.Remove(vendor);
                p.Icao = seen;
            }
            // groupe = sous-dossier de la bibliothèque (AVIONS, AEROPORTS FRANCAIS…)
            try
            {
                string parent = Path.GetDirectoryName(path);
                string libN = NormDir(lib);
                if (parent.Length > libN.Length && parent.StartsWith(libN, StringComparison.OrdinalIgnoreCase))
                    p.Group = parent.Substring(libN.Length).TrimStart('\\', '/');
            }
            catch (Exception) { }
            return p;
        }

        public static bool IsDecorPack(string text)
        {
            string t = text.ToLowerInvariant();
            if (AirportWords.Any(w => t.Contains(w))) return false;
            if (DecorWords.Any(w => t.Contains(w))) return true;
            foreach (Match m in Regex.Matches(t, "[a-zà-ÿ]+"))
                if (DecorExact.Contains(m.Value)) return true;
            return false;
        }

        // Empreinte légère (dates des dossiers sur 2 niveaux) pour voir si la bibliothèque a changé
        public static string LibSignature(string lib)
        {
            if (string.IsNullOrEmpty(lib) || !Directory.Exists(lib)) return null;
            var sb = new StringBuilder();
            try
            {
                sb.Append(Directory.GetLastWriteTimeUtc(lib).Ticks).Append('|');
                var l1 = Directory.GetDirectories(lib);
                Array.Sort(l1, StringComparer.OrdinalIgnoreCase);
                foreach (var d in l1)
                {
                    sb.Append(Path.GetFileName(d)).Append('=').Append(Directory.GetLastWriteTimeUtc(d).Ticks).Append('|');
                    try
                    {
                        var l2 = Directory.GetDirectories(d);
                        Array.Sort(l2, StringComparer.OrdinalIgnoreCase);
                        foreach (var d2 in l2)
                            sb.Append(Path.GetFileName(d)).Append('/').Append(Path.GetFileName(d2)).Append('=')
                              .Append(Directory.GetLastWriteTimeUtc(d2).Ticks).Append('|');
                    }
                    catch (Exception) { }
                }
            }
            catch (Exception) { return null; }
            return sb.ToString();
        }

        // Lit UserCfg.opt (MSFS 2024 puis 2020, Store puis Steam) pour trouver Community
        public static string DetectCommunity()
        {
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            var candidates = new[] {
                Path.Combine(local, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "UserCfg.opt"),
                Path.Combine(roaming, "Microsoft Flight Simulator 2024", "UserCfg.opt"),
                Path.Combine(local, "Packages", "Microsoft.FlightSimulator_8wekyb3d8bbwe", "LocalCache", "UserCfg.opt"),
                Path.Combine(roaming, "Microsoft Flight Simulator", "UserCfg.opt"),
            };
            foreach (var opt in candidates)
            {
                try
                {
                    if (!File.Exists(opt)) continue;
                    foreach (var raw in File.ReadAllLines(opt))
                    {
                        string line = raw.Trim();
                        if (!line.StartsWith("InstalledPackagesPath")) continue;
                        var parts = line.Split(new[] { ' ', '\t' }, 2, StringSplitOptions.RemoveEmptyEntries);
                        if (parts.Length < 2) continue;
                        string comm = Path.Combine(parts[1].Trim().Trim('"'), "Community");
                        if (Directory.Exists(comm)) return Path.GetFullPath(comm);
                    }
                }
                catch (Exception) { }
            }
            return "";
        }

        public static bool Inside(string child, string parent)
        {
            try
            {
                string c = NormDir(child) + "\\";
                string p = NormDir(parent) + "\\";
                return c.StartsWith(p, StringComparison.OrdinalIgnoreCase);
            }
            catch (Exception) { return false; }
        }

        public static bool SamePath(string a, string b)
        {
            if (string.IsNullOrEmpty(a) || string.IsNullOrEmpty(b)) return false;
            try { return string.Equals(NormDir(a), NormDir(b), StringComparison.OrdinalIgnoreCase); }
            catch (Exception) { return false; }
        }
    }

    // ------------------------------------------------------------------ jonctions (liens) dans Community
    static class Links
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr sec,
            uint disposition, uint flags, IntPtr template);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool DeviceIoControl(SafeFileHandle h, uint code, IntPtr inBuf, int inSize,
            byte[] outBuf, int outSize, out int returned, IntPtr overlapped);

        const uint FSCTL_GET_REPARSE_POINT = 0x000900A8;
        const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
        const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;
        const uint IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003;
        const uint IO_REPARSE_TAG_SYMLINK = 0xA000000C;

        public static bool Lexists(string path)
        {
            try { File.GetAttributes(path); return true; }
            catch (Exception) { return false; }
        }

        public static bool IsLink(string path)
        {
            try { return (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0 && LinkTarget(path) != ""; }
            catch (Exception) { return false; }
        }

        public static string LinkTarget(string path)
        {
            try
            {
                using (var h = CreateFile(path, 0, 7, IntPtr.Zero, 3,
                    FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, IntPtr.Zero))
                {
                    if (h.IsInvalid) return "";
                    var buf = new byte[16 * 1024];
                    int ret;
                    if (!DeviceIoControl(h, FSCTL_GET_REPARSE_POINT, IntPtr.Zero, 0, buf, buf.Length, out ret, IntPtr.Zero))
                        return "";
                    uint tag = BitConverter.ToUInt32(buf, 0);
                    int pathBuf;
                    if (tag == IO_REPARSE_TAG_MOUNT_POINT) pathBuf = 16;
                    else if (tag == IO_REPARSE_TAG_SYMLINK) pathBuf = 20;
                    else return "";
                    int subOff = BitConverter.ToUInt16(buf, 8), subLen = BitConverter.ToUInt16(buf, 10);
                    string t = Encoding.Unicode.GetString(buf, pathBuf + subOff, subLen);
                    if (t.StartsWith(@"\??\")) t = t.Substring(4);
                    if (t.StartsWith(@"\\?\")) t = t.Substring(4);
                    if (tag == IO_REPARSE_TAG_SYMLINK && (BitConverter.ToUInt32(buf, 16) & 1) != 0)
                        t = Path.GetFullPath(Path.Combine(Path.GetDirectoryName(path), t));   // lien relatif
                    return t;
                }
            }
            catch (Exception) { return ""; }
        }

        // le lien existe ET sa cible aussi (sinon : lien cassé)
        public static bool TargetExists(string path)
        {
            if (!IsLink(path)) return Directory.Exists(path);
            string t = LinkTarget(path);
            return t != "" && Directory.Exists(t);
        }

        public static void MakeLink(string target, string link)
        {
            var psi = new ProcessStartInfo("cmd.exe", "/c mklink /J \"" + link + "\" \"" + target + "\"")
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            try
            {
                var oem = Encoding.GetEncoding(CultureInfo.CurrentCulture.TextInfo.OEMCodePage);
                psi.StandardOutputEncoding = oem;
                psi.StandardErrorEncoding = oem;
            }
            catch (Exception) { }
            using (var p = Process.Start(psi))
            {
                string o = p.StandardOutput.ReadToEnd();
                string e = p.StandardError.ReadToEnd();
                p.WaitForExit(20000);
                if (p.ExitCode != 0)
                {
                    string msg = (e + " " + o).Trim();
                    throw new IOException(msg != "" ? msg : "mklink a échoué");
                }
            }
        }

        public static void RemoveLink(string link)
        {
            if (!Lexists(link)) return;
            if (!IsLink(link))
                throw new IOException(Hangar.L("refus : c'est un vrai dossier, pas un lien",
                                               "refused: this is a real folder, not a link"));
            Directory.Delete(link, false);   // retire la jonction, pas le contenu de la cible
        }
    }

    // ------------------------------------------------------------------ SimBrief
    static class SimBrief
    {
        static readonly string[][] Roles = {
            new[] { "origin", "Départ", "1" },
            new[] { "destination", "Arrivée", "1" },
            new[] { "alternate", "Dégagement", "0" },
            new[] { "takeoff_altn", "Dégagement décollage", "0" },
            new[] { "enroute_altn", "Dégagement en route", "0" },
        };

        static IEnumerable<JObject> AsList(JToken x)
        {
            if (x is JArray)
            {
                foreach (var o in (JArray)x)
                    if (o is JObject) yield return (JObject)o;
            }
            else if (x is JObject) yield return (JObject)x;
        }

        public static JObject Parse(JObject data)
        {
            var fetch = data["fetch"] as JObject;
            string status = fetch != null ? JsonStore.Str(fetch["status"]) : "";
            if (status != "" && status.ToLowerInvariant() != "success")
                throw new Exception("SimBrief : " + status);
            var airports = new JArray();
            var seen = new HashSet<string>();
            foreach (var r in Roles)
            {
                foreach (var o in AsList(data[r[0]]))
                {
                    string code = JsonStore.Str(o["icao_code"]).Trim().ToUpperInvariant();
                    if (code.Length == 4 && seen.Add(code))
                        airports.Add(new JObject { ["role"] = r[1], ["icao"] = code,
                            ["name"] = JsonStore.Str(o["name"]), ["primary"] = r[2] == "1" });
                }
            }
            if (airports.Count == 0)
                throw new Exception(Hangar.L("Aucun aéroport trouvé dans le plan de vol.", "No airport found in the flight plan."));
            var gen = data["general"] as JObject ?? new JObject();
            var ac = data["aircraft"] as JObject ?? new JObject();
            var prm = data["params"] as JObject ?? new JObject();
            long generated = 0;
            double g;
            if (double.TryParse(JsonStore.Str(prm["time_generated"]), NumberStyles.Float, CultureInfo.InvariantCulture, out g))
                generated = (long)g;
            string ofp = JsonStore.Str(prm["request_id"]);
            if (ofp.Length > 40) ofp = ofp.Substring(0, 40);
            string acName = JsonStore.Str(ac["icaocode"]);
            if (acName == "") acName = JsonStore.Str(ac["name"]);
            var route = string.Join(" → ", airports.Where(a => (bool)a["primary"]).Select(a => (string)a["icao"]));
            return new JObject
            {
                ["ofp_id"] = ofp,
                ["generated"] = generated,
                ["airports"] = airports,
                ["flight"] = (JsonStore.Str(gen["icao_airline"]) + JsonStore.Str(gen["flight_number"])).Trim(),
                ["aircraft"] = acName,
                ["route"] = route,
            };
        }

        public static JObject Fetch(string user)
        {
            user = (user ?? "").Trim();
            if (user == "")
                throw new Exception(Hangar.L("Indique ton identifiant SimBrief (nom d'utilisateur ou Pilot ID).",
                                             "Enter your SimBrief ID (username or Pilot ID)."));
            string key = user.All(char.IsDigit) ? "userid" : "username";
            string url = "https://www.simbrief.com/api/xml.fetcher.php?" + key + "=" + Uri.EscapeDataString(user) + "&json=1";
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            string body;
            try
            {
                var req = (HttpWebRequest)WebRequest.Create(url);
                req.UserAgent = AppInfo.Name + "/" + AppInfo.Version;
                req.Timeout = 20000;
                using (var resp = req.GetResponse())
                using (var sr = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                    body = sr.ReadToEnd();
            }
            catch (WebException e)
            {
                if (e.Response == null)
                    throw new Exception(Hangar.L("Impossible de joindre SimBrief (", "Unable to reach SimBrief (") + e.Message + ").");
                using (var sr = new StreamReader(e.Response.GetResponseStream(), Encoding.UTF8))
                    body = sr.ReadToEnd();
            }
            JObject data;
            try { data = JObject.Parse(body); }
            catch (Exception) { throw new Exception(Hangar.L("Réponse SimBrief illisible.", "Unreadable SimBrief response.")); }
            return Parse(data);
        }
    }
}
