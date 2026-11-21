// FMS — PMDG 737 (-600 / -700 / -800 / -900) : le MCP de l'avion lu et commandé par le SDK officiel de PMDG.
// Lecture : bloc de données « PMDG_NG3_Data » diffusé par l'avion (à activer dans 737NG3_Options.ini, section [SDK] :
// EnableDataBroadcast=1). Commandes : événements « #69632 + n » du SDK (appui = clic gauche puis relâché) et
// événements de réglage direct (altitude, cap, vitesse, VS). Positions des valeurs : PMDG_NG3_SDK.h (structure PMDG_NG3_Data).
// Le FMS de l'avion reste maître de la route : ici on ne fait qu'appuyer sur les boutons et tourner les molettes du MCP.
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class Pmdg
    {
        public const string DataName = "PMDG_NG3_Data";
        public const uint DataId = 0x4E473331, DataDef = 0x4E473332, DataSize = 916;
        const uint Base = 0x00011000;   // THIRD_PARTY_EVENT_ID_MIN = 69632
        const int MouseLeft = 0x20000000, MouseRelease = 0x00020000;

        // boutons du MCP (numéros du SDK) et réglages directs
        static readonly Dictionary<string, uint> Buttons = new Dictionary<string, uint>
        {
            { "cmda", 402 }, { "cmdb", 403 }, { "at", 380 }, { "n1", 381 }, { "speed", 382 }, { "vnav", 386 }, { "lvlchg", 391 },
            { "hdgsel", 392 }, { "app", 393 }, { "althold", 394 }, { "vs", 395 }, { "vorloc", 396 }, { "lnav", 397 },
            { "fdl", 378 }, { "fdr", 407 }, { "spdintv", 387 }, { "altintv", 885 }, { "co", 383 },
        };
        const uint CrsLSet = 14500, CrsRSet = 14501, IasSet = 14502, MachSet = 14503, HdgSet = 14504, AltSet = 14505, VsSet = 14506;

        /// <summary>Tous les numéros d'événements PMDG utilisés (à associer à « #numéro » au démarrage de SimConnect).</summary>
        public static IEnumerable<uint> AllEvents()
        {
            foreach (var b in Buttons.Values) yield return Base + b;
            foreach (var s in new[] { CrsLSet, CrsRSet, IasSet, MachSet, HdgSet, AltSet, VsSet }) yield return Base + s;
        }

        static readonly object Gate = new object();
        static byte[] data; static double dataAt;
        static readonly ConcurrentQueue<KeyValuePair<uint, int>> outbox = new ConcurrentQueue<KeyValuePair<uint, int>>();

        public static bool IsPmdg737(string title) { var t = (title ?? "").ToUpperInvariant(); return t.Contains("PMDG") && t.Contains("737"); }

        public static void Update(byte[] buf, int offset)
        {
            if (buf.Length < offset + 460) return;
            var b = new byte[Math.Min(DataSize, buf.Length - offset)];
            Buffer.BlockCopy(buf, offset, b, 0, b.Length);
            lock (Gate) { data = b; dataAt = RelayState.Now(); }
        }
        public static void Clear() { lock (Gate) data = null; }

        static bool B(byte[] d, int o) { return d[o] != 0; }
        static int U16(byte[] d, int o) { return BitConverter.ToUInt16(d, o); }
        static int S16(byte[] d, int o) { return BitConverter.ToInt16(d, o); }

        /// <summary>État du MCP pour la fenêtre FMS (null si le SDK ne diffuse pas).</summary>
        public static JObject Snapshot()
        {
            lock (Gate)
            {
                if (data == null || RelayState.Now() - dataAt > 10) return null;
                var d = data;
                float iasMach = BitConverter.ToSingle(d, 420);
                return new JObject
                {
                    ["powered"] = B(d, 457),
                    ["crs"] = U16(d, 416), ["crsR"] = U16(d, 418),
                    ["ias"] = iasMach < 10 ? Math.Round(iasMach, 2) : Math.Round(iasMach), ["mach"] = iasMach < 10, ["iasBlank"] = B(d, 424),
                    ["hdg"] = U16(d, 428), ["alt"] = U16(d, 430), ["vs"] = S16(d, 432), ["vsBlank"] = B(d, 434),
                    ["on"] = new JObject
                    {
                        ["cmda"] = B(d, 453), ["cmdb"] = B(d, 455), ["cwsa"] = B(d, 454), ["cwsb"] = B(d, 456),
                        ["at"] = B(d, 442), ["n1"] = B(d, 443), ["speed"] = B(d, 444), ["vnav"] = B(d, 445), ["lvlchg"] = B(d, 446),
                        ["hdgsel"] = B(d, 447), ["lnav"] = B(d, 448), ["vorloc"] = B(d, 449), ["app"] = B(d, 450), ["althold"] = B(d, 451), ["vs"] = B(d, 452),
                        ["fdl"] = B(d, 440), ["fdr"] = B(d, 441),
                    },
                };
            }
        }

        /// <summary>Ordre venu de la fenêtre FMS : { c: "pmdg", b: "cmda" } (appui) ou { c: "pmdg_set", k: "alt"|"hdg"|"ias"|"vs"|"crs", v }.</summary>
        public static void Command(JObject a)
        {
            string c = JsonStore.Str(a["c"]);
            if (c == "pmdg")
            {
                uint n; if (!Buttons.TryGetValue(JsonStore.Str(a["b"]), out n)) return;
                outbox.Enqueue(new KeyValuePair<uint, int>(Base + n, MouseLeft));
                outbox.Enqueue(new KeyValuePair<uint, int>(Base + n, MouseRelease));
                return;
            }
            if (c != "pmdg_set") return;
            double v; double.TryParse(JsonStore.Str(a["v"]), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v);
            switch (JsonStore.Str(a["k"]))
            {
                case "alt": outbox.Enqueue(new KeyValuePair<uint, int>(Base + AltSet, (int)Math.Max(0, Math.Min(50000, Math.Round(v / 100) * 100)))); break;
                case "hdg": { int h = (int)Math.Round(((v % 360) + 360) % 360); outbox.Enqueue(new KeyValuePair<uint, int>(Base + HdgSet, h == 0 ? 360 : h)); break; }
                case "crs": { int h = (int)Math.Round(((v % 360) + 360) % 360); outbox.Enqueue(new KeyValuePair<uint, int>(Base + CrsLSet, h == 0 ? 360 : h)); outbox.Enqueue(new KeyValuePair<uint, int>(Base + CrsRSet, h == 0 ? 360 : h)); break; }
                case "ias":
                    if (v > 0 && v < 1) outbox.Enqueue(new KeyValuePair<uint, int>(Base + MachSet, (int)Math.Round(v * 100)));   // nombre de Mach (ex. 0.78)
                    else outbox.Enqueue(new KeyValuePair<uint, int>(Base + IasSet, (int)Math.Max(100, Math.Min(400, Math.Round(v)))));
                    break;
                case "vs": outbox.Enqueue(new KeyValuePair<uint, int>(Base + VsSet, (int)Math.Max(-8000, Math.Min(6000, Math.Round(v / 50) * 50)) + 10000)); break;   // le SDK attend VS + 10000
            }
        }

        /// <summary>Active la diffusion du SDK dans les options des PMDG 737 installés (section [SDK], EnableDataBroadcast=1).
        /// Dossiers cherchés : ceux de MSFS 2024 (version Microsoft Store / Xbox et version Steam). Rien n'est écrit en dur pour un PC.</summary>
        public static JObject EnableSdk()
        {
            var res = new JObject { ["files"] = new JArray(), ["changed"] = 0 };
            var roots = new List<string>
            {
                System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalState", "WASM", "MSFS2024"),
                System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Microsoft Flight Simulator 2024", "WASM", "MSFS2024"),
            };
            foreach (var root in roots)
            {
                if (!System.IO.Directory.Exists(root)) continue;
                string[] pkgs; try { pkgs = System.IO.Directory.GetDirectories(root, "pmdg-aircraft-73*"); } catch (Exception) { continue; }
                foreach (var pkg in pkgs)
                {
                    string[] inis; try { inis = System.IO.Directory.GetFiles(pkg, "737NG3_Options.ini", System.IO.SearchOption.AllDirectories); } catch (Exception) { continue; }
                    foreach (var f in inis)
                    {
                        try
                        {
                            string txt = System.IO.File.ReadAllText(f), nl = txt.Contains("\r\n") ? "\r\n" : "\n", nt;
                            var rx = new System.Text.RegularExpressions.Regex("(?im)^[ \\t]*EnableDataBroadcast[ \\t]*=[ \\t]*\\d+[ \\t]*(?=\\r?$)");
                            if (rx.IsMatch(txt)) nt = rx.Replace(txt, "EnableDataBroadcast=1");
                            else if (System.Text.RegularExpressions.Regex.IsMatch(txt, "(?im)^\\s*\\[SDK\\]\\s*$"))
                                nt = System.Text.RegularExpressions.Regex.Replace(txt, "(?im)^([ \\t]*\\[SDK\\][ \\t]*)(?=\\r?$)", "$1" + nl + "EnableDataBroadcast=1", System.Text.RegularExpressions.RegexOptions.None);
                            else nt = txt.TrimEnd() + nl + nl + "[SDK]" + nl + "EnableDataBroadcast=1" + nl;
                            bool ch = nt != txt;
                            if (ch) { System.IO.File.Copy(f, f + ".hangar.bak", true); System.IO.File.WriteAllText(f, nt); res["changed"] = (int)res["changed"] + 1; }
                            ((JArray)res["files"]).Add(new JObject { ["pkg"] = System.IO.Path.GetFileName(pkg), ["changed"] = ch });
                        }
                        catch (Exception e) { ((JArray)res["files"]).Add(new JObject { ["pkg"] = System.IO.Path.GetFileName(pkg), ["error"] = e.Message }); }
                    }
                }
            }
            return res;
        }

        public static List<KeyValuePair<uint, int>> TakeOrders()
        {
            var l = new List<KeyValuePair<uint, int>>(); KeyValuePair<uint, int> o;
            while (outbox.TryDequeue(out o)) l.Add(o);
            return l;
        }
    }
}
