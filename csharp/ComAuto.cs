// FMS — COM auto : COM1 réglé selon la phase du vol, avec les fréquences des aéroports lues dans MSFS
// (données d'installations : AIRPORT > FREQUENCY, demandées à la volée pour le départ et l'arrivée du plan).
// À chaque nouvelle phase : la fréquence à utiliser en ACTIVE, la suivante en ATTENTE (le pilote n'a plus qu'à permuter).
// Le changement n'est fait qu'une fois par phase : si tu règles autre chose à la main, le FMS ne revient pas dessus.
// Arrêté par défaut (SayIntentions et autres ATC gèrent leurs fréquences eux-mêmes).
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class ComAuto
    {
        // types MSFS : 1 ATIS, 2 MULTICOM, 3 UNICOM, 4 CTAF, 5 GROUND, 6 TOWER, 7 CLEARANCE, 8 APPROACH, 9 DEPARTURE, 10 CENTER, 11 FSS, 12 AWOS, 13 ASOS, 14 CLEARANCE PRE TAXI, 15 REMOTE CLEARANCE
        public const uint DefFreq = 30, ReqBase = 9000000;
        public static readonly string[] FacFields = { "OPEN AIRPORT", "N_FREQUENCIES", "OPEN FREQUENCY", "TYPE", "FREQUENCY", "NAME", "CLOSE FREQUENCY", "CLOSE AIRPORT" };

        class Freq { public int Type; public int Hz; public string Name; }
        static readonly object Gate = new object();
        static readonly Dictionary<string, List<Freq>> byIcao = new Dictionary<string, List<Freq>>();
        static readonly Dictionary<uint, string> pending = new Dictionary<uint, string>();
        static readonly Dictionary<uint, List<Freq>> building = new Dictionary<uint, List<Freq>>();
        static readonly HashSet<string> asked = new HashSet<string>();
        static readonly ConcurrentQueue<string> toAsk = new ConcurrentQueue<string>();
        static uint nextReq = ReqBase;

        static bool auto;
        static string phase = "", lastPhase = "", actName = "", stbyName = "";
        static int actHz, stbyHz;
        static double nextCalc;
        static bool moved;   // l'avion a roulé depuis le parking (pour distinguer parking / roulage)

        public static void SetAuto(bool v) { lock (Gate) { auto = v; lastPhase = ""; } }

        // ---- demandes de fréquences (boucle SimConnect du relais)
        static void Need(string icao)
        {
            if (string.IsNullOrEmpty(icao) || icao.Length < 3) return;
            lock (Gate) { if (asked.Contains(icao)) return; asked.Add(icao); }
            toAsk.Enqueue(icao);
        }
        /// <summary>Aéroports à demander à MSFS : (requête, code OACI).</summary>
        public static List<KeyValuePair<uint, string>> TakeRequests()
        {
            var l = new List<KeyValuePair<uint, string>>();
            string icao;
            while (toAsk.TryDequeue(out icao))
                lock (Gate) { uint r = ++nextReq; pending[r] = icao; building[r] = new List<Freq>(); l.Add(new KeyValuePair<uint, string>(r, icao)); }
            return l;
        }
        public static void RequestFailed(uint req) { lock (Gate) { pending.Remove(req); building.Remove(req); } }

        static string Txt(byte[] b, int off, int len)
        {
            int n = 0; while (n < len && off + n < b.Length && b[off + n] != 0) n++;
            return System.Text.Encoding.ASCII.GetString(b, off, n).Trim();
        }
        /// <summary>Message 28 (données) ou 29 (fin) de SimConnect ; true s'il nous concernait.</summary>
        public static bool OnFacility(uint msgId, byte[] b)
        {
            if (b.Length < 16) return false;
            uint req = BitConverter.ToUInt32(b, 12);
            if (req <= ReqBase || req > ReqBase + 100000) return false;
            lock (Gate)
            {
                List<Freq> list;
                if (!building.TryGetValue(req, out list)) return true;
                if (msgId == 29)
                {
                    string icao = pending[req];
                    pending.Remove(req); building.Remove(req);
                    byIcao[icao] = list;
                    lastPhase = "";   // fréquences arrivées : réappliquer la phase en cours
                    return true;
                }
                const int D = 40;
                if (b.Length < D + 8 + 64 || BitConverter.ToUInt32(b, 24) != 3) return true;   // 3 = FREQUENCY
                int type = BitConverter.ToInt32(b, D), f = BitConverter.ToInt32(b, D + 4);
                long hz = f < 1000 ? f * 1000000L : f < 1000000 ? f * 1000L : f;
                if (hz >= 108000000 && hz <= 137000000) list.Add(new Freq { Type = type, Hz = (int)hz, Name = Txt(b, D + 8, 64) });
                return true;
            }
        }

        static Freq Pick(string icao, params int[] types)
        {
            List<Freq> l;
            if (icao == null || !byIcao.TryGetValue(icao, out l)) return null;
            foreach (int t in types) { var f = l.FirstOrDefault(x => x.Type == t); if (f != null) return f; }
            return null;
        }
        static readonly int[] ATIS = { 1, 12, 13 }, DEL = { 7, 14, 15 }, GND = { 5, 6, 4, 3, 2 }, TWR = { 6, 4, 3, 2 }, DEP = { 9, 8, 10 }, APP = { 8, 9, 10 };

        static double Dist(double la1, double lo1, double la2, double lo2) { return Lnav.Dist(la1, lo1, la2, lo2) * Lnav.EarthNm; }

        public static JObject Snapshot()
        {
            lock (Gate)
                return new JObject { ["auto"] = auto, ["phase"] = phase, ["act"] = actHz > 0 ? Math.Round(actHz / 1e6, 3) : 0, ["actName"] = actName,
                    ["stby"] = stbyHz > 0 ? Math.Round(stbyHz / 1e6, 3) : 0, ["stbyName"] = stbyName };
        }

        static string Label(Freq f, string icao) { return f == null ? "" : icao + " " + (string.IsNullOrEmpty(f.Name) ? "" : f.Name); }

        /// <summary>Appelé avec les valeurs du pilote auto (Autopilot.Fields).</summary>
        public static void Tick(double[] v, double now)
        {
            if (v == null || v.Length < 33) return;
            lock (Gate) { if (now < nextCalc) return; nextCalc = now + 2; }
            var plan = FlightStore.Get()["plan"] as JObject ?? new JObject();
            var route = plan["route"] as JArray;
            if (route == null || route.Count < 2) return;
            string org = JsonStore.Str(plan["origin"]?["icao"]), dst = JsonStore.Str(plan["dest"]?["icao"]);
            Need(org); Need(dst);
            lock (Gate)
            {
                double ola, olo, dla, dlo;
                if (!Lnav.Pt(route, 0, out ola, out olo) || !Lnav.Pt(route, route.Count - 1, out dla, out dlo)) return;
                bool ground = v[17] >= 0.5; double gs = v[22], agl = v[32], lat = v[20], lon = v[21];
                double dO = Dist(lat, lon, ola, olo), dD = Dist(lat, lon, dla, dlo);
                if (ground && dO < 3 && gs > 5) moved = true;

                // phase du vol et fréquences (active, attente)
                Freq a = null, s = null; string ai = org, si = org;
                if (ground && dD < 3 && dO > 3) { phase = "landed"; a = Pick(dst, GND); s = Pick(dst, TWR); ai = si = dst; }
                else if (ground && dO < 3 && !moved) { phase = "parked"; a = Pick(org, ATIS) ?? Pick(org, DEL) ?? Pick(org, GND); s = Pick(org, DEL) ?? Pick(org, GND); }
                else if (ground && dO < 3) { phase = "taxi"; a = Pick(org, GND); s = Pick(org, TWR); }
                else if (!ground && dD < 12 && agl < 3500) { phase = "final"; a = Pick(dst, TWR); s = Pick(dst, GND); ai = si = dst; }
                else if (!ground && dD < 40) { phase = "approach"; a = Pick(dst, APP) ?? Pick(dst, TWR); s = Pick(dst, TWR); ai = si = dst; }
                else if (!ground && dD < 80) { phase = "arrival"; s = Pick(dst, ATIS); si = dst; }
                else if (!ground && dO < 8 && agl < 3000) { phase = "takeoff"; a = Pick(org, TWR); s = Pick(org, DEP); }
                else if (!ground) { phase = "climb"; a = Pick(org, DEP); }
                else phase = "";
                if (!ground) moved = false;   // prochain vol : on repart de « parking »

                if (!auto || phase == "" || phase == lastPhase) return;
                lastPhase = phase;
                if (a != null) { Autopilot.Order("COM_RADIO_SET_HZ", a.Hz); actHz = a.Hz; actName = Label(a, ai); }
                if (s != null) { Autopilot.Order("COM_STBY_RADIO_SET_HZ", s.Hz); stbyHz = s.Hz; stbyName = Label(s, si); }
                if (a == null && s == null) { actHz = stbyHz = 0; actName = stbyName = ""; }
            }
        }
    }
}
