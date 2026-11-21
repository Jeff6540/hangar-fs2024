// FMS — pilote automatique, morceaux 1 et 2 : lire ce que l'avion sait faire, régler les consignes et les modes.
// Les ordres viennent de la fenêtre FMS (chrome.webview.postMessage({ ap: { c: "hdg", v: 1 } })) et sont envoyés
// à MSFS par la boucle SimConnect du relais (voir Relay.cs). L'état est lu deux fois par seconde (relais : /ap).
// Pour chaque mode, on essaie d'abord l'ordre « _ON / _OFF » ; si l'avion ne réagit pas, l'ordre « bascule » ;
// s'il ne réagit toujours pas, le mode est marqué « non géré par l'avion » (le FMS pourra le forcer plus tard).
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
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

        /// <summary>MSFS déconnecté.</summary>
        public static void Clear() { lock (Gate) { vals = null; pending.Clear(); } }

        static bool On(int i) { return vals != null && i < vals.Length && vals[i] >= 0.5; }

        /// <summary>Ordre venu de la fenêtre FMS : { c: "ap"|"hdg"|"alt"|"vs"|"spd"|"nav"|"apr" (v = 1 ou 0) | "hdg_set"|"alt_set"|"vs_set"|"spd_set" (v = valeur) }.</summary>
        public static void Command(JObject a)
        {
            string c = JsonStore.Str(a["c"]);
            double v; double.TryParse(JsonStore.Str(a["v"]), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v);
            switch (c)
            {
                case "hdg_set": outbox.Enqueue(Kv("HEADING_BUG_SET", (int)Math.Round(((v % 360) + 360) % 360))); return;
                case "alt_set": outbox.Enqueue(Kv("AP_ALT_VAR_SET_ENGLISH", Clamp(v, -1000, 60000))); return;
                case "vs_set": outbox.Enqueue(Kv("AP_VS_VAR_SET_ENGLISH", Clamp(v, -8000, 8000))); return;
                case "spd_set": outbox.Enqueue(Kv("AP_SPD_VAR_SET", Clamp(v, 0, 600))); return;
            }
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
            var list = new List<KeyValuePair<string, int>>();
            KeyValuePair<string, int> o;
            while (outbox.TryDequeue(out o)) list.Add(o);
            return list;
        }

        // avions aux systèmes maison, qui n'écoutent souvent pas les ordres standards de MSFS
        static readonly Regex Custom = new Regex("PMDG|Fenix|iniBuilds|FlyByWire|A32NX|Headwind|Maddog|Leonardo", RegexOptions.IgnoreCase);

        /// <summary>État pour la fenêtre FMS (relais : /ap).</summary>
        public static JObject Snapshot(bool connected)
        {
            lock (Gate)
            {
                double now = RelayState.Now();
                bool fresh = connected && vals != null && now - valsAt < 5;
                var o = new JObject { ["connected"] = connected, ["live"] = fresh, ["aircraft"] = aircraft, ["custom"] = Custom.IsMatch(aircraft ?? "") };
                if (!fresh) return o;
                o["available"] = On(0);
                var modes = new JObject();
                foreach (var m in Modes)
                    modes[m.Key] = new JObject { ["on"] = On(m.Var), ["busy"] = pending.ContainsKey(m.Key), ["no"] = unsupported.ContainsKey(m.Key) };
                modes["gs"] = new JObject { ["on"] = On(12), ["busy"] = false, ["no"] = false };
                o["modes"] = modes;
                o["target"] = new JObject { ["hdg"] = Math.Round(vals[3]), ["alt"] = Math.Round(vals[5]), ["vs"] = Math.Round(vals[7]), ["spd"] = Math.Round(vals[9]) };
                o["actual"] = new JObject { ["hdg"] = Math.Round(vals[13]), ["alt"] = Math.Round(vals[14]), ["vs"] = Math.Round(vals[15]), ["spd"] = Math.Round(vals[16]), ["ground"] = On(17) };
                return o;
            }
        }
    }
}
