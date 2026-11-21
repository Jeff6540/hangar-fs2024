// FMS — pilote automatique, morceaux 1 et 2 : lire ce que l'avion sait faire, régler les consignes et les modes.
// Les ordres viennent de la fenêtre FMS (chrome.webview.postMessage({ ap: { c: "hdg", v: 1 } })) et sont envoyés
// à MSFS par la boucle SimConnect du relais (voir Relay.cs). L'état est lu deux fois par seconde (relais : /ap).
// Pour chaque mode, on essaie d'abord l'ordre « _ON / _OFF » ; si l'avion ne réagit pas, l'ordre « bascule » ;
// s'il ne réagit toujours pas, le mode est marqué « non géré par l'avion » (le FMS pourra le forcer plus tard).
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class Autopilot
    {
        // ---- variables lues dans MSFS (toutes en nombres à virgule, dans cet ordre)
        public static readonly string[][] Fields = {
            new[] { "AUTOPILOT AVAILABLE", "bool" },                 // 0
            new[] { "AUTOPILOT MASTER", "bool" },                    // 1
            new[] { "AUTOPILOT HEADING LOCK", "bool" },              // 2
            new[] { "AUTOPILOT HEADING LOCK DIR", "degrees" },       // 3
            new[] { "AUTOPILOT ALTITUDE LOCK", "bool" },             // 4
            new[] { "AUTOPILOT ALTITUDE LOCK VAR", "feet" },         // 5
            new[] { "AUTOPILOT VERTICAL HOLD", "bool" },             // 6
            new[] { "AUTOPILOT VERTICAL HOLD VAR", "feet per minute" }, // 7
            new[] { "AUTOPILOT AIRSPEED HOLD", "bool" },             // 8
            new[] { "AUTOPILOT AIRSPEED HOLD VAR", "knots" },        // 9
            new[] { "AUTOPILOT NAV1 LOCK", "bool" },                 // 10
            new[] { "AUTOPILOT APPROACH HOLD", "bool" },             // 11
            new[] { "AUTOPILOT GLIDESLOPE HOLD", "bool" },           // 12
            new[] { "PLANE HEADING DEGREES MAGNETIC", "degrees" },   // 13
            new[] { "INDICATED ALTITUDE", "feet" },                  // 14
            new[] { "VERTICAL SPEED", "feet per minute" },           // 15
            new[] { "AIRSPEED INDICATED", "knots" },                 // 16
            new[] { "SIM ON GROUND", "bool" },                       // 17
            new[] { "GPS GROUND TRUE TRACK", "degrees" },            // 18  (LNAV)
            new[] { "MAGVAR", "degrees" },                           // 19
            new[] { "PLANE LATITUDE", "degrees" },                   // 20
            new[] { "PLANE LONGITUDE", "degrees" },                  // 21
            new[] { "GROUND VELOCITY", "knots" },                    // 22
            new[] { "PLANE HEADING DEGREES TRUE", "degrees" },       // 23
            new[] { "NAV ACTIVE FREQUENCY:1", "MHz" },               // 24  (approche / ILS)
            new[] { "NAV STANDBY FREQUENCY:1", "MHz" },              // 25
            new[] { "GPS DRIVES NAV1", "bool" },                     // 26
            new[] { "NAV HAS LOCALIZER:1", "bool" },                 // 27
            new[] { "NAV CDI:1", "number" },                         // 28
            new[] { "NAV HAS GLIDE SLOPE:1", "bool" },               // 29
            new[] { "NAV ACTIVE FREQUENCY:2", "MHz" },               // 30  (liners : ILS aussi sur NAV2)
            new[] { "NAV STANDBY FREQUENCY:2", "MHz" },              // 31
            new[] { "PLANE ALT ABOVE GROUND", "feet" },              // 32  (COM auto : phases du vol)
        };

        // ---- ordres envoyés à MSFS (numéro d'ordre = 1000 + position dans la liste)
        public static readonly string[] Events = {
            "AUTOPILOT_ON", "AUTOPILOT_OFF", "AP_MASTER",
            "AP_HDG_HOLD_ON", "AP_HDG_HOLD_OFF", "AP_PANEL_HEADING_HOLD",
            "AP_ALT_HOLD_ON", "AP_ALT_HOLD_OFF", "AP_PANEL_ALTITUDE_HOLD",
            "AP_VS_ON", "AP_VS_OFF", "AP_PANEL_VS_HOLD",
            "AP_AIRSPEED_ON", "AP_AIRSPEED_OFF", "AP_PANEL_SPEED_HOLD",
            "AP_NAV1_HOLD_ON", "AP_NAV1_HOLD_OFF", "AP_NAV1_HOLD",
            "AP_APR_HOLD_ON", "AP_APR_HOLD_OFF", "AP_APR_HOLD",
            "HEADING_BUG_SET", "AP_ALT_VAR_SET_ENGLISH", "AP_VS_VAR_SET_ENGLISH", "AP_SPD_VAR_SET",
            "NAV1_STBY_SET_HZ", "NAV1_RADIO_SWAP", "VOR1_SET", "TOGGLE_GPS_DRIVES_NAV1",
            "NAV2_STBY_SET_HZ", "NAV2_RADIO_SWAP", "COM_RADIO_SET_HZ", "COM_STBY_RADIO_SET_HZ",
        };
        public const uint EventBase = 1000;

        class Mode { public string Key, On, Off, Toggle; public int Var; }
        static readonly Mode[] Modes = {
            new Mode { Key = "ap",  On = "AUTOPILOT_ON",    Off = "AUTOPILOT_OFF",    Toggle = "AP_MASTER",              Var = 1 },
            new Mode { Key = "hdg", On = "AP_HDG_HOLD_ON",  Off = "AP_HDG_HOLD_OFF",  Toggle = "AP_PANEL_HEADING_HOLD",  Var = 2 },
            new Mode { Key = "alt", On = "AP_ALT_HOLD_ON",  Off = "AP_ALT_HOLD_OFF",  Toggle = "AP_PANEL_ALTITUDE_HOLD", Var = 4 },
            new Mode { Key = "vs",  On = "AP_VS_ON",        Off = "AP_VS_OFF",        Toggle = "AP_PANEL_VS_HOLD",       Var = 6 },
            new Mode { Key = "spd", On = "AP_AIRSPEED_ON",  Off = "AP_AIRSPEED_OFF",  Toggle = "AP_PANEL_SPEED_HOLD",    Var = 8 },
            new Mode { Key = "nav", On = "AP_NAV1_HOLD_ON", Off = "AP_NAV1_HOLD_OFF", Toggle = "AP_NAV1_HOLD",           Var = 10 },
            new Mode { Key = "apr", On = "AP_APR_HOLD_ON",  Off = "AP_APR_HOLD_OFF",  Toggle = "AP_APR_HOLD",            Var = 11 },
        };

        class Pending { public Mode M; public bool Want; public double Since; public bool Toggled; }

        static readonly object Gate = new object();
        static double[] vals;
        static double valsAt;
        static readonly Dictionary<string, Pending> pending = new Dictionary<string, Pending>();
        static readonly Dictionary<string, bool> unsupported = new Dictionary<string, bool>();   // modes sans réaction de l'avion
        static string aircraft = "";
        static readonly ConcurrentQueue<KeyValuePair<string, int>> outbox = new ConcurrentQueue<KeyValuePair<string, int>>();

        public static int EventId(string name) { int i = Array.IndexOf(Events, name); return i < 0 ? -1 : (int)EventBase + i; }

        /// <summary>Nouvelles valeurs lues dans MSFS.</summary>
        public static void Update(double[] v, string title)
        {
            lock (Gate)
            {
                if (!string.IsNullOrEmpty(title) && title != aircraft) { aircraft = title; unsupported.Clear(); pending.Clear(); }   // autre avion : on réapprend
                vals = v; valsAt = RelayState.Now();
            }
        }

        /// <summary>Dernières valeurs lues (null si trop anciennes).</summary>
        public static double[] Values() { lock (Gate) return vals != null && RelayState.Now() - valsAt < 3 ? (double[])vals.Clone() : null; }

        /// <summary>MSFS déconnecté.</summary>
        public static void Clear() { lock (Gate) { vals = null; pending.Clear(); } Lnav.Engage(false); Vnav.Engage(false); }

        static bool On(int i) { return vals != null && i < vals.Length && vals[i] >= 0.5; }

        /// <summary>Ordre venu de la fenêtre FMS : { c: "ap"|"hdg"|"alt"|"vs"|"spd"|"nav"|"apr" (v = 1 ou 0) | "hdg_set"|"alt_set"|"vs_set"|"spd_set" (v = valeur) }.</summary>
        public static void Command(JObject a)
        {
            string c = JsonStore.Str(a["c"]);
            double v; double.TryParse(JsonStore.Str(a["v"]), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v);
            switch (c)
            {
                case "hdg_set": Lnav.ManualHeading(); outbox.Enqueue(Kv("HEADING_BUG_SET", (int)Math.Round(((v % 360) + 360) % 360))); return;
                case "alt_set": Vnav.Manual(); outbox.Enqueue(Kv("AP_ALT_VAR_SET_ENGLISH", Clamp(v, -1000, 60000))); return;
                case "vs_set": if (!Vnav.ClimbVs(v)) Vnav.Manual(); outbox.Enqueue(Kv("AP_VS_VAR_SET_ENGLISH", Clamp(v, -8000, 8000))); return;
                case "spd_set": outbox.Enqueue(Kv("AP_SPD_VAR_SET", Clamp(v, 0, 600))); return;
            }
            if (c == "pmdg" || c == "pmdg_set") { Pmdg.Command(a); return; }   // PMDG 737 : MCP de l'avion
            if (c == "ifly" || c == "ifly_set") { Ifly.Command(a); return; }   // iFly 737 MAX : MCP de l'avion
            if (c == "a220" || c == "a220_set") { A220.Command(a); return; }   // Airbus A220 : FCP de l'avion
            if (c == "lnav") { Lnav.Engage(v >= 0.5); return; }
            if (c == "vnav") { Vnav.Engage(v >= 0.5); return; }
            if (c == "vnav_climb") { Vnav.SetClimb(v); return; }
            if (c == "ils_auto") { Approach.SetAuto(v >= 0.5); return; }
            if (c == "ils_arm") { Approach.SetArm(v >= 0.5); return; }
            if (c == "com_auto") { ComAuto.SetAuto(v >= 0.5); return; }
            foreach (var m in Modes)
            {
                if (m.Key != c) continue;
                bool want = v >= 0.5;
                lock (Gate)
                {
                    unsupported.Remove(m.Key);   // on réessaie à chaque appui
                    pending[m.Key] = new Pending { M = m, Want = want, Since = RelayState.Now() };
                }
                outbox.Enqueue(Kv(want ? m.On : m.Off, 0));
                return;
            }
        }

        static bool IsPending(string k) { lock (Gate) return pending.ContainsKey(k); }
        internal static void Order(string ev, int v) { outbox.Enqueue(Kv(ev, v)); }
        internal static void ModeOn(string key)   // le LNAV demande un mode (ex. HDG) comme si on appuyait sur le bouton
        {
            Command(new JObject { ["c"] = key, ["v"] = 1 });
        }

        static int Clamp(double v, double lo, double hi) { return (int)Math.Round(Math.Max(lo, Math.Min(hi, v))); }
        static KeyValuePair<string, int> Kv(string k, int v) { return new KeyValuePair<string, int>(k, v); }

        /// <summary>Appelé par la boucle SimConnect : vérifie que l'avion a bien réagi, puis rend les ordres à envoyer.</summary>
        public static List<KeyValuePair<string, int>> TakeOrders()
        {
            double now = RelayState.Now();
            lock (Gate)
            {
                foreach (var p in new List<Pending>(pending.Values))
                {
                    if (vals == null || valsAt < p.Since) continue;
                    if (On(p.M.Var) == p.Want) { pending.Remove(p.M.Key); continue; }
                    if (!p.Toggled && now - p.Since > 1.2) { p.Toggled = true; outbox.Enqueue(Kv(p.M.Toggle, 0)); continue; }   // 2e essai
                    if (now - p.Since > 3.0) { pending.Remove(p.M.Key); unsupported[p.M.Key] = true; }                       // l'avion ne gère pas ce mode
                }
            }
            double[] cur; lock (Gate) cur = vals != null && now - valsAt < 3 ? (double[])vals.Clone() : null;
            Lnav.Tick(cur, now, hdgBusy: IsPending("hdg"));
            Vnav.Tick(cur, now, vsBusy: IsPending("vs"));
            Approach.Tick(cur, now, IsPending("nav") || IsPending("apr"), Liner(now));
            ComAuto.Tick(cur, now);
            var list = new List<KeyValuePair<string, int>>();
            KeyValuePair<string, int> o;
            while (outbox.TryDequeue(out o)) list.Add(o);
            return list;
        }

        // PMDG 737 ou iFly 737 MAX (vérifié au plus une fois toutes les 2 s)
        static string liner; static double nextLiner;
        static string Liner(double now)
        {
            if (now < nextLiner) return liner;
            nextLiner = now + 2;
            string ac; lock (Gate) ac = aircraft;
            liner = Pmdg.Snapshot() != null || Pmdg.IsPmdg737(ac) ? "pmdg" : Ifly.Snapshot() != null || Ifly.IsIfly(ac) ? "ifly" : A220.IsA220(ac) ? "a220" : null;
            return liner;
        }

        // avions aux systèmes maison, qui n'écoutent souvent pas les ordres standards de MSFS
        static readonly Regex Custom = new Regex("PMDG|Fenix|iniBuilds|FlyByWire|A32NX|Headwind|Maddog|Leonardo", RegexOptions.IgnoreCase);

        /// <summary>État pour la fenêtre FMS (relais : /ap).</summary>
        public static JObject Snapshot(bool connected)
        {
            var ln = Lnav.Snapshot(); var vn = Vnav.Snapshot(); var apx = Approach.Snapshot(); var com = ComAuto.Snapshot();
            lock (Gate)
            {
                double now = RelayState.Now();
                bool fresh = connected && vals != null && now - valsAt < 5;
                var o = new JObject { ["connected"] = connected, ["live"] = fresh, ["aircraft"] = aircraft, ["custom"] = Custom.IsMatch(aircraft ?? ""), ["com"] = com };
                var pm = connected ? Pmdg.Snapshot() : null;   // bloc du SDK reçu : c'est un PMDG 737, quel que soit le nom de la livrée
                if (pm != null || Pmdg.IsPmdg737(aircraft)) { o["pmdg737"] = true; if (pm != null) o["pmdg"] = pm; }
                else
                {   // iFly 737 MAX : mémoire partagée de son module (si elle répond, c'est un iFly, quel que soit le nom de la livrée)
                    var ifl = connected ? Ifly.Snapshot() : null;
                    if (ifl != null || Ifly.IsIfly(aircraft)) { o["ifly737"] = true; if (ifl != null) o["ifly"] = ifl; }
                    else if (A220.IsA220(aircraft)) { o["a220"] = true; var fcp = connected ? A220.Snapshot(fresh ? vals : null) : null; if (fcp != null) o["fcp"] = fcp; }
                }
                if (!fresh) return o;
                o["available"] = On(0);
                var modes = new JObject();
                foreach (var m in Modes)
                    modes[m.Key] = new JObject { ["on"] = On(m.Var), ["busy"] = pending.ContainsKey(m.Key), ["no"] = unsupported.ContainsKey(m.Key) };
                modes["gs"] = new JObject { ["on"] = On(12), ["busy"] = false, ["no"] = false };
                o["modes"] = modes;
                o["target"] = new JObject { ["hdg"] = Math.Round(vals[3]), ["alt"] = Math.Round(vals[5]), ["vs"] = Math.Round(vals[7]), ["spd"] = Math.Round(vals[9]) };
                o["lnav"] = ln; o["vnav"] = vn; o["ils"] = apx;
                o["actual"] = new JObject { ["hdg"] = Math.Round(vals[13]), ["alt"] = Math.Round(vals[14]), ["vs"] = Math.Round(vals[15]), ["spd"] = Math.Round(vals[16]), ["ground"] = On(17),
                    ["lat"] = Math.Round(vals[20], 5), ["lon"] = Math.Round(vals[21], 5), ["gs"] = Math.Round(vals[22]) };
                return o;
            }
        }
    }

    // ------------------------------------------------------------------ LNAV : l'avion suit la route du FMS de l'appli
    // Le FMS calcule le cap à suivre (avec la correction de vent) et le règle en continu sur le mode HDG de l'avion.
    // Il passe tout seul au point suivant (avec anticipation du virage) et prévient toutes les fenêtres.
    static class Lnav
    {
        static readonly object Gate = new object();
        static bool on, hdgSeenOn;
        static string message = "";
        static int active = -1, myActive = -1, lastRev = -1;
        static double fromLat, fromLon; static bool fromSet;
        static double nextCalc, lastBugSent = -1, lastBugAt, lastHdgAsk;
        static string activeIdent = ""; static double distNm, xteNm, cmdMag = -1;

        public static void Engage(bool v)
        {
            lock (Gate)
            {
                on = v; hdgSeenOn = false; fromSet = false; lastBugSent = -1; myActive = -1; active = -1;
                message = v ? "" : message;
            }
        }

        // ---- suivi du vol sans LNAV (FMS de l'avion, NAV, pilotage à la main) : la liste avance au passage de chaque point
        static double nextFollow;
        static void Follow(double[] v, double now)
        {
            if (now < nextFollow) return;
            nextFollow = now + 2;
            if (v == null || v.Length < 24 || v[17] >= 0.5 || v[22] < 50) return;   // au sol ou trop lent : rien
            var st = FlightStore.Get();
            var plan = st["plan"] as JObject ?? new JObject();
            var route = plan["route"] as JArray;
            if (route == null || route.Count < 3) return;
            int act = Math.Max(1, Math.Min(route.Count - 1, (int?)plan["activeLeg"] ?? 1)), start = act;
            double lat = v[20], lon = v[21];
            for (int guard = 0; guard < 5 && act < route.Count - 1; guard++)
            {
                double pla, plo, bla, blo, nla, nlo;
                if (!Pt(route, act - 1, out pla, out plo) || !Pt(route, act, out bla, out blo) || !Pt(route, act + 1, out nla, out nlo)) break;
                double dB = Dist(lat, lon, bla, blo) * EarthNm;
                double legLen = Dist(pla, plo, bla, blo), d13 = Dist(pla, plo, lat, lon);
                double crs12 = Brg(pla, plo, bla, blo), crs13 = Brg(pla, plo, lat, lon);
                double xtd = Math.Asin(Math.Sin(d13) * Math.Sin((crs13 - crs12) * R));
                double atd = Math.Acos(Math.Max(-1, Math.Min(1, Math.Cos(d13) / Math.Max(1e-9, Math.Cos(xtd)))));
                if (Math.Abs(Wrap(crs13 - crs12)) > 90) atd = -atd;
                // point passé : à moins de 1,5 NM, ou dépassé le long de la route (et plus près du tronçon suivant que de l'ancien)
                bool passed = dB < 1.5 || (legLen > 0 && atd >= legLen && Dist(lat, lon, nla, nlo) < Dist(bla, blo, nla, nlo) + 2 / EarthNm);
                if (!passed) break;
                act++;
            }
            if (act != start) FlightStore.Set(new JObject { ["plan"] = new JObject { ["activeLeg"] = act } }, "track");
        }

        public static void ManualHeading()   // cap réglé à la main : le pilote reprend la main sur le LNAV
        {
            lock (Gate) if (on) Off(Hangar.L("LNAV désengagé : cap réglé à la main.", "LNAV disengaged: heading set by hand."));
        }

        static void Off(string why) { on = false; hdgSeenOn = false; message = why; }

        public static JObject Snapshot()
        {
            lock (Gate)
                return new JObject { ["on"] = on, ["to"] = activeIdent, ["dist"] = Math.Round(distNm, 1), ["xte"] = Math.Round(xteNm, 2),
                    ["hdg"] = cmdMag < 0 ? -1 : Math.Round(cmdMag), ["msg"] = message };
        }

        internal const double R = Math.PI / 180, EarthNm = 3440.065;
        internal static double Dist(double la1, double lo1, double la2, double lo2)   // en radians d'arc
        {
            double dLa = (la2 - la1) * R, dLo = (lo2 - lo1) * R;
            double h = Math.Sin(dLa / 2) * Math.Sin(dLa / 2) + Math.Cos(la1 * R) * Math.Cos(la2 * R) * Math.Sin(dLo / 2) * Math.Sin(dLo / 2);
            return 2 * Math.Atan2(Math.Sqrt(h), Math.Sqrt(1 - h));
        }
        internal static double Brg(double la1, double lo1, double la2, double lo2)    // en degrés vrais
        {
            double y = Math.Sin((lo2 - lo1) * R) * Math.Cos(la2 * R);
            double x = Math.Cos(la1 * R) * Math.Sin(la2 * R) - Math.Sin(la1 * R) * Math.Cos(la2 * R) * Math.Cos((lo2 - lo1) * R);
            return (Math.Atan2(y, x) / R + 360) % 360;
        }
        static double Wrap(double a) { a = (a + 540) % 360 - 180; return a; }     // -180..180
        static double Norm(double a) { return ((a % 360) + 360) % 360; }

        internal static bool Pt(JArray route, int i, out double lat, out double lon)
        {
            lat = lon = 0;
            if (route == null || i < 0 || i >= route.Count) return false;
            var w = route[i] as JObject; if (w == null) return false;
            double.TryParse(JsonStore.Str(w["lat"]), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out lat);
            double.TryParse(JsonStore.Str(w["lon"]), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out lon);
            return !(lat == 0 && lon == 0);
        }

        public static void Tick(double[] v, double now, bool hdgBusy)
        {
            lock (Gate)
            {
                if (!on) { cmdMag = -1; Follow(v, now); return; }
                if (now < nextCalc) return;
                nextCalc = now + 0.25;
                if (v == null || v.Length < 24) { message = Hangar.L("En attente de l'avion…", "Waiting for the aircraft…"); return; }
                if (v[1] < 0.5) { message = Hangar.L("AP coupé : appuie sur AP pour que l'avion suive la route.", "AP off: press AP for the aircraft to follow the route."); return; }
                if (v[10] >= 0.5 || v[11] >= 0.5) { Off(Hangar.L("LNAV désengagé : le mode NAV ou APR de l'avion a pris la main.", "LNAV disengaged: the aircraft's NAV or APR mode took over.")); return; }
                bool hdg = v[2] >= 0.5;
                if (hdg) hdgSeenOn = true;
                else if (hdgSeenOn && !hdgBusy) { Off(Hangar.L("LNAV désengagé : le mode HDG a été coupé.", "LNAV disengaged: HDG mode was turned off.")); return; }

                var st = FlightStore.Get();
                var plan = st["plan"] as JObject ?? new JObject();
                var route = plan["route"] as JArray;
                int act = (int?)plan["activeLeg"] ?? 0, rev = (int?)st["rev"] ?? 0;
                if (route == null || route.Count < 2) { Off(Hangar.L("Pas de route dans le FMS.", "No route in the FMS.")); return; }
                if (act < 1) act = 1;
                if (act >= route.Count) act = route.Count - 1;
                double lat = v[20], lon = v[21], gs = v[22], trk = v[18], hdgT = v[23], magvar = v[19];

                // point de départ du tronçon : le point précédent, ou la position de l'avion après un « Direct vers »
                if (act != active || rev != lastRev)
                {
                    bool mine = act == myActive;
                    double pla, plo;
                    if (!fromSet || !mine) { fromLat = lat; fromLon = lon; fromSet = true; }   // engagement, Direct vers ou nouveau plan
                    if (mine || (active == -1 && Pt(route, act - 1, out pla, out plo) && Dist(pla, plo, lat, lon) * EarthNm < 3))
                    { if (Pt(route, act - 1, out pla, out plo)) { fromLat = pla; fromLon = plo; } }
                    active = act; lastRev = rev; myActive = -1;
                }
                double bla, blo; Pt(route, act, out bla, out blo);
                activeIdent = JsonStore.Str((route[act] as JObject ?? new JObject())["ident"]);

                // écart à la route (à droite = positif) et distance restante
                double d13 = Dist(fromLat, fromLon, lat, lon), crs12 = Brg(fromLat, fromLon, bla, blo), crs13 = Brg(fromLat, fromLon, lat, lon);
                double legLen = Dist(fromLat, fromLon, bla, blo);
                double xtd = Math.Asin(Math.Sin(d13) * Math.Sin((crs13 - crs12) * R));
                double atd = Math.Acos(Math.Max(-1, Math.Min(1, Math.Cos(d13) / Math.Max(1e-9, Math.Cos(xtd)))));
                if (Math.Abs(Wrap(crs13 - crs12)) > 90) atd = -atd;
                xteNm = xtd * EarthNm;
                distNm = Dist(lat, lon, bla, blo) * EarthNm;

                // passage au point suivant, avec anticipation du virage
                double nla, nlo;
                if (act < route.Count - 1 && Pt(route, act + 1, out nla, out nlo))
                {
                    double turn = Math.Abs(Wrap(Brg(bla, blo, nla, nlo) - Brg(bla, blo, fromLat, fromLon) - 180));
                    double radiusNm = Math.Max(60, gs) * Math.Max(60, gs) / (11.26 * Math.Tan(25 * R)) / 6076.0;
                    double lead = Math.Min(radiusNm * Math.Tan(Math.Min(120, turn) * R / 2), 4);
                    if (distNm <= Math.Max(0.3, lead) || (legLen > 0 && atd >= legLen))
                    {
                        myActive = act + 1;
                        FlightStore.Set(new JObject { ["plan"] = new JObject { ["activeLeg"] = act + 1 } }, "lnav");
                        return;
                    }
                }

                // cap à suivre : route du tronçon + retour sur l'axe (30° maxi) + correction de vent
                double legCrsHere = distNm > 0.2 ? Brg(lat, lon, bla, blo) + Math.Asin(Math.Max(-1, Math.Min(1, xteNm / Math.Max(distNm, 0.5)))) / R : crs12;
                if (legLen * EarthNm < 0.3) legCrsHere = Brg(lat, lon, bla, blo);
                double intercept = Math.Max(-30, Math.Min(30, xteNm * 25));
                double trackCmd = Norm(legCrsHere - intercept);
                double drift = gs > 40 ? Wrap(trk - hdgT) : 0;
                if (Math.Abs(drift) > 25) drift = 0;
                cmdMag = Norm(trackCmd - drift - magvar);
                message = "";

                // le mode HDG doit être actif ; on règle le curseur de cap dès qu'il change d'un degré (ou chaque seconde)
                if (!hdg && !hdgBusy && now - lastHdgAsk > 3) { lastHdgAsk = now; Autopilot.ModeOn("hdg"); }
                int bug = (int)Math.Round(cmdMag) % 360; if (bug <= 0) bug += 360;
                if (lastBugSent < 0 || Math.Abs(Wrap(bug - lastBugSent)) >= 1 || now - lastBugAt > 1.0)
                {
                    Autopilot.Order("HEADING_BUG_SET", bug);
                    lastBugSent = bug; lastBugAt = now;
                }
            }
        }
    }

    // ------------------------------------------------------------------ VNAV / VPATH : montée, début de descente (TOD) et descente sur un plan à 3°
    // Montée : altitude cible = croisière (ou point plus haut devant), VS de montée réglable.
    // Descente : pour chaque point plus bas devant l'avion, le FMS calcule où commencer la descente (pente 3°)
    // et prévient une minute avant ; au TOD il règle l'altitude cible et la VS, puis la corrige pour rester sur le plan.
    static class Vnav
    {
        static readonly object Gate = new object();
        static bool on;
        static string phase = "", message = "", targetIdent = "";
        static double todNm = -1, targetAlt = -1, devFt;
        static int climbVs = 700;
        static bool elevUnknown;
        static double nextCalc, lastAltSent = -1, lastVsSent = 99999, lastSentAt, lastVsAsk;
        const double FtPerNm = 318.4;   // pente de 3°

        public static void Engage(bool v) { lock (Gate) { on = v; lastAltSent = -1; lastVsSent = 99999; if (v) message = ""; phase = ""; todNm = -1; } }
        public static void SetClimb(double v) { lock (Gate) { climbVs = (int)Math.Max(300, Math.Min(3000, Math.Round(v / 100) * 100)); lastVsSent = 99999; } }
        /// <summary>VS réglée à la main pendant la montée VNAV : elle devient la VS de montée, sans rien désengager.</summary>
        public static bool ClimbVs(double v)
        {
            lock (Gate)
            {
                if (!on || phase != "climb" || v < 100) return false;
                climbVs = (int)Math.Max(300, Math.Min(3000, Math.Round(v / 100) * 100)); lastVsSent = climbVs;
                return true;
            }
        }
        public static void Manual()
        {
            lock (Gate) if (on) { on = false; phase = ""; message = Hangar.L("VNAV désengagé : altitude ou VS réglée à la main.", "VNAV disengaged: altitude or VS set by hand."); }
        }

        public static JObject Snapshot()
        {
            lock (Gate)
                return new JObject { ["on"] = on, ["phase"] = phase, ["tod"] = Math.Round(todNm, 1), ["alt"] = Math.Round(targetAlt), ["at"] = targetIdent,
                    ["dev"] = Math.Round(devFt), ["climb"] = climbVs, ["msg"] = message, ["elevUnknown"] = elevUnknown };
        }

        static double Num(JToken t) { double d; double.TryParse(JsonStore.Str(t), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out d); return d; }

        public static void Tick(double[] v, double now, bool vsBusy)
        {
            lock (Gate)
            {
                if (!on) return;
                if (now < nextCalc) return;
                nextCalc = now + 0.5;
                if (v == null || v.Length < 24) { message = Hangar.L("En attente de l'avion…", "Waiting for the aircraft…"); return; }
                if (v[1] < 0.5) { message = Hangar.L("AP coupé : appuie sur AP pour que l'avion suive le profil.", "AP off: press AP for the aircraft to follow the profile."); return; }
                if (v[12] >= 0.5) { on = false; phase = ""; message = Hangar.L("VNAV terminé : l'avion est sur le plan de descente de l'ILS.", "VNAV finished: the aircraft is on the ILS glideslope."); return; }

                var st = FlightStore.Get();
                var plan = st["plan"] as JObject ?? new JObject();
                var route = plan["route"] as JArray;
                if (route == null || route.Count < 2) { on = false; message = Hangar.L("Pas de route dans le FMS.", "No route in the FMS."); return; }
                int act = Math.Max(1, Math.Min(route.Count - 1, (int?)plan["activeLeg"] ?? 1));
                double lat = v[20], lon = v[21], alt = v[14], gs = Math.Max(60, v[22]);
                double cruise = Num(plan["cruiseAlt"]);

                // distances le long de la route depuis l'avion
                var along = new double[route.Count];
                double la, lo, pla = lat, plo = lon, sum = 0;
                for (int i = act; i < route.Count; i++)
                {
                    if (!Lnav.Pt(route, i, out la, out lo)) { along[i] = -1; continue; }
                    sum += Lnav.Dist(pla, plo, la, lo) * Lnav.EarthNm; along[i] = sum; pla = la; plo = lo;
                }

                // altitude à respecter sur chaque point (destination : terrain + 1500 ft, 5 NM avant)
                double bestTod = double.MaxValue, bestAlt = -1, pathAlt = double.MaxValue; string bestId = "";
                elevUnknown = false;
                // pas de descente avant le point le plus haut de la route restante (sinon la montée serait prise pour une descente)
                // sommet = dernier point prévu à l'altitude de croisière (aucun devant : on peut descendre dès maintenant)
                double topAlt = cruise;
                for (int i = act; i < route.Count - 1; i++) topAlt = Math.Max(topAlt, Num((route[i] as JObject ?? new JObject())["alt"]));
                int peak = act;
                for (int i = act; i < route.Count - 1; i++) if (Num((route[i] as JObject ?? new JObject())["alt"]) >= topAlt - 300) peak = i;
                double highAhead = cruise;
                for (int i = act; i < route.Count; i++)
                {
                    if (along[i] < 0) continue;
                    var w = route[i] as JObject ?? new JObject();
                    double a = Num(w["alt"]), d = along[i];
                    bool dest = i == route.Count - 1;
                    if (dest)
                    {   // terrain d'arrivée inconnu : pas de cible à l'arrivée (on ne descend pas plus bas que le dernier point connu)
                        string ek = JsonStore.Str(w["elev"]).ToLowerInvariant();
                        if (!(ek == "true" || (a > 0 && ek != "false"))) { elevUnknown = true; continue; }
                        // approche avec une altitude (FAF) : c'est elle la dernière cible, l'ILS fait le reste
                        bool faf = false;
                        foreach (var q in route.OfType<JObject>()) { string apf = JsonStore.Str(q["ap"]).ToLowerInvariant(); if (apf == "true" && Num(q["alt"]) > 0) { faf = true; break; } }
                        if (faf) continue;
                        a = a + 1500; d = Math.Max(0, d - 5);
                    }
                    if (a <= 0) continue;
                    if (a > highAhead && !dest) highAhead = a;
                    double pa = a + d * FtPerNm;                  // altitude du plan à 3° au niveau de l'avion
                    if (i >= peak && pa < pathAlt) pathAlt = pa;
                    if (a < alt - (phase == "path" ? 50 : 300) && i >= peak)   // en descente : on garde la cible jusqu'à l'atteindre
                    {
                        double tod = d - (alt - a) / FtPerNm;      // distance jusqu'au début de descente
                        if (tod < bestTod) { bestTod = tod; bestAlt = a; bestId = JsonStore.Str(w["ident"]) + (dest ? " (-5 NM)" : ""); }
                    }
                }

                double wantAlt, wantVs;
                if (bestAlt > 0 && bestTod <= 0.2)
                {   // VPATH : descente sur le plan à 3°, corrigée selon l'écart
                    phase = "path";
                    devFt = alt - pathAlt;
                    wantAlt = Math.Round(bestAlt / 100) * 100;
                    wantVs = -gs * 5.31 - devFt * 2.0;
                    wantVs = Math.Max(-2500, Math.Min(-300, wantVs));
                    todNm = 0; targetAlt = wantAlt; targetIdent = bestId;
                    message = "";
                }
                else
                {
                    devFt = 0;
                    todNm = bestAlt > 0 ? bestTod : -1;
                    double climbTo = Math.Max(cruise, 0);
                    if (climbTo > 0 && alt < climbTo - 200)
                    {   // montée vers la croisière
                        phase = "climb"; wantAlt = Math.Round(climbTo / 100) * 100; wantVs = climbVs;
                        targetAlt = wantAlt; targetIdent = "";
                    }
                    else
                    {   // croisière : on attend le TOD
                        phase = "cruise"; targetAlt = bestAlt; targetIdent = bestId;
                        double oneMin = gs / 60.0;
                        message = bestAlt > 0 && todNm <= oneMin ? Hangar.L("Descente dans 1 min", "Descent in 1 min") : "";
                        return;
                    }
                }

                // ordres vers l'avion : altitude cible d'abord, puis VS, puis mode VS
                int altI = (int)wantAlt, vsI = (int)(Math.Round(wantVs / 100) * 100);
                bool vsOn = v[6] >= 0.5;
                if (lastAltSent != altI || now - lastSentAt > 3) { Autopilot.Order("AP_ALT_VAR_SET_ENGLISH", altI); lastAltSent = altI; }
                if (Math.Abs(lastVsSent - vsI) >= 100 || now - lastSentAt > 3) { Autopilot.Order("AP_VS_VAR_SET_ENGLISH", vsI); lastVsSent = vsI; lastSentAt = now; }
                // altitude atteinte : l'avion la tient (ALT) ; sinon le mode VS doit être actif
                bool captured = Math.Abs(alt - wantAlt) < 150;
                if (!captured && !vsOn && !vsBusy && now - lastVsAsk > 4) { lastVsAsk = now; Autopilot.ModeOn("vs"); }
            }
        }
    }

    // ------------------------------------------------------------------ approche : fréquence ILS automatique, puis LOC avant APP
    // L'ILS choisi dans le FMS (plan.ils) est mis en attente sur NAV1 à 80 NM, permuté à 25 NM, le cap de piste réglé ;
    // vers 18 NM le mode NAV (LOC) est armé ; une fois l'axe capté, APR est armé pour descendre sur le plan de l'ILS.
    static class Approach
    {
        static readonly object Gate = new object();
        static bool auto = true, arm = true;   // auto : radios (fréquence, course) ; arm : armement LOC puis APP
        static string state = "", ident = "", lastKey = "";
        static double freqHz, crs, distNm = -1;
        static bool hasGs;
        static double nextCalc, lastStby, lastSwap, lastObs, lastGps, lastArm, lastStby2, lastSwap2;
        static bool obsSet;

        public static void SetAuto(bool v) { lock (Gate) auto = v; }
        public static void SetArm(bool v) { lock (Gate) arm = v; }

        public static JObject Snapshot()
        {
            lock (Gate)
                return new JObject { ["auto"] = auto, ["arm"] = arm, ["ident"] = ident, ["freq"] = Math.Round(freqHz / 1e6, 2), ["crs"] = Math.Round(crs), ["gs"] = hasGs,
                    ["state"] = state, ["dist"] = Math.Round(distNm, 1) };
        }

        static double Num(JToken t) { double d; double.TryParse(JsonStore.Str(t), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out d); return d; }
        static bool Same(double mhz, double hz) { return Math.Abs(mhz * 1e6 - hz) < 2000; }

        public static void Tick(double[] v, double now, bool modeBusy, string liner)
        {
            lock (Gate)
            {
                if (now < nextCalc) return;
                nextCalc = now + 1.0;
                var plan = FlightStore.Get()["plan"] as JObject ?? new JObject();
                var ils = plan["ils"] as JObject;
                if (ils == null || Num(ils["freq"]) <= 0) { state = ""; ident = ""; freqHz = 0; distNm = -1; return; }
                freqHz = Num(ils["freq"]); crs = Num(ils["crs"]); ident = JsonStore.Str(ils["ident"]); hasGs = JsonStore.Str(ils["gs"]) == "True" || JsonStore.Str(ils["gs"]) == "true";
                string key = ident + freqHz;
                if (key != lastKey) { lastKey = key; obsSet = false; }
                var route = plan["route"] as JArray;
                double dla, dlo;
                if (v == null || v.Length < 30 || route == null || !Lnav.Pt(route, route.Count - 1, out dla, out dlo)) { state = "wait"; return; }
                distNm = Lnav.Dist(v[20], v[21], dla, dlo) * Lnav.EarthNm;
                bool active = Same(v[24], freqHz), standby = Same(v[25], freqHz);
                bool apOn = v[1] >= 0.5, navOn = v[10] >= 0.5, aprOn = v[11] >= 0.5, gsOn = v[12] >= 0.5;
                bool loc = v[27] >= 0.5;
                double hdgMag = v[13], cdi = v[28];

                if (aprOn && (gsOn || !hasGs)) { state = gsOn ? "gs" : "app"; return; }
                if (aprOn) { state = "app"; return; }
                // A220 : son FMC règle lui-même l'ILS (fréquences et courses), le FMS n'y touche pas
                if (liner == "a220") { state = active ? "active" : "fmc"; return; }
                bool two = liner != null && v.Length >= 32;   // PMDG / iFly : ILS sur NAV1 et NAV2, les deux courses
                bool active2 = two && Same(v[30], freqHz), standby2 = two && Same(v[31], freqHz);
                if (auto)
                {
                    // 1) fréquence en attente, 2) permutation, 3) cap de piste, 4) l'aiguille NAV1 sur l'ILS (et pas le GPS)
                    if (!active && !standby && distNm < 80 && now - lastStby > 5) { lastStby = now; Autopilot.Order("NAV1_STBY_SET_HZ", (int)freqHz); }
                    if (!active && standby && distNm < 25 && now - lastSwap > 5) { lastSwap = now; Autopilot.Order("NAV1_RADIO_SWAP", 0); }
                    if (two)
                    {
                        if (!active2 && !standby2 && distNm < 80 && now - lastStby2 > 5) { lastStby2 = now; Autopilot.Order("NAV2_STBY_SET_HZ", (int)freqHz); }
                        if (!active2 && standby2 && distNm < 25 && now - lastSwap2 > 5) { lastSwap2 = now; Autopilot.Order("NAV2_RADIO_SWAP", 0); }
                        // les deux courses (gauche et droite) du MCP, par le SDK de l'avion
                        if (active && !obsSet && now - lastObs > 3)
                        {
                            lastObs = now; obsSet = true;
                            var o = new JObject { ["c"] = liner + "_set", ["k"] = "crs", ["v"] = Math.Round(crs) };
                            if (liner == "pmdg") Pmdg.Command(o); else Ifly.Command(o);
                        }
                    }
                    else
                    {
                        if (active && !obsSet && now - lastObs > 3) { lastObs = now; obsSet = true; Autopilot.Order("VOR1_SET", (int)Math.Round(crs) % 360 == 0 ? 360 : (int)Math.Round(crs) % 360); }
                        if (active && v[26] >= 0.5 && distNm < 25 && now - lastGps > 5) { lastGps = now; Autopilot.Order("TOGGLE_GPS_DRIVES_NAV1", 0); }
                    }
                }
                state = active ? (active2 ? "active2" : "active") : standby ? "standby" : auto ? "wait" : "manual";
                if (!arm || !active) return;   // armement seulement quand la bonne fréquence est active (réglée par le FMS ou à la main)
                double off = Math.Abs(((hdgMag - crs) % 360 + 540) % 360 - 180);

                if (two)
                {   // PMDG / iFly : boutons VOR/LOC et APP du MCP, par le SDK (seulement si CMD A ou B est engagé)
                    var snap = liner == "pmdg" ? Pmdg.Snapshot() : Ifly.Snapshot();
                    var on = snap != null ? snap["on"] as JObject : null;
                    if (on == null) return;
                    Func<string, bool> lit = k => (bool?)on[k] ?? false;
                    if (!lit("cmda") && !lit("cmdb")) return;
                    Action<string> press = k => { var o = new JObject { ["c"] = liner, ["b"] = k }; if (liner == "pmdg") Pmdg.Command(o); else Ifly.Command(o); };
                    if (lit("app")) { state = "app"; return; }
                    if (!lit("vorloc"))
                    {
                        if (loc && distNm < 18 && off < 90 && now - lastArm > 6) { lastArm = now; press("vorloc"); state = "loc_arm"; }
                        return;
                    }
                    state = "loc";
                    if (hasGs && v[29] >= 0.5 && Math.Abs(cdi) < 40 && off < 30 && now - lastArm > 6) { lastArm = now; press("app"); state = "app_arm"; }
                    return;
                }
                if (!apOn || modeBusy) return;

                // 5) LOC d'abord : mode NAV armé vers 18 NM si l'avion se présente dans le bon sens
                if (!navOn && loc && distNm < 18 && off < 90 && v[26] < 0.5 && now - lastArm > 6) { lastArm = now; Autopilot.ModeOn("nav"); state = "loc_arm"; return; }
                if (navOn)
                {
                    state = "loc";
                    // 6) axe capté (aiguille presque centrée, avion aligné) : APR pour le plan de descente
                    if (hasGs && v[29] >= 0.5 && Math.Abs(cdi) < 40 && off < 30 && now - lastArm > 6) { lastArm = now; Autopilot.ModeOn("apr"); state = "app_arm"; }
                }
            }
        }
    }
}
