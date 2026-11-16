// Base des aéroports OurAirports (téléchargée une fois, rafraîchie tous les 30 jours) : positions pour la carte,
// vérification des codes OACI des scènes et détection de l'avion au parking.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;

namespace HangarFS2024
{
    class AirportRec
    {
        public string Name = "", Type = "", Country = "", City = "";
        public double Lat, Lon;
    }

    static class Airports
    {
        static readonly string[] Urls = { "https://davidmegginson.github.io/ourairports-data/airports.csv", "https://ourairports.com/data/airports.csv" };
        public static string FilePath { get { return Path.Combine(AppInfo.BaseDir, "airports.csv"); } }
        static readonly HashSet<string> Generic = new HashSet<string> { "airport", "aeroport", "international", "intl", "airfield", "aerodrome", "scenery", "msfs",
            "the", "and", "de", "du", "la", "le", "les", "des", "et", "city", "int", "regional", "region", "airports", "pack", "airbase", "heliport", "altiport", "airstrip", "field" };
        static readonly Dictionary<string, int> TypeRank = new Dictionary<string, int> { { "large_airport", 0 }, { "medium_airport", 1 }, { "small_airport", 2 },
            { "heliport", 3 }, { "seaplane_base", 4 }, { "balloonport", 5 } };

        public static void Download()
        {
            Exception last = null;
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            foreach (var url in Urls)
            {
                try
                {
                    byte[] data;
                    using (var wc = new WebClient())
                    {
                        wc.Headers[HttpRequestHeader.UserAgent] = AppInfo.Name + "/" + AppInfo.Version;
                        data = wc.DownloadData(url);
                    }
                    string head = Encoding.ASCII.GetString(data, 0, Math.Min(4, data.Length));
                    if (data.Length < 1000000 || !(head.StartsWith("\"id\"") || head.StartsWith("id")))
                        throw new Exception(Hangar.L("fichier inattendu", "unexpected file"));
                    Directory.CreateDirectory(AppInfo.BaseDir);
                    File.WriteAllBytes(FilePath + ".tmp", data);
                    if (File.Exists(FilePath)) File.Delete(FilePath);
                    File.Move(FilePath + ".tmp", FilePath);
                    return;
                }
                catch (Exception e) { last = e; }
            }
            throw new Exception(Hangar.L("téléchargement impossible (", "download failed (") + (last != null ? last.Message : "") + ")");
        }

        static List<string> ParseCsvLine(string line)
        {
            var res = new List<string>();
            var sb = new StringBuilder();
            bool q = false;
            for (int i = 0; i < line.Length; i++)
            {
                char c = line[i];
                if (q)
                {
                    if (c == '"') { if (i + 1 < line.Length && line[i + 1] == '"') { sb.Append('"'); i++; } else q = false; }
                    else sb.Append(c);
                }
                else if (c == '"') q = true;
                else if (c == ',') { res.Add(sb.ToString()); sb.Clear(); }
                else sb.Append(c);
            }
            res.Add(sb.ToString());
            return res;
        }

        public static Dictionary<string, AirportRec> Load()
        {
            bool fresh = File.Exists(FilePath) && (DateTime.UtcNow - File.GetLastWriteTimeUtc(FilePath)).TotalDays < 30;
            if (!fresh)
            {
                try { Download(); }
                catch (Exception) { if (!File.Exists(FilePath)) throw; }
            }
            var db = new Dictionary<string, AirportRec>();
            using (var sr = new StreamReader(FilePath, Encoding.UTF8))
            {
                var header = ParseCsvLine(sr.ReadLine() ?? "");
                Func<string, int> col = n => header.IndexOf(n);
                int iLat = col("latitude_deg"), iLon = col("longitude_deg"), iName = col("name"), iType = col("type"), iCountry = col("iso_country"),
                    iCity = col("municipality"), iIcao = col("icao_code"), iGps = col("gps_code"), iIdent = col("ident");
                string line;
                while ((line = sr.ReadLine()) != null)
                {
                    // un nom peut contenir un retour à la ligne entre guillemets
                    while (line.Count(ch => ch == '"') % 2 == 1) { string more = sr.ReadLine(); if (more == null) break; line += "\n" + more; }
                    var r = ParseCsvLine(line);
                    Func<int, string> get = i => i >= 0 && i < r.Count ? r[i] : "";
                    double lat, lon;
                    if (!double.TryParse(get(iLat), NumberStyles.Float, CultureInfo.InvariantCulture, out lat)
                        || !double.TryParse(get(iLon), NumberStyles.Float, CultureInfo.InvariantCulture, out lon)) continue;
                    var rec = new AirportRec { Name = get(iName), Type = get(iType), Lat = lat, Lon = lon, Country = get(iCountry), City = get(iCity) };
                    foreach (int k in new[] { iIcao, iGps, iIdent })
                    {
                        string code = get(k).Trim().ToUpperInvariant();
                        AirportRec cur;
                        if (code != "" && (!db.TryGetValue(code, out cur) || (cur.Type == "closed" && rec.Type != "closed"))) db[code] = rec;
                    }
                }
            }
            return db;
        }

        public static HashSet<string> TextWords(string text)
        {
            string t = (text ?? "").Normalize(NormalizationForm.FormKD);
            var sb = new StringBuilder();
            foreach (char c in t) if (c < 128) sb.Append(c);
            var set = new HashSet<string>();
            foreach (Match m in Regex.Matches(sb.ToString().ToLowerInvariant(), "[a-z]+"))
                if (m.Value.Length >= 3 && !Generic.Contains(m.Value)) set.Add(m.Value);
            return set;
        }

        static bool IsAlpha(string s) { foreach (char c in s) if (!char.IsLetter(c)) return false; return true; }

        public static Dictionary<string, List<KeyValuePair<string, AirportRec>>> CityIndex(Dictionary<string, AirportRec> db)
        {
            var idx = new Dictionary<string, List<KeyValuePair<string, AirportRec>>>();
            foreach (var kv in db)
            {
                if (kv.Key.Length != 4 || !IsAlpha(kv.Key) || !TypeRank.ContainsKey(kv.Value.Type)) continue;
                var w = TextWords(kv.Value.City);
                if (w.Count != 1) continue;
                string word = w.First();
                List<KeyValuePair<string, AirportRec>> l;
                if (!idx.TryGetValue(word, out l)) { l = new List<KeyValuePair<string, AirportRec>>(); idx[word] = l; }
                l.Add(kv);
            }
            return idx;
        }

        static double Km(double lat1, double lon1, double lat2, double lon2)
        {
            double la1 = lat1 * Math.PI / 180, la2 = lat2 * Math.PI / 180, dla = la2 - la1, dlo = (lon2 - lon1) * Math.PI / 180;
            double h = Math.Pow(Math.Sin(dla / 2), 2) + Math.Cos(la1) * Math.Cos(la2) * Math.Pow(Math.Sin(dlo / 2), 2);
            return 12742 * Math.Asin(Math.Min(1, Math.Sqrt(h)));
        }

        // pack de plusieurs aéroports : écarte les codes égarés, loin de la zone du pack
        public static List<string> DropStray(List<string> codes, Dictionary<string, AirportRec> db)
        {
            if (codes.Count < 5) return codes;
            var known = codes.Where(db.ContainsKey).Select(c => new KeyValuePair<string, AirportRec>(c, db[c])).ToList();
            if (known.Count < 4) return codes;
            var lats = known.Select(k => k.Value.Lat).OrderBy(x => x).ToList();
            var lons = known.Select(k => k.Value.Lon).OrderBy(x => x).ToList();
            double clat = lats[lats.Count / 2], clon = lons[lons.Count / 2];
            var dist = known.ToDictionary(k => k.Key, k => Km(clat, clon, k.Value.Lat, k.Value.Lon));
            var sorted = dist.Values.OrderBy(x => x).ToList();
            double med = sorted[sorted.Count / 2], limit = Math.Max(1500, 4 * med);
            var near = new HashSet<string>(dist.Where(kv => kv.Value <= limit).Select(kv => kv.Key));
            var letters = new HashSet<char>(near.Select(c => c[0]));
            var keep = codes.Where(c => near.Contains(c) || (!db.ContainsKey(c) && c.Length > 0 && letters.Contains(c[0]))).ToList();
            return keep.Count > 0 ? keep : codes;
        }

        // garde les codes dont l'aéroport correspond au nom de l'add-on ; sinon cherche par la ville citée
        public static List<string> ResolveCodes(List<string> codes, string text, Dictionary<string, AirportRec> db,
            Dictionary<string, List<KeyValuePair<string, AirportRec>>> cityIdx)
        {
            if (codes.Count >= 10) return DropStray(codes, db);
            var words = TextWords(text);
            var near = new HashSet<string>(DropStray(codes, db));
            var matched = new List<string>();
            foreach (var c in codes)
            {
                AirportRec rec;
                if (!near.Contains(c) || !db.TryGetValue(c, out rec)) continue;
                var w2 = new HashSet<string>(words); w2.Remove(c.ToLowerInvariant());
                if (TextWords(rec.City + " " + rec.Name).Overlaps(w2)) matched.Add(c);
            }
            if (matched.Count > 0) return matched;
            int bestRank = int.MaxValue; string best = null;
            foreach (var w in words)
            {
                List<KeyValuePair<string, AirportRec>> l;
                if (!cityIdx.TryGetValue(w, out l)) continue;
                foreach (var kv in l)
                {
                    if (kv.Key.ToLowerInvariant() == w) continue;
                    int r;
                    if (!TypeRank.TryGetValue(kv.Value.Type, out r)) r = 9;
                    if (best == null || r < bestRank) { bestRank = r; best = kv.Key; }
                }
            }
            if (best != null) return new List<string> { best };
            return DropStray(codes, db);
        }

        // aéroport le plus proche à moins de maxKm (ou null)
        public static string Nearest(Dictionary<string, AirportRec> db, double lat, double lon, double maxKm)
        {
            string best = null; double bestD = maxKm, dlat = maxKm / 111.0, coslat = Math.Max(0.05, Math.Cos(lat * Math.PI / 180));
            foreach (var kv in db)
            {
                var r = kv.Value;
                if (Math.Abs(r.Lat - lat) > dlat || (kv.Key.Length != 3 && kv.Key.Length != 4)) continue;
                double dx = (r.Lon - lon) * 111.0 * coslat;
                if (Math.Abs(dx) > maxKm) continue;
                double d = Math.Sqrt(Math.Pow((r.Lat - lat) * 111.0, 2) + dx * dx);
                if (d < bestD && (r.Type == "large_airport" || r.Type == "medium_airport" || r.Type == "small_airport" || r.Type == "heliport" || r.Type == "seaplane_base"))
                { best = kv.Key; bestD = d; }
            }
            return best;
        }
    }
}
