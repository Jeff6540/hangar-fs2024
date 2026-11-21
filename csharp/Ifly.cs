// FMS — iFly 737 MAX : le MCP de l'avion lu et commandé par le SDK d'iFly (v1.5).
// Lecture : mémoire partagée « iFly737MAX_SDK_FileMappingObject » (structure ShareMemory737MAXSDK de SDK_Defines.h,
// alignement 8 ; positions calculées à partir du SDK). Écriture : message WM_COPYDATA envoyé à la fenêtre du module
// « iFly Plugin - MSFS2024 » (ou « iFly Plugin » pour MSFS 2020), avec le message enregistré « iFly737MAX_MSG_GAU »
// et la structure { int Command; double Value1, Value2, Value3 } (commandes de key_command.h).
// Le FMS de l'avion reste maître de la route : on ne fait qu'appuyer sur les boutons et tourner les molettes du MCP.
using System;
using System.Collections.Generic;
using System.IO.MemoryMappedFiles;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class Ifly
    {
        const string MapName = "iFly737MAX_SDK_FileMappingObject", MsgName = "iFly737MAX_MSG_GAU";
        const int MapSize = 3240;

        // commandes (numéros de l'énumération KEY_COMMAND_IFLY737MAX)
        static readonly Dictionary<string, int> Buttons = new Dictionary<string, int>
        {
            { "at", 230 }, { "n1", 232 }, { "speed", 233 }, { "spdintv", 234 }, { "vnav", 235 }, { "lvlchg", 236 }, { "app", 237 },
            { "althold", 238 }, { "vs", 239 }, { "altintv", 240 }, { "lnav", 241 }, { "vorloc", 242 }, { "hdgsel", 243 },
            { "cmda", 244 }, { "cmdb", 245 }, { "fdl", 248 }, { "fdr", 250 }, { "co", 216 },
        };
        const int Crs1Set = 209, Crs2Set = 212, IasMachSet = 215, HdgSet = 223, AltSet = 226, VsSet = 229;

        public static bool IsIfly(string title) { var t = (title ?? "").ToUpperInvariant(); return t.Contains("IFLY") || t.Contains("737 MAX") || t.Contains("737-MAX") || t.Contains("737MAX"); }

        static byte[] Read()
        {
            try
            {
                using (var mm = MemoryMappedFile.OpenExisting(MapName, MemoryMappedFileRights.Read))
                using (var v = mm.CreateViewAccessor(0, MapSize, MemoryMappedFileAccess.Read))
                {
                    var b = new byte[MapSize];
                    v.ReadArray(0, b, 0, MapSize);
                    return BitConverter.ToInt32(b, 0) == 1 ? b : null;   // iFly737MAX_RUNNING
                }
            }
            catch (Exception) { return null; }   // module iFly absent, avion pas chargé
        }

        static bool Lit(byte s) { return s == 1 || s == 2 || s == 4 || s == 5; }   // voyant allumé (faible ou fort), bouton relâché ou appuyé
        static int Digit(byte d) { return d <= 9 ? d : -1; }
        static int? Num(byte[] b, params int[] offs)
        {
            int v = 0; bool any = false;
            foreach (var o in offs) { int d = Digit(b[o]); if (d < 0) { if (any) return null; continue; } v = v * 10 + d; any = true; }
            return any ? v : (int?)null;
        }

        /// <summary>État du MCP pour la fenêtre FMS (null si l'iFly ne répond pas).</summary>
        public static JObject Snapshot()
        {
            var b = Read(); if (b == null) return null;
            var o = new JObject();
            // vitesse : symbole + 3 chiffres ; point décimal = nombre de Mach (.780)
            int? spd = Num(b, 268, 269, 270);
            bool mach = b[271] != 0;
            o["iasBlank"] = spd == null;
            o["mach"] = mach;
            if (spd != null) o["ias"] = mach ? Math.Round(spd.Value / 1000.0, 2) : spd.Value;
            int? hdg = Num(b, 272, 273, 274); if (hdg != null) o["hdg"] = hdg.Value;
            int? alt = Num(b, 275, 276, 277, 278, 279); if (alt != null) o["alt"] = alt.Value;
            int? crs = Num(b, 264, 265, 266); if (crs != null) o["crs"] = crs.Value;
            int? vs = Num(b, 281, 282, 283, 284);
            o["vsBlank"] = vs == null;
            if (vs != null) o["vs"] = b[280] == 11 ? -vs.Value : vs.Value;
            o["powered"] = hdg != null || alt != null;
            o["on"] = new JObject
            {
                ["althold"] = Lit(b[233]), ["app"] = Lit(b[234]), ["cmda"] = Lit(b[235]), ["cmdb"] = Lit(b[236]), ["cwsa"] = Lit(b[237]), ["cwsb"] = Lit(b[238]),
                ["hdgsel"] = Lit(b[239]), ["lnav"] = Lit(b[240]), ["lvlchg"] = Lit(b[241]), ["speed"] = Lit(b[242]), ["vnav"] = Lit(b[243]),
                ["vorloc"] = Lit(b[244]), ["vs"] = Lit(b[245]), ["n1"] = Lit(b[246]),
                ["fdl"] = b[250] != 0, ["fdr"] = b[251] != 0, ["at"] = b[252] != 0,   // A/T sur ARM
            };
            return o;
        }

        // ---- envoi des commandes au module iFly (fenêtre « iFly Plugin »)
        [StructLayout(LayoutKind.Sequential)] struct CopyData { public IntPtr dwData; public int cbData; public IntPtr lpData; }
        [DllImport("user32.dll", CharSet = CharSet.Ansi)] static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string cls, string title);
        [DllImport("user32.dll", CharSet = CharSet.Ansi)] static extern uint RegisterWindowMessage(string name);
        [DllImport("user32.dll")] static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr w, ref CopyData l, uint flags, uint timeout, out IntPtr result);
        const uint WM_COPYDATA = 0x004A, SMTO_ABORTIFHUNG = 0x0002;
        static uint msgId;

        static bool Send(int command, double v1, double v2, double v3)
        {
            IntPtr w = FindWindowEx(IntPtr.Zero, IntPtr.Zero, null, "iFly Plugin - MSFS2024");
            if (w == IntPtr.Zero) w = FindWindowEx(IntPtr.Zero, IntPtr.Zero, null, "iFly Plugin");
            if (w == IntPtr.Zero) return false;
            if (msgId == 0) msgId = RegisterWindowMessage(MsgName);
            // { int Command; (4 octets de bourrage) double Value1, Value2, Value3 } + 2 octets, comme dans le SDK
            var buf = new byte[34];
            BitConverter.GetBytes(command).CopyTo(buf, 0);
            BitConverter.GetBytes(v1).CopyTo(buf, 8); BitConverter.GetBytes(v2).CopyTo(buf, 16); BitConverter.GetBytes(v3).CopyTo(buf, 24);
            var h = GCHandle.Alloc(buf, GCHandleType.Pinned);
            try
            {
                var cd = new CopyData { dwData = (IntPtr)msgId, cbData = buf.Length, lpData = h.AddrOfPinnedObject() };
                IntPtr r;
                return SendMessageTimeout(w, WM_COPYDATA, IntPtr.Zero, ref cd, SMTO_ABORTIFHUNG, 500, out r) != IntPtr.Zero;
            }
            finally { h.Free(); }
        }

        /// <summary>Ordre venu de la fenêtre FMS : { c: "ifly", b: "cmda" } (appui) ou { c: "ifly_set", k: "alt"|"hdg"|"ias"|"vs"|"crs", v }.</summary>
        public static void Command(JObject a)
        {
            string c = JsonStore.Str(a["c"]);
            double v; double.TryParse(JsonStore.Str(a["v"]), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v);
            string b = JsonStore.Str(a["b"]), k = JsonStore.Str(a["k"]);
            Task.Run(() =>   // jamais sur la fenêtre de l'appli : le module iFly peut tarder à répondre
            {
                try
                {
                    if (c == "ifly") { int n; if (Buttons.TryGetValue(b, out n)) Send(n, 0, 0, 0); return; }
                    if (c != "ifly_set") return;
                    switch (k)
                    {
                        case "alt": Send(AltSet, 0, Math.Max(0, Math.Min(50000, Math.Round(v / 100) * 100)), 0); break;
                        case "hdg": Send(HdgSet, 0, Math.Round(((v % 360) + 360) % 360) % 360, 0); break;
                        case "crs": { double h = Math.Round(((v % 360) + 360) % 360) % 360; Send(Crs1Set, 0, h, 0); Send(Crs2Set, 0, h, 0); break; }
                        case "ias":
                            if (v > 0 && v < 1) Send(IasMachSet, 0, 0, Math.Max(0.60, Math.Min(0.82, Math.Round(v, 2))));   // Mach
                            else Send(IasMachSet, 0, 1, Math.Max(100, Math.Min(340, Math.Round(v))));
                            break;
                        case "vs":
                            {
                                double s = Math.Max(-7900, Math.Min(6000, v));
                                s = Math.Abs(s) < 1000 ? Math.Round(s / 50) * 50 : Math.Round(s / 100) * 100;   // pas de 50 sous 1000 ft/min, 100 au-dessus
                                Send(VsSet, 0, s, 0); break;
                            }
                    }
                }
                catch (Exception) { }
            });
        }
    }
}
