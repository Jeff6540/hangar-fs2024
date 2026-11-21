// FMS — Airbus A220 (Synaptic / iniBuilds) : le FCP de l'avion lu et commandé depuis la fenêtre FMS.
// D'après la documentation publique de Synaptic (docs.synapticsim.com, pages SimVars et Inputs) :
//  - état des modes : variables « L:A22X … » (AP Master, AT Master, FG Heading, FG LNAV…), lues par SimConnect ;
//  - boutons : ordres standards de MSFS que l'avion écoute (AP_MASTER, AP_HDG_HOLD, AP_NAV1_HOLD, FLIGHT_LEVEL_CHANGE…) ;
//  - F/D gauche / droit et VNAV : variables « L:A22X » écrites directement ;
//  - molettes : seulement + / − pour l'altitude, la VS et la vitesse (on « tourne » jusqu'à la valeur voulue),
//    réglage direct pour le cap (HEADING_BUG_SET).
// Le FMC de l'avion garde la route et règle lui-même l'ILS : l'ILS auto du FMS ne touche à rien sur cet avion.
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class A220
    {
        // variables lues (une valeur double chacune, dans cet ordre)
        public static readonly string[][] Fields = {
            new[] { "L:A22X AP Master", "Bool" },            // 0
            new[] { "L:A22X AT Master", "Bool" },            // 1
            new[] { "L:A22X FG Heading", "Bool" },           // 2
            new[] { "L:A22X FG LNAV", "Bool" },              // 3
            new[] { "L:A22X FG Approach", "Bool" },          // 4
            new[] { "L:A22X FG Flight Level", "Bool" },      // 5
            new[] { "L:A22X FG Altitude", "Bool" },          // 6
            new[] { "L:A22X FG VNAV", "Bool" },              // 7
            new[] { "L:A22X FG Vertical Speed", "Bool" },    // 8
            new[] { "L:A22X L Flight Director", "Bool" },    // 9
            new[] { "L:A22X R Flight Director", "Bool" },    // 10
            new[] { "L:A22X FG VNAV Toggle", "Bool" },       // 11
        };
        // variables écrites (une définition SimConnect chacune)
        public const uint DefFdL = 20, DefFdR = 21, DefVnav = 22;
        public static readonly KeyValuePair<uint, string>[] Writable = {
            new KeyValuePair<uint, string>(DefFdL, "L:A22X L Flight Director"),
            new KeyValuePair<uint, string>(DefFdR, "L:A22X R Flight Director"),
            new KeyValuePair<uint, string>(DefVnav, "L:A22X FG VNAV Toggle"),
        };

        // ordres standards écoutés par l'avion (numéro = 3000 + position)
        public const uint EventBase = 3000;
        public static readonly string[] Events = {
            "AP_MASTER", "AUTO_THROTTLE_ARM", "AP_HDG_HOLD", "AP_NAV1_HOLD", "AP_APR_HOLD", "FLIGHT_LEVEL_CHANGE", "AP_ALT_HOLD", "AP_VS_HOLD",
            "HEADING_BUG_SET", "AP_ALT_VAR_INC", "AP_ALT_VAR_DEC", "AP_VS_VAR_INC", "AP_VS_VAR_DEC", "AP_SPD_VAR_INC", "AP_SPD_VAR_DEC",
        };
        static readonly Dictionary<string, string> Buttons = new Dictionary<string, string>
        {
            { "ap", "AP_MASTER" }, { "at", "AUTO_THROTTLE_ARM" }, { "hdg", "AP_HDG_HOLD" }, { "nav", "AP_NAV1_HOLD" }, { "appr", "AP_APR_HOLD" },
            { "flc", "FLIGHT_LEVEL_CHANGE" }, { "alt", "AP_ALT_HOLD" }, { "vs", "AP_VS_HOLD" },
        };
        static uint Ev(string name) { return EventBase + (uint)Array.IndexOf(Events, name); }

        static readonly object Gate = new object();
        static double[] lv; static double lvAt;
        static readonly ConcurrentQueue<KeyValuePair<uint, int>> events = new ConcurrentQueue<KeyValuePair<uint, int>>();
        static readonly ConcurrentQueue<KeyValuePair<uint, double>> writes = new ConcurrentQueue<KeyValuePair<uint, double>>();

        public static bool IsA220(string title)
        {
            return Regex.IsMatch(title ?? "", @"A22[0X]|BD-?500|\bCS[13]00\b|BCS[13]", RegexOptions.IgnoreCase);
        }

        public static void Update(double[] v) { lock (Gate) { lv = v; lvAt = RelayState.Now(); } }
        public static void Clear() { lock (Gate) { lv = null; targets.Clear(); } }

        static bool On(double[] v, int i) { return v != null && v.Length > i && v[i] >= 0.5; }

        /// <summary>État du FCP pour la fenêtre FMS (null tant que rien n'est lu).</summary>
        public static JObject Snapshot(double[] ap)
        {
            double[] v; lock (Gate) v = lv != null && RelayState.Now() - lvAt < 3 ? lv : null;
            if (v == null) return null;
            var o = new JObject
            {
                ["powered"] = true,
                ["on"] = new JObject
                {
                    ["ap"] = On(v, 0), ["at"] = On(v, 1), ["hdg"] = On(v, 2), ["nav"] = On(v, 3), ["appr"] = On(v, 4), ["flc"] = On(v, 5),
                    ["alt"] = On(v, 6), ["vnav"] = On(v, 7), ["vs"] = On(v, 8), ["fdl"] = On(v, 9), ["fdr"] = On(v, 10),
                },
            };
            if (ap != null && ap.Length > 9)
            {
                o["hdg"] = (((int)Math.Round(ap[3]) % 360) + 360) % 360 == 0 ? 360 : (((int)Math.Round(ap[3]) % 360) + 360) % 360;
                o["alt"] = (int)Math.Round(ap[5] / 100) * 100;
                o["vs"] = (int)Math.Round(ap[7] / 100) * 100;
                if (ap[9] > 1) o["ias"] = (int)Math.Round(ap[9]);
            }
            return o;
        }

        // ---- molettes « + / − » : on tourne jusqu'à la valeur voulue, en apprenant la taille d'un cran
        class Target { public double Want, Until, Next, LastCur = double.NaN; public int LastSent; public double Step; }
        static readonly Dictionary<string, Target> targets = new Dictionary<string, Target>();
        static readonly Dictionary<string, double> steps = new Dictionary<string, double> { { "alt", 100 }, { "vs", 100 }, { "ias", 1 } };

        /// <summary>Ordre venu de la fenêtre FMS : { c: "a220", b: "ap" } (appui) ou { c: "a220_set", k: "alt"|"hdg"|"ias"|"vs", v }.</summary>
        public static void Command(JObject a)
        {
            string c = JsonStore.Str(a["c"]), b = JsonStore.Str(a["b"]), k = JsonStore.Str(a["k"]);
            double v; double.TryParse(JsonStore.Str(a["v"]), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v);
            double[] cur; lock (Gate) cur = lv;
            if (c == "a220")
            {
                string ev;
                if (Buttons.TryGetValue(b, out ev)) { events.Enqueue(new KeyValuePair<uint, int>(Ev(ev), 0)); return; }
                if (b == "fdl") writes.Enqueue(new KeyValuePair<uint, double>(DefFdL, On(cur, 9) ? 0 : 1));
                else if (b == "fdr") writes.Enqueue(new KeyValuePair<uint, double>(DefFdR, On(cur, 10) ? 0 : 1));
                else if (b == "vnav") writes.Enqueue(new KeyValuePair<uint, double>(DefVnav, On(cur, 11) ? 0 : 1));
                return;
            }
            if (c != "a220_set") return;
            if (k == "hdg") { int h = (int)Math.Round(((v % 360) + 360) % 360); events.Enqueue(new KeyValuePair<uint, int>(Ev("HEADING_BUG_SET"), h == 0 ? 360 : h)); return; }
            if (!steps.ContainsKey(k)) return;
            if (k == "alt") v = Math.Max(0, Math.Min(45000, Math.Round(v / 100) * 100));
            if (k == "vs") v = Math.Max(-6000, Math.Min(6000, Math.Round(v / 100) * 100));
            if (k == "ias") { if (v < 1) return; v = Math.Max(100, Math.Min(340, Math.Round(v))); }   // Mach : pas de réglage possible de l'extérieur
            double now = RelayState.Now();
            lock (Gate) targets[k] = new Target { Want = v, Until = now + 30, Next = now, Step = steps[k] };
        }

        static double Current(string k, double[] ap)
        {
            if (ap == null || ap.Length <= 9) return double.NaN;
            return k == "alt" ? ap[5] : k == "vs" ? ap[7] : ap[9];
        }

        /// <summary>Ordres à envoyer (boutons et crans de molette) ; ap = valeurs du pilote auto (Autopilot.Fields).</summary>
        public static List<KeyValuePair<uint, int>> TakeOrders(double[] ap)
        {
            var list = new List<KeyValuePair<uint, int>>();
            KeyValuePair<uint, int> e;
            while (events.TryDequeue(out e)) list.Add(e);
            double now = RelayState.Now();
            lock (Gate)
            {
                foreach (var k in new List<string>(targets.Keys))
                {
                    var t = targets[k];
                    if (now > t.Until) { targets.Remove(k); continue; }
                    if (now < t.Next) continue;
                    double cur = Current(k, ap);
                    if (double.IsNaN(cur)) continue;
                    // taille d'un cran apprise sur le dernier envoi (100 ou 1000 ft selon le mode de la molette, etc.)
                    if (t.LastSent != 0 && !double.IsNaN(t.LastCur) && Math.Abs(cur - t.LastCur) > 0.1)
                    {
                        double s = Math.Abs(cur - t.LastCur) / Math.Abs(t.LastSent);
                        if (s > 0.2) { t.Step = s; steps[k] = s; }
                    }
                    double diff = t.Want - cur;
                    if (Math.Abs(diff) < Math.Max(t.Step / 2, k == "ias" ? 0.5 : 50)) { targets.Remove(k); continue; }
                    int n = (int)Math.Round(diff / t.Step);
                    if (n == 0) n = Math.Sign(diff);
                    n = Math.Max(-25, Math.Min(25, n));
                    string ev = k == "alt" ? (n > 0 ? "AP_ALT_VAR_INC" : "AP_ALT_VAR_DEC") : k == "vs" ? (n > 0 ? "AP_VS_VAR_INC" : "AP_VS_VAR_DEC") : (n > 0 ? "AP_SPD_VAR_INC" : "AP_SPD_VAR_DEC");
                    for (int i = 0; i < Math.Abs(n); i++) list.Add(new KeyValuePair<uint, int>(Ev(ev), 0));
                    t.LastSent = n; t.LastCur = cur; t.Next = now + 0.8;   // laisser le temps à la valeur d'être relue
                }
            }
            return list;
        }

        public static List<KeyValuePair<uint, double>> TakeWrites()
        {
            var list = new List<KeyValuePair<uint, double>>();
            KeyValuePair<uint, double> w;
            while (writes.TryDequeue(out w)) list.Add(w);
            return list;
        }
    }
}
