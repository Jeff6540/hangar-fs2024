// 12.9 : données de navigation de MSFS (points RNAV, VOR, ILS, NDB, approches) importées une fois par SimConnect,
// gardées dans le dossier des réglages, puis servies à la page « Plan VFR » simulateur éteint.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class NavData
    {
        public static string Dir { get { return Path.Combine(AppInfo.BaseDir, "navdata"); } }
        static readonly object Gate = new object();
        static JObject status = new JObject { ["state"] = "idle" };
        static Thread worker;
        static volatile bool stopAsked;

        // ------------------------------------------------------------ état de l'import
        public static JObject Status()
        {
            lock (Gate)
            {
                var s = (JObject)status.DeepClone();
                var meta = Meta();
                if (meta != null) s["meta"] = meta;
                return s;
            }
        }
        static void Set(string state, string step, int done = 0, int total = 0, string msg = null)
        {
            lock (Gate) status = new JObject { ["state"] = state, ["step"] = step, ["done"] = done, ["total"] = total, ["msg"] = msg };
        }
        static JObject Meta()
        {
            try { string f = Path.Combine(Dir, "meta.json"); return File.Exists(f) ? JObject.Parse(File.ReadAllText(f)) : null; } catch (Exception) { return null; }
        }

        public static void Start(string dll, bool simRunning)
        {
            lock (Gate)
            {
                if (worker != null && worker.IsAlive) return;
                if (!simRunning) { Set("error", "", msg: Hangar.L("Lance d'abord MSFS 2024 (jusqu'au menu principal), puis recommence.", "Start MSFS 2024 first (up to the main menu), then try again.")); return; }
                if (string.IsNullOrEmpty(dll)) { Set("error", "", msg: Hangar.L("SimConnect.dll introuvable.", "SimConnect.dll not found.")); return; }
                stopAsked = false;
                Set("run", "open");
                worker = new Thread(() => Run(dll)) { IsBackground = true, Name = "navdata" };
                worker.Start();
            }
        }
        public static void Stop() { stopAsked = true; }

        // ------------------------------------------------------------ import
        const uint REQ_APT = 1, REQ_WPT = 2, REQ_NDB = 3, REQ_VOR = 4, DEF_APPR = 100, REQ_BASE = 1000;

        static void Run(string dll)
        {
            var c = new SimConnectClient();
            try
            {
                if (!SimConnectClient.Load(dll) || !SimConnectClient.LoadNav())
                    throw new Exception(Hangar.L("La SimConnect.dll trouvée est trop ancienne pour lire les données de navigation. Installe le SDK de MSFS 2024, ou copie la SimConnect.dll du SDK 2024 à côté de l'appli.",
                                                 "The SimConnect.dll found is too old to read navigation data. Install the MSFS 2024 SDK, or copy the 2024 SDK SimConnect.dll next to the app."));
                c.Open("Hangar FS 2024 navdata");
                Directory.CreateDirectory(Dir);
                var tmp = Path.Combine(Dir, "tmp"); Directory.CreateDirectory(tmp);

                // 1) listes mondiales
                var apts = List(c, 0, REQ_APT, "airports");
                var wpts = SimConnectClient.HasAll ? List(c, 1, REQ_WPT, "waypoints") : new List<object[]>();
                var vors = SimConnectClient.HasAll ? List(c, 3, REQ_VOR, "vors") : new List<object[]>();
                var ndbs = SimConnectClient.HasAll ? List(c, 2, REQ_NDB, "ndbs") : new List<object[]>();
                if (apts.Count == 0) throw new Exception(Hangar.L("MSFS n'a renvoyé aucun aéroport. Attends d'être au menu principal du simulateur, puis recommence.",
                                                                  "MSFS returned no airport. Wait until you are at the simulator's main menu, then try again."));

                // 2) approches, aéroport par aéroport
                var appr = Approaches(c, apts);

                Write(Path.Combine(tmp, "waypoints.json"), wpts);
                Write(Path.Combine(tmp, "vors.json"), vors);
                Write(Path.Combine(tmp, "ndbs.json"), ndbs);
                File.WriteAllText(Path.Combine(tmp, "approaches.json"), appr.ToString(Formatting.None), new UTF8Encoding(false));
                int nAppr = appr.Properties().Sum(p => ((JArray)p.Value).Count);
                var meta = new JObject
                {
                    ["date"] = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture), ["airports"] = apts.Count, ["waypoints"] = wpts.Count,
                    ["vors"] = vors.Count(v => ((int)v[6] & 2) == 0), ["ils"] = vors.Count(v => ((int)v[6] & 2) != 0), ["ndbs"] = ndbs.Count, ["approaches"] = nAppr,
                };
                File.WriteAllText(Path.Combine(tmp, "meta.json"), meta.ToString(Formatting.None));
                foreach (var f in Directory.GetFiles(tmp))
                {
                    string dst = Path.Combine(Dir, Path.GetFileName(f));
                    if (File.Exists(dst)) File.Delete(dst);
                    File.Move(f, dst);
                }
                try { Directory.Delete(tmp, true); } catch (Exception) { }
                lock (Gate) { cache.Clear(); apprCache = null; }
                Set("done", "", msg: null);
            }
            catch (Exception e)
            {
                Set(stopAsked ? "idle" : "error", "", msg: stopAsked ? null : e.Message);
            }
            finally { c.Dispose(); }
        }

        static byte[] Wait(SimConnectClient c, ref DateTime last, int timeoutSec)
        {
            var b = c.Next();
            if (b != null) { last = DateTime.UtcNow; return b; }
            if (stopAsked) throw new Exception("stop");
            if ((DateTime.UtcNow - last).TotalSeconds > timeoutSec) throw new TimeoutException();
            Thread.Sleep(3);
            return null;
        }

        static string Txt(byte[] b, int off, int len)
        {
            int n = 0; while (n < len && off + n < b.Length && b[off + n] != 0) n++;
            return Encoding.ASCII.GetString(b, off, n).Trim();
        }

        /// <summary>Liste mondiale : [ident, région, lat, lon, (magvar), (fréq. Hz), (drapeaux), (cap du localizer)].</summary>
        static List<object[]> List(SimConnectClient c, int type, uint req, string step)
        {
            var res = new List<object[]>();
            Set("run", step, 0, 0);
            if (c.ReqAll(type, req) != 0) return res;
            uint got = 0, outOf = uint.MaxValue;
            var last = DateTime.UtcNow;
            int baseSize = type == 0 ? 24 : type == 1 ? 28 : type == 2 ? 32 : 68;
            while (got < outOf)
            {
                byte[] b;
                try { b = Wait(c, ref last, 60); } catch (TimeoutException) { break; }
                if (b == null || b.Length < 28) continue;
                uint id = BitConverter.ToUInt32(b, 8);
                if (id < 18 || id > 21 || BitConverter.ToUInt32(b, 12) != req) continue;
                uint n = BitConverter.ToUInt32(b, 16); outOf = BitConverter.ToUInt32(b, 24); got++;
                if (n == 0) continue;
                int es = (b.Length - 28) / (int)n, idreg = es - baseSize;
                if (idreg < 6) continue;
                int rl = idreg >= 9 ? 3 : 0, il = idreg - rl;
                for (int i = 0; i < n; i++)
                {
                    int o = 28 + i * es;
                    string ident = Txt(b, o, il), region = rl > 0 ? Txt(b, o + il, rl) : "";
                    int p = o + idreg;
                    double lat = BitConverter.ToDouble(b, p), lon = BitConverter.ToDouble(b, p + 8);
                    if (ident == "" || Math.Abs(lat) > 90 || Math.Abs(lon) > 180) continue;
                    lat = Math.Round(lat, 5); lon = Math.Round(lon, 5);
                    if (type == 0) res.Add(new object[] { ident, region, lat, lon });
                    else
                    {
                        double mv = Math.Round(BitConverter.ToSingle(b, p + 24), 1);
                        if (type == 1) res.Add(new object[] { ident, region, lat, lon, mv });
                        else
                        {
                            uint fq = BitConverter.ToUInt32(b, p + 28);
                            if (type == 2) res.Add(new object[] { ident, region, lat, lon, mv, fq });
                            else
                            {
                                int flags = (int)BitConverter.ToUInt32(b, p + 32);
                                double loc = Math.Round(BitConverter.ToSingle(b, p + 36), 1);
                                res.Add(new object[] { ident, region, lat, lon, mv, fq, flags, loc });
                            }
                        }
                    }
                }
                Set("run", step, res.Count, 0);
            }
            return res;
        }

        static readonly string[] ApprType = { "", "GPS", "VOR", "NDB", "ILS", "LOC", "SDF", "LDA", "VOR/DME", "NDB/DME", "RNAV", "LOC BC" };
        static readonly string[] Desig = { "", "L", "R", "C", "W", "A", "B" };

        static JObject Approaches(SimConnectClient c, List<object[]> apts)
        {
            // définition : approches de l'aéroport, avec leurs transitions et leurs branches finales (points et coordonnées)
            foreach (var f in new[] { "OPEN AIRPORT", "N_APPROACHES",
                "OPEN APPROACH", "TYPE", "SUFFIX", "RUNWAY_NUMBER", "RUNWAY_DESIGNATOR",
                "OPEN APPROACH_TRANSITION", "TYPE",
                "OPEN APPROACH_LEG", "TYPE", "FIX_ICAO", "FIX_REGION", "FIX_LATITUDE", "FIX_LONGITUDE", "CLOSE APPROACH_LEG",
                "CLOSE APPROACH_TRANSITION",
                "OPEN FINAL_APPROACH_LEG", "TYPE", "FIX_ICAO", "FIX_REGION", "FIX_LATITUDE", "FIX_LONGITUDE", "CLOSE FINAL_APPROACH_LEG",
                "CLOSE APPROACH", "CLOSE AIRPORT" })
                if (c.AddFac(DEF_APPR, f) != 0) throw new Exception(Hangar.L("MSFS refuse la demande d'approches (", "MSFS refuses the approach request (") + f + ")");

            var list = apts.Where(a => System.Text.RegularExpressions.Regex.IsMatch((string)a[0], "^[A-Z0-9]{3,4}$")).ToList();
            var outRes = new JObject();
            var pending = new Dictionary<uint, string>();
            var objs = new Dictionary<uint, JObject>();           // identifiant unique -> approche / transition
            var byReq = new Dictionary<uint, JArray>();           // requête -> approches de l'aéroport
            int next = 0, done = 0, total = list.Count;
            uint req = REQ_BASE;
            var last = DateTime.UtcNow;
            Set("run", "approaches", 0, total);
            while (done < total)
            {
                while (pending.Count < 24 && next < total)
                {
                    req++;
                    string icao = (string)list[next][0];
                    next++;
                    if (c.ReqFac(DEF_APPR, req, icao, "") == 0) { pending[req] = icao; byReq[req] = new JArray(); }
                    else done++;
                }
                byte[] b;
                try { b = Wait(c, ref last, 20); }
                catch (TimeoutException)
                {
                    // MSFS ne répond plus pour ces aéroports : on les passe
                    done += pending.Count; foreach (var k in pending.Keys) byReq.Remove(k); pending.Clear(); last = DateTime.UtcNow; continue;
                }
                if (b == null || b.Length < 16) continue;
                uint id = BitConverter.ToUInt32(b, 8);
                if (id == 29)          // fin des données d'un aéroport
                {
                    uint r = BitConverter.ToUInt32(b, 12);
                    string icao;
                    if (pending.TryGetValue(r, out icao))
                    {
                        pending.Remove(r); done++;
                        var arr = byReq[r]; byReq.Remove(r);
                        var clean = new JArray(arr.OfType<JObject>().Where(a => ((JArray)a["f"]).Count > 0).Select(a => { a.Remove("u"); foreach (var t in (JArray)a["tr"]) ((JObject)t).Remove("u"); a["tr"] = new JArray(((JArray)a["tr"]).Where(t => ((JArray)t["l"]).Count > 0)); return a; }));
                        if (clean.Count > 0) outRes[icao] = clean;
                        if (done % 50 == 0) Set("run", "approaches", done, total);
                    }
                    continue;
                }
                if (id == 1)          // exception : une demande refusée
                {
                    continue;
                }
                if (id != 28 || b.Length < 40) continue;
                uint ureq = BitConverter.ToUInt32(b, 12), uid = BitConverter.ToUInt32(b, 16), parent = BitConverter.ToUInt32(b, 20), dtype = BitConverter.ToUInt32(b, 24);
                JArray apList;
                if (!byReq.TryGetValue(ureq, out apList)) continue;
                const int D = 40;
                if (dtype == 5 && b.Length >= D + 16)       // approche
                {
                    int t = BitConverter.ToInt32(b, D), sfx = BitConverter.ToInt32(b, D + 4), rn = BitConverter.ToInt32(b, D + 8), rd = BitConverter.ToInt32(b, D + 12);
                    string rwy = rn >= 1 && rn <= 36 ? rn.ToString("00") + (rd >= 0 && rd < Desig.Length ? Desig[rd] : "") : "";
                    var a = new JObject { ["u"] = uid, ["t"] = t >= 0 && t < ApprType.Length ? ApprType[t] : "?", ["r"] = rwy,
                        ["s"] = sfx > 32 && sfx < 127 ? ((char)sfx).ToString() : "", ["f"] = new JArray(), ["tr"] = new JArray() };
                    objs[uid] = a; apList.Add(a);
                }
                else if (dtype == 6)                         // transition
                {
                    JObject a;
                    if (objs.TryGetValue(parent, out a)) { var t = new JObject { ["u"] = uid, ["l"] = new JArray() }; objs[uid] = t; ((JArray)a["tr"]).Add(t); }
                }
                else if ((dtype == 7 || dtype == 8) && b.Length >= D + 36)   // branche de transition / branche finale
                {
                    string fix = Txt(b, D + 4, 8);
                    double lat = BitConverter.ToDouble(b, D + 20), lon = BitConverter.ToDouble(b, D + 28);
                    int lt = BitConverter.ToInt32(b, D);
                    if (fix == "" || (lat == 0 && lon == 0) || Math.Abs(lat) > 90 || Math.Abs(lon) > 180) continue;
                    var leg = new JArray(fix, Math.Round(lat, 5), Math.Round(lon, 5), lt);
                    JObject o;
                    if (!objs.TryGetValue(parent, out o)) continue;
                    if (dtype == 8 && o["f"] != null) ((JArray)o["f"]).Add(leg);
                    else if (dtype == 7 && o["l"] != null) ((JArray)o["l"]).Add(leg);
                }
            }
            return outRes;
        }

        static void Write(string path, List<object[]> rows)
        {
            using (var w = new StreamWriter(path, false, new UTF8Encoding(false)))
            using (var j = new JsonTextWriter(w))
            {
                j.WriteStartArray();
                foreach (var r in rows) { j.WriteStartArray(); foreach (var v in r) j.WriteValue(v); j.WriteEndArray(); }
                j.WriteEndArray();
            }
        }

        // ------------------------------------------------------------ lecture (page Plan VFR)
        static readonly Dictionary<string, JArray> cache = new Dictionary<string, JArray>();
        static JObject apprCache;

        static JArray Load(string name)
        {
            lock (Gate)
            {
                JArray a;
                if (cache.TryGetValue(name, out a)) return a;
                string f = Path.Combine(Dir, name + ".json");
                try { a = File.Exists(f) ? JArray.Parse(File.ReadAllText(f)) : new JArray(); } catch (Exception) { a = new JArray(); }
                cache[name] = a;
                if (name == "approaches") apprCache = null;
                return a;
            }
        }

        /// <summary>Points dans un rectangle : k = wpt, vor, ils, ndb.</summary>
        public static JArray Query(string k, double s, double w, double n, double e, int max)
        {
            var src = Load(k == "wpt" ? "waypoints" : k == "ndb" ? "ndbs" : "vors");
            var res = new JArray();
            bool wrap = w > e;
            foreach (JArray r in src)
            {
                double lat = (double)r[2], lon = (double)r[3];
                if (lat < s || lat > n) continue;
                if (wrap ? (lon < w && lon > e) : (lon < w || lon > e)) continue;
                if (k == "vor" || k == "ils")
                {
                    bool ils = ((int)r[6] & 2) != 0;
                    if ((k == "ils") != ils) continue;
                }
                res.Add(r);
                if (res.Count >= max) break;
            }
            return res;
        }

        public static JToken Approaches(string icao)
        {
            lock (Gate)
            {
                if (apprCache == null)
                {
                    string f = Path.Combine(Dir, "approaches.json");
                    try { apprCache = File.Exists(f) ? JObject.Parse(File.ReadAllText(f)) : new JObject(); } catch (Exception) { apprCache = new JObject(); }
                }
                return apprCache[(icao ?? "").ToUpperInvariant()] ?? new JArray();
            }
        }
    }
}
