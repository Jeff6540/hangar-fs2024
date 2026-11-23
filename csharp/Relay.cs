// Relais de la page Plan de vol (port 8765) : trafic IA de MSFS par SimConnect, SimBrief, METAR, plans d'aéroport
// OpenStreetMap et FSHub — mêmes réponses que la 11.8, pour que la page Plan & suivi de vol fonctionne à l'identique.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    // ------------------------------------------------------------------ petit serveur HTTP local (127.0.0.1)
    class MiniHttp
    {
        public delegate void Handler(string path, string query, Response r);
        public class Response
        {
            public int Status = 200;
            public string ContentType = "application/json; charset=utf-8";
            public byte[] Body = new byte[0];
            public bool Cors;
            public void Json(int status, JToken data) { Status = status; Body = Encoding.UTF8.GetBytes(data.ToString(Formatting.None)); }
            public void Text(string s, string type) { ContentType = type; Body = Encoding.UTF8.GetBytes(s); }
        }

        TcpListener listener;
        readonly Handler handler;
        public int Port;
        volatile bool running;

        public MiniHttp(Handler h) { handler = h; }

        public bool Start(int port)
        {
            try
            {
                listener = new TcpListener(IPAddress.Loopback, port);
                listener.Server.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ExclusiveAddressUse, true);
                listener.Start(64);
            }
            catch (Exception) { listener = null; return false; }
            Port = ((IPEndPoint)listener.LocalEndpoint).Port;
            running = true;
            var t = new Thread(Loop) { IsBackground = true, Name = "http-" + Port };
            t.Start();
            return true;
        }

        public void Stop()
        {
            running = false;
            try { if (listener != null) listener.Stop(); } catch (Exception) { }
            listener = null;
        }

        public bool Running { get { return running && listener != null; } }

        void Loop()
        {
            while (running)
            {
                TcpClient c;
                try { c = listener.AcceptTcpClient(); }
                catch (Exception) { if (!running) return; Thread.Sleep(50); continue; }
                ThreadPool.QueueUserWorkItem(_ => Serve(c));
            }
        }

        void Serve(TcpClient c)
        {
            try
            {
                using (c)
                {
                    c.ReceiveTimeout = 15000;
                    var st = c.GetStream();
                    var head = new StringBuilder();
                    var buf = new byte[1];
                    // lecture de l'en-tête (jusqu'à la ligne vide)
                    while (head.Length < 16384)
                    {
                        int n = st.Read(buf, 0, 1);
                        if (n <= 0) return;
                        head.Append((char)buf[0]);
                        if (head.Length >= 4 && head.ToString(head.Length - 4, 4) == "\r\n\r\n") break;
                    }
                    var first = head.ToString().Split(new[] { "\r\n" }, StringSplitOptions.None)[0].Split(' ');
                    if (first.Length < 2) return;
                    string method = first[0].ToUpperInvariant(), target = first[1];
                    int q = target.IndexOf('?');
                    string path = q >= 0 ? target.Substring(0, q) : target, query = q >= 0 ? target.Substring(q + 1) : "";
                    var r = new Response();
                    if (method == "OPTIONS") { r.Status = 204; r.Cors = true; }
                    else
                    {
                        try { handler(path, query, r); }
                        catch (Exception e) { r.Json(500, new JObject { ["error"] = e.Message }); }
                    }
                    var sb = new StringBuilder();
                    sb.Append("HTTP/1.1 ").Append(r.Status).Append(' ').Append(r.Status == 200 ? "OK" : r.Status == 204 ? "No Content" : "Status").Append("\r\n");
                    sb.Append("Content-Type: ").Append(r.ContentType).Append("\r\n");
                    sb.Append("Cache-Control: no-store\r\n");
                    if (r.Cors)
                    {
                        sb.Append("Access-Control-Allow-Origin: *\r\nAccess-Control-Allow-Private-Network: true\r\n");
                        sb.Append("Access-Control-Allow-Methods: GET, OPTIONS\r\nAccess-Control-Allow-Headers: *\r\n");
                    }
                    sb.Append("Content-Length: ").Append(r.Body.Length).Append("\r\nConnection: close\r\n\r\n");
                    var hb = Encoding.ASCII.GetBytes(sb.ToString());
                    st.Write(hb, 0, hb.Length);
                    if (method != "HEAD" && r.Body.Length > 0) st.Write(r.Body, 0, r.Body.Length);
                    st.Flush();
                }
            }
            catch (Exception) { }
        }

        public static Dictionary<string, string> ParseQuery(string q)
        {
            var d = new Dictionary<string, string>();
            foreach (var part in (q ?? "").Split('&'))
            {
                if (part == "") continue;
                int i = part.IndexOf('=');
                string k = Uri.UnescapeDataString((i >= 0 ? part.Substring(0, i) : part).Replace('+', ' '));
                string v = i >= 0 ? Uri.UnescapeDataString(part.Substring(i + 1).Replace('+', ' ')) : "";
                if (!d.ContainsKey(k)) d[k] = v;
            }
            return d;
        }
    }

    // ------------------------------------------------------------------ requêtes web
    static class Web
    {
        static Web() { ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12; }

        public class Result { public int Status; public string Body = ""; public string Error; }

        public static Result Request(string url, Dictionary<string, string> headers, int timeoutMs, byte[] post = null)
        {
            var res = new Result();
            try
            {
                var req = (HttpWebRequest)WebRequest.Create(url);
                req.Timeout = timeoutMs;
                req.ReadWriteTimeout = timeoutMs;
                req.AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate;
                req.UserAgent = AppInfo.Name + "/" + AppInfo.Version;
                if (headers != null)
                    foreach (var kv in headers)
                    {
                        if (kv.Key == "User-Agent") req.UserAgent = kv.Value;
                        else if (kv.Key == "Accept") req.Accept = kv.Value;
                        else if (kv.Key == "Content-Type") req.ContentType = kv.Value;
                        else if (kv.Key == "Referer") req.Referer = kv.Value;
                        else req.Headers[kv.Key] = kv.Value;
                    }
                if (post != null)
                {
                    req.Method = "POST";
                    req.ContentLength = post.Length;
                    using (var s = req.GetRequestStream()) s.Write(post, 0, post.Length);
                }
                using (var resp = (HttpWebResponse)req.GetResponse())
                using (var sr = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                {
                    res.Status = (int)resp.StatusCode;
                    res.Body = sr.ReadToEnd();
                }
            }
            catch (WebException e)
            {
                var hr = e.Response as HttpWebResponse;
                if (hr != null)
                {
                    res.Status = (int)hr.StatusCode;
                    try { using (var sr = new StreamReader(hr.GetResponseStream(), Encoding.UTF8)) res.Body = sr.ReadToEnd(); } catch (Exception) { }
                }
                else res.Error = e.Message;
            }
            catch (Exception e) { res.Error = e.Message; }
            return res;
        }

        public static JToken ParseOrNull(string s)
        {
            try { return string.IsNullOrWhiteSpace(s) ? null : JToken.Parse(s); } catch (Exception) { return null; }
        }
    }

    // ------------------------------------------------------------------ SimConnect (SimConnect.dll de MSFS, chargée à la demande)
    class SimConnectClient : IDisposable
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr LoadLibrary(string path);
        [DllImport("kernel32.dll", CharSet = CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr mod, string name);

        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        delegate int OpenFn(out IntPtr h, [MarshalAs(UnmanagedType.LPStr)] string name, IntPtr hwnd, uint evt, IntPtr hevt, uint cfg);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CloseFn(IntPtr h);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        delegate int AddDefFn(IntPtr h, uint def, [MarshalAs(UnmanagedType.LPStr)] string datum, [MarshalAs(UnmanagedType.LPStr)] string units, int type, float eps, uint id);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int ReqTypeFn(IntPtr h, uint req, uint def, uint radius, int type);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int NextFn(IntPtr h, out IntPtr data, out uint size);
        // FMS : ordres envoyés à l'avion (pilote automatique)
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int MapFn(IntPtr h, uint evt, [MarshalAs(UnmanagedType.LPStr)] string name);
        // FMS : blocs de données des avions à SDK (PMDG)
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CdNameFn(IntPtr h, [MarshalAs(UnmanagedType.LPStr)] string name, uint id);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CdDefFn(IntPtr h, uint def, uint offset, uint size, float eps, uint datum);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CdReqFn(IntPtr h, uint cd, uint req, uint def, int period, int flags, uint origin, uint interval, uint limit);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int PlanLoadFn(IntPtr h, [MarshalAs(UnmanagedType.LPStr)] string file);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int TransmitFn(IntPtr h, uint obj, uint evt, uint data, uint group, uint flags);

        static IntPtr module = IntPtr.Zero;
        static OpenFn open; static CloseFn close; static AddDefFn addDef; static ReqTypeFn reqType; static NextFn next;
        static MapFn mapEvt; static TransmitFn transmit; static PlanLoadFn planLoad;
        static CdNameFn cdName; static CdDefFn cdDef; static CdReqFn cdReq;
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int SetDataFn(IntPtr h, uint def, uint obj, uint flags, uint count, uint size, ref double data);
        static SetDataFn setData;
        IntPtr handle = IntPtr.Zero;

        public static bool Load(string dll)
        {
            if (module != IntPtr.Zero) return true;
            module = LoadLibrary(dll);
            if (module == IntPtr.Zero) return false;
            open = Get<OpenFn>("SimConnect_Open"); close = Get<CloseFn>("SimConnect_Close");
            addDef = Get<AddDefFn>("SimConnect_AddToDataDefinition"); reqType = Get<ReqTypeFn>("SimConnect_RequestDataOnSimObjectType");
            next = Get<NextFn>("SimConnect_GetNextDispatch");
            mapEvt = Get<MapFn>("SimConnect_MapClientEventToSimEvent"); transmit = Get<TransmitFn>("SimConnect_TransmitClientEvent");
            planLoad = Get<PlanLoadFn>("SimConnect_FlightPlanLoad");
            setData = Get<SetDataFn>("SimConnect_SetDataOnSimObject");
            cdName = Get<CdNameFn>("SimConnect_MapClientDataNameToID"); cdDef = Get<CdDefFn>("SimConnect_AddToClientDataDefinition"); cdReq = Get<CdReqFn>("SimConnect_RequestClientData");
            return open != null && close != null && addDef != null && reqType != null && next != null;
        }

        static T Get<T>(string name) where T : class
        {
            var p = GetProcAddress(module, name);
            return p == IntPtr.Zero ? null : Marshal.GetDelegateForFunctionPointer(p, typeof(T)) as T;
        }

        public const int DT_INT32 = 1, DT_FLOAT64 = 4, DT_STRING8 = 5, DT_STRING32 = 6, DT_STRING64 = 7, DT_STRING256 = 9;
        public const uint UNUSED = 0xFFFFFFFF;

        public void Open(string name)
        {
            int hr = open(out handle, name, IntPtr.Zero, 0, IntPtr.Zero, 0);
            if (hr != 0) throw new Exception(Hangar.L("MSFS ne répond pas (SimConnect_Open code ", "MSFS does not answer (SimConnect_Open code ") + ((uint)hr) + ")");
        }
        public int Add(uint def, string datum, string units, int type) { return addDef(handle, def, datum, units, type, 0f, UNUSED); }
        public int Request(uint req, uint def, uint radius, int type) { return reqType(handle, req, def, radius, type); }
        public bool CanSend { get { return mapEvt != null && transmit != null; } }
        public int MapEvent(uint id, string name) { return mapEvt == null ? -1 : mapEvt(handle, id, name); }
        // objet 0 = ton avion ; groupe 1 = priorité la plus haute ; 0x10 = « le groupe est une priorité »
        /// <summary>Bloc de données d'un avion (SDK) : demandé une fois, reçu à chaque changement (message 16).</summary>
        public bool ClientData(string name, uint id, uint def, uint size, uint req)
        {
            if (cdName == null || cdDef == null || cdReq == null) return false;
            if (cdName(handle, name, id) != 0) return false;
            if (cdDef(handle, def, 0, size, 0, 0) != 0) return false;
            return cdReq(handle, id, req, def, 3 /* à chaque changement */, 1 /* seulement si ça change */, 0, 0, 0) == 0;
        }
        /// <summary>Écrit une valeur (définition à une seule variable) sur ton avion.</summary>
        public int SetDouble(uint def, double v) { return setData == null ? -1 : setData(handle, def, 0, 0, 0, 8, ref v); }
        public int LoadPlan(string fileNoExt) { return planLoad == null ? -1 : planLoad(handle, fileNoExt); }   // FMS : plan .PLN chargé comme plan actif
        public int Send(uint id, int data) { return transmit == null ? -1 : transmit(handle, 0, id, unchecked((uint)data), 1, 0x10); }
        public byte[] Next()
        {
            IntPtr p; uint size;
            if (next(handle, out p, out size) != 0 || p == IntPtr.Zero) return null;
            var b = new byte[size];
            Marshal.Copy(p, b, 0, (int)size);
            return b;
        }
        public void Dispose()
        {
            try { if (handle != IntPtr.Zero) close(handle); } catch (Exception) { }
            handle = IntPtr.Zero;
        }

        // ---- 12.9 : données de navigation (import des points RNAV, VOR, ILS, NDB et approches de MSFS)
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int AddFacFn(IntPtr h, uint def, [MarshalAs(UnmanagedType.LPStr)] string field);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        delegate int ReqFacFn(IntPtr h, uint def, uint req, [MarshalAs(UnmanagedType.LPStr)] string icao, [MarshalAs(UnmanagedType.LPStr)] string region);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int ReqListFn(IntPtr h, int type, uint req);
        static AddFacFn addFac; static ReqFacFn reqFac; static ReqListFn reqAll, reqList;

        /// <summary>Fonctions de données d'installations ; false si la SimConnect.dll est trop ancienne.</summary>
        public static bool LoadNav()
        {
            if (module == IntPtr.Zero) return false;
            if (addFac == null) addFac = Get<AddFacFn>("SimConnect_AddToFacilityDefinition");
            if (reqFac == null) reqFac = Get<ReqFacFn>("SimConnect_RequestFacilityData");
            if (reqAll == null) reqAll = Get<ReqListFn>("SimConnect_RequestAllFacilities") ?? Get<ReqListFn>("SimConnect_RequestAllFacilites");
            if (reqList == null) reqList = Get<ReqListFn>("SimConnect_RequestFacilitiesList") ?? Get<ReqListFn>("SimConnect_RequestFacilitesList");
            return addFac != null && reqFac != null && (reqAll != null || reqList != null);
        }
        public static bool HasAll { get { return reqAll != null; } }
        public int AddFac(uint def, string field) { return addFac(handle, def, field); }
        public int ReqFac(uint def, uint req, string icao, string region) { return reqFac(handle, def, req, icao, region ?? ""); }
        /// <summary>Liste mondiale (type 0 aéroports, 1 points, 2 NDB, 3 VOR) ; -1 si impossible.</summary>
        public int ReqAll(int type, uint req)
        {
            if (reqAll != null) return reqAll(handle, type, req);
            if (type == 0 && reqList != null) return reqList(handle, type, req);   // ancienne DLL : la liste des aéroports est déjà mondiale
            return -1;
        }
    }

    // ------------------------------------------------------------------ données partagées du relais
    class RelayState
    {
        public const uint REQ_AI = 1, REQ_USER = 2, DEFINE_ID = 1, REQ_ROUTE = 3, DEFINE_ROUTE = 2, REQ_FLIGHT = 4, DEFINE_FLIGHT = 3, REQ_AP = 5, DEFINE_AP = 4, REQ_PMDG = 6, REQ_A220 = 7, DEFINE_A220 = 23;
        const double STALE = 10.0;
        readonly object gate = new object();
        public volatile bool Connected;
        readonly Dictionary<long, Tuple<double, JObject>> objects = new Dictionary<long, Tuple<double, JObject>>();
        Tuple<double, JObject> user, flight;
        readonly Dictionary<long, string[]> routes = new Dictionary<long, string[]>();
        int exceptions;
        public Action<string> Log = m => { };
        public Func<JObject> PlanInfo = () => null;
        public FshubFeed Fshub;

        public static double Now() { return (DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalSeconds; }

        public void SetConnected(bool v)
        {
            lock (gate)
            {
                Connected = v;
                if (!v) { objects.Clear(); routes.Clear(); user = null; flight = null; Autopilot.Clear(); Pmdg.Clear(); A220.Clear(); }
            }
        }

        static string Text(byte[] b, int off, int len)
        {
            int end = off;
            while (end < off + len && end < b.Length && b[end] != 0) end++;
            return Encoding.UTF8.GetString(b, off, end - off).Trim();
        }

        static string Model(byte[] b, int off, int len)
        {
            string t = Text(b, off, len);
            var m = Regex.Match(t, "AC_MODEL[ _]?([A-Za-z0-9]{2,5})");
            return m.Success ? m.Groups[1].Value.ToUpperInvariant() : t;
        }

        static double D(byte[] b, int off) { return BitConverter.ToDouble(b, off); }

        // message SimConnect reçu -> type ("data", "flight", "route", "exception", "quit", "open", "other")
        public string Handle(byte[] buf)
        {
            if (buf.Length < 12) return null;
            uint msgId = BitConverter.ToUInt32(buf, 8);
            if (msgId == 16 && buf.Length >= 44 && BitConverter.ToUInt32(buf, 12) == REQ_PMDG) { Pmdg.Update(buf, 40); return "pmdg"; }   // FMS : MCP du PMDG 737
            if ((msgId == 28 || msgId == 29) && ComAuto.OnFacility(msgId, buf)) return "freq";   // FMS : fréquences des aéroports (COM auto)
            if (msgId == 8 || msgId == 9)
            {
                if (buf.Length < 20) return "short";
                uint reqId = BitConverter.ToUInt32(buf, 12), objId = BitConverter.ToUInt32(buf, 16);
                const int O = 40;
                if (reqId == REQ_FLIGHT)
                {
                    if (buf.Length < O + 15 * 8) return "other";
                    var v = new double[15];
                    for (int i = 0; i < 15; i++) v[i] = D(buf, O + i * 8);
                    var f = new JObject
                    {
                        ["vs"] = (int)Math.Round(v[0]), ["fuel_kg"] = (int)Math.Round(v[1] * 0.45359237), ["weight_kg"] = (int)Math.Round(v[2] * 0.45359237),
                        ["flaps"] = (int)Math.Round(v[3]), ["flaps_pct"] = (int)Math.Round(v[4]), ["wind_dir"] = (((int)Math.Round(v[5]) % 360) + 360) % 360,
                        ["wind_kt"] = (int)Math.Round(v[6]), ["pbrake"] = v[7] >= 0.5, ["eng"] = v[8] >= 0.5 || v[9] >= 0.5 || v[10] >= 0.5 || v[11] >= 0.5,
                        ["agl"] = (int)Math.Round(v[12]), ["ias"] = (int)Math.Round(v[13]), ["ialt"] = (int)Math.Round(v[14]),
                    };
                    lock (gate) flight = Tuple.Create(Now(), f);
                    return "flight";
                }
                if (reqId == REQ_AP)   // FMS : pilote automatique de ton avion
                {
                    int n = Autopilot.Fields.Length;
                    if (buf.Length < O + n * 8) return "other";
                    var v = new double[n];
                    for (int i = 0; i < n; i++) v[i] = D(buf, O + i * 8);
                    string title;
                    lock (gate) title = user != null ? JsonStore.Str(user.Item2["title"]) : "";
                    Autopilot.Update(v, title);
                    return "ap";
                }
                if (reqId == REQ_A220)   // FMS : FCP de l'Airbus A220 (variables de l'avion)
                {
                    int n = A220.Fields.Length;
                    if (buf.Length < O + n * 8) return "other";
                    var v = new double[n];
                    for (int i = 0; i < n; i++) v[i] = D(buf, O + i * 8);
                    A220.Update(v);
                    return "a220";
                }
                if (reqId == REQ_ROUTE)
                {
                    if (buf.Length < O + 16) return "other";
                    lock (gate) routes[objId] = new[] { Text(buf, O, 8), Text(buf, O + 8, 8) };
                    return "route";
                }
                // "<5di32s64s8s32s256sd" : 5 doubles, 1 entier, 5 textes, 1 double (sans alignement)
                const int SIZE = 40 + 4 + 32 + 64 + 8 + 32 + 256 + 8;
                if (buf.Length < O + SIZE) return "short";
                double lat = D(buf, O), lon = D(buf, O + 8), alt = D(buf, O + 16), hdg = D(buf, O + 24), gs = D(buf, O + 32);
                int ground = BitConverter.ToInt32(buf, O + 40);
                int p = O + 44;
                var rec = new JObject
                {
                    ["id"] = (long)objId, ["lat"] = Math.Round(lat, 5), ["lon"] = Math.Round(lon, 5), ["alt"] = (int)Math.Round(alt),
                    ["hdg"] = (((int)Math.Round(hdg) % 360) + 360) % 360, ["gs"] = (int)Math.Round(gs), ["ground"] = ground != 0,
                    ["agl"] = (int)Math.Round(D(buf, p + 392)),
                    ["callsign"] = Text(buf, p, 32), ["airline"] = Text(buf, p + 32, 64), ["flight"] = Text(buf, p + 96, 8),
                    ["model"] = Model(buf, p + 104, 32), ["title"] = Text(buf, p + 136, 256),
                };
                if (buf.Length >= p + 408) { double trk = D(buf, p + 400); if (!double.IsNaN(trk) && trk != 0) rec["trk"] = (((int)Math.Round(trk) % 360) + 360) % 360; }
                Put(reqId, rec);
                return "data";
            }
            if (msgId == 1)
            {
                exceptions++;
                if (exceptions <= 5 && buf.Length >= 24)
                    Log(string.Format(Hangar.L("SimConnect signale une erreur : code={0}, requête={1}, index={2}", "SimConnect reports an error: code={0}, request={1}, index={2}"),
                        BitConverter.ToUInt32(buf, 12), BitConverter.ToUInt32(buf, 16), BitConverter.ToUInt32(buf, 20)));
                return "exception";
            }
            if (msgId == 3) return "quit";
            if (msgId == 2) return "open";
            return "other";
        }

        void Put(uint reqId, JObject rec)
        {
            double lat = (double)rec["lat"], lon = (double)rec["lon"];
            if ((lat == 0 && lon == 0) || Math.Abs(lat) > 90 || Math.Abs(lon) > 180) return;
            lock (gate)
            {
                if (reqId == REQ_USER) user = Tuple.Create(Now(), rec);
                else
                {
                    // MSFS 2024 indique parfois « en vol » pour des avions IA garés ou au roulage
                    int agl = (int)rec["agl"], gs = (int)rec["gs"];
                    if (!(bool)rec["ground"] && (agl < 50 || (gs < 40 && agl < 500))) rec["ground"] = true;
                    objects[(long)rec["id"]] = Tuple.Create(Now(), rec);
                }
            }
        }

        public int Count()
        {
            double now = Now();
            lock (gate) return objects.Values.Count(o => now - o.Item1 <= STALE);
        }

        public JObject User()
        {
            double now = Now();
            lock (gate) return user != null && now - user.Item1 <= STALE ? user.Item2 : null;
        }

        public JObject Snapshot()
        {
            double now = Now();
            lock (gate)
            {
                foreach (var k in objects.Where(kv => now - kv.Value.Item1 > STALE).Select(kv => kv.Key).ToList()) objects.Remove(k);
                var u = user != null && now - user.Item1 <= STALE ? user.Item2 : null;
                var f = flight != null && now - flight.Item1 <= STALE ? flight.Item2 : null;
                long uid = u != null ? (long)u["id"] : -1;
                var ac = new JArray();
                foreach (var o in objects.Values)
                {
                    var r = o.Item2;
                    if ((long)r["id"] == uid) continue;
                    var c = (JObject)r.DeepClone();
                    string[] rt;
                    if (routes.TryGetValue((long)r["id"], out rt)) { c["from"] = rt[0]; c["to"] = rt[1]; }
                    else { c["from"] = ""; c["to"] = ""; }
                    ac.Add(c);
                }
                return new JObject { ["connected"] = Connected, ["mode"] = "msfs", ["updated"] = Math.Round(now, 1),
                    ["user"] = u, ["flight"] = f, ["aircraft"] = ac };
            }
        }

        // boucle : se connecte à MSFS quand il tourne, se déconnecte proprement quand il se ferme
        public void SimConnectLoop(string dll, CancellationToken stop, Func<bool> simRunning)
        {
            var fields = new[] {
                new object[] { "PLANE LATITUDE", "degrees", SimConnectClient.DT_FLOAT64 }, new object[] { "PLANE LONGITUDE", "degrees", SimConnectClient.DT_FLOAT64 },
                new object[] { "PLANE ALTITUDE", "feet", SimConnectClient.DT_FLOAT64 }, new object[] { "PLANE HEADING DEGREES TRUE", "degrees", SimConnectClient.DT_FLOAT64 },
                new object[] { "GROUND VELOCITY", "knots", SimConnectClient.DT_FLOAT64 }, new object[] { "SIM ON GROUND", "bool", SimConnectClient.DT_INT32 },
                new object[] { "ATC ID", null, SimConnectClient.DT_STRING32 }, new object[] { "ATC AIRLINE", null, SimConnectClient.DT_STRING64 },
                new object[] { "ATC FLIGHT NUMBER", null, SimConnectClient.DT_STRING8 }, new object[] { "ATC MODEL", null, SimConnectClient.DT_STRING32 },
                new object[] { "TITLE", null, SimConnectClient.DT_STRING256 }, new object[] { "PLANE ALT ABOVE GROUND", "feet", SimConnectClient.DT_FLOAT64 },
                new object[] { "GPS GROUND TRUE TRACK", "degrees", SimConnectClient.DT_FLOAT64 },   // route suivie au sol (avec le vent), pour orienter l'icône sur la carte
            };
            var flightFields = new[] {
                new[] { "VERTICAL SPEED", "feet per minute" }, new[] { "FUEL TOTAL QUANTITY WEIGHT", "pounds" }, new[] { "TOTAL WEIGHT", "pounds" },
                new[] { "FLAPS HANDLE INDEX", "number" }, new[] { "FLAPS HANDLE PERCENT", "percent" }, new[] { "AMBIENT WIND DIRECTION", "degrees" },
                new[] { "AMBIENT WIND VELOCITY", "knots" }, new[] { "BRAKE PARKING POSITION", "bool" }, new[] { "GENERAL ENG COMBUSTION:1", "bool" },
                new[] { "GENERAL ENG COMBUSTION:2", "bool" }, new[] { "GENERAL ENG COMBUSTION:3", "bool" }, new[] { "GENERAL ENG COMBUSTION:4", "bool" },
                new[] { "PLANE ALT ABOVE GROUND", "feet" }, new[] { "AIRSPEED INDICATED", "knots" },
                new[] { "INDICATED ALTITUDE", "feet" },   // altitude lue sur l'altimètre (calage QNH ou STD), comme sur le PFD
            };
            const uint RADIUS = 200 * 1000;
            while (!stop.IsCancellationRequested)
            {
                if (!simRunning())
                {
                    SetConnected(false);
                    stop.WaitHandle.WaitOne(3000);
                    continue;
                }
                SimConnectClient client = null;
                try
                {
                    client = new SimConnectClient();
                    client.Open("Hangar FS 2024 - relais");
                    foreach (var f in fields)
                    {
                        int hr = client.Add(DEFINE_ID, (string)f[0], (string)f[1], (int)f[2]);
                        if (hr != 0) throw new Exception(Hangar.L("Variable refusée : ", "Variable refused: ") + f[0]);
                    }
                    bool routeOk = client.Add(DEFINE_ROUTE, "AI TRAFFIC FROMAIRPORT", null, SimConnectClient.DT_STRING8) == 0
                                && client.Add(DEFINE_ROUTE, "AI TRAFFIC TOAIRPORT", null, SimConnectClient.DT_STRING8) == 0;
                    bool flightOk = true;
                    foreach (var f in flightFields)
                        if (client.Add(DEFINE_FLIGHT, f[0], f[1], SimConnectClient.DT_FLOAT64) != 0) { flightOk = false; break; }
                    // FMS : lecture du pilote automatique et ordres vers l'avion
                    bool apOk = true;
                    foreach (var f in Autopilot.Fields)
                        if (client.Add(DEFINE_AP, f[0], f[1], SimConnectClient.DT_FLOAT64) != 0) { apOk = false; break; }
                    bool sendOk = client.CanSend;
                    if (sendOk)
                        for (int i = 0; i < Autopilot.Events.Length; i++)
                            if (client.MapEvent(Autopilot.EventBase + (uint)i, Autopilot.Events[i]) != 0) { sendOk = false; break; }
                    // PMDG 737 : boutons du MCP (« #numéro ») et bloc de données du SDK (diffusé seulement si activé dans les options de l'avion)
                    if (sendOk) foreach (var pe in Pmdg.AllEvents()) client.MapEvent(pe, "#" + pe);
                    client.ClientData(Pmdg.DataName, Pmdg.DataId, Pmdg.DataDef, Pmdg.DataSize, REQ_PMDG);
                    // Airbus A220 : variables du FCP (lues et écrites) et boutons standards qu'il écoute
                    bool a220Ok = true;
                    foreach (var f in A220.Fields)
                        if (client.Add(DEFINE_A220, f[0], f[1], SimConnectClient.DT_FLOAT64) != 0) { a220Ok = false; break; }
                    foreach (var w in A220.Writable) client.Add(w.Key, w.Value, "Bool", SimConnectClient.DT_FLOAT64);
                    if (sendOk) for (int i = 0; i < A220.Events.Length; i++) client.MapEvent(A220.EventBase + (uint)i, A220.Events[i]);
                    // COM auto : fréquences des aéroports du plan, demandées à la volée
                    bool freqOk = SimConnectClient.LoadNav();
                    if (freqOk) foreach (var f in ComAuto.FacFields) if (client.AddFac(ComAuto.DefFreq, f) != 0) { freqOk = false; break; }
                    SetConnected(true);
                    Log(Hangar.L("connecté à MSFS : le trafic IA est envoyé au suivi de vol.", "connected to MSFS: AI traffic is sent to flight tracking."));
                    double nextAi = 0, nextUser = 0, nextRoute = 0;
                    while (!stop.IsCancellationRequested)
                    {
                        double now = Now();
                        if (now >= nextUser)   // ton avion : deux fois par seconde
                        {
                            client.Request(REQ_USER, DEFINE_ID, 0, 0);
                            if (flightOk) client.Request(REQ_FLIGHT, DEFINE_FLIGHT, 0, 0);
                            if (apOk) client.Request(REQ_AP, DEFINE_AP, 0, 0);
                            if (a220Ok) client.Request(REQ_A220, DEFINE_A220, 0, 0);
                            nextUser = now + 0.5;
                        }
                        if (now >= nextAi)     // trafic IA : chaque seconde
                        {
                            if (client.Request(REQ_AI, DEFINE_ID, RADIUS, 2) != 0) throw new Exception(Hangar.L("Demande refusée", "Request refused"));
                            nextAi = now + 1.0;
                        }
                        if (routeOk && now >= nextRoute)   // départ / arrivée de l'IA : ne change pas souvent
                        {
                            client.Request(REQ_ROUTE, DEFINE_ROUTE, RADIUS, 2);
                            nextRoute = now + 5.0;
                        }
                        string planFile;   // FMS : « Envoyer à l'avion »
                        while (FmsExport.PlanLoads.TryDequeue(out planFile))
                        {
                            int hr = client.LoadPlan(planFile);
                            Log(hr == 0 ? Hangar.L("FMS : plan de vol envoyé à MSFS.", "FMS: flight plan sent to MSFS.") : Hangar.L("FMS : MSFS a refusé le plan de vol (code ", "FMS: MSFS refused the flight plan (code ") + (uint)hr + ")");
                        }
                        if (sendOk)   // ordres du FMS (boutons du pilote automatique)
                        {
                            foreach (var o in Autopilot.TakeOrders())
                            {
                                int id = Autopilot.EventId(o.Key);
                                if (id >= 0) client.Send((uint)id, o.Value);
                            }
                            foreach (var o in Pmdg.TakeOrders()) client.Send(o.Key, o.Value);   // PMDG 737 : MCP
                            foreach (var o in A220.TakeOrders(Autopilot.Values())) client.Send(o.Key, o.Value);   // Airbus A220 : FCP
                            foreach (var w in A220.TakeWrites()) client.SetDouble(w.Key, w.Value);
                        }
                        foreach (var fr in ComAuto.TakeRequests())
                            if (!freqOk || client.ReqFac(ComAuto.DefFreq, fr.Key, fr.Value, "") != 0) ComAuto.RequestFailed(fr.Key);
                        bool got = false;
                        while (true)
                        {
                            var b = client.Next();
                            if (b == null) break;
                            got = true;
                            if (Handle(b) == "quit") throw new Exception(Hangar.L("MSFS a été fermé", "MSFS was closed"));
                        }
                        if (!got) Thread.Sleep(30);
                    }
                }
                catch (Exception e)
                {
                    if (Connected) Log(Hangar.L("déconnecté de MSFS (", "disconnected from MSFS (") + e.Message + ").");
                    SetConnected(false);
                    stop.WaitHandle.WaitOne(3000);
                }
                finally { if (client != null) client.Dispose(); }
            }
            SetConnected(false);
        }

        // SimConnect.dll : à côté de l'appli, dans les réglages, le dossier choisi dans Réglages, le SDK, Little Navmap
        static string foundDll, foundKey;
        static readonly object findGate = new object();
        public static string FindSimConnectDll(string extraDir, string launchTarget)
        {
            // la recherche parcourt plusieurs disques : faite une fois par lancement de l'appli (refaite si le réglage change ou si la DLL a disparu)
            string key = (extraDir ?? "") + "|" + (launchTarget ?? "");
            lock (findGate)
            {
                if (foundDll != null && foundKey == key && File.Exists(foundDll)) return foundDll;
                foundDll = FindSimConnectDllNow(extraDir, launchTarget); foundKey = key;
                return foundDll;
            }
        }
        static string FindSimConnectDllNow(string extraDir, string launchTarget)
        {
            var c = new List<string>();
            string here = AppDomain.CurrentDomain.BaseDirectory;
            foreach (var d in new[] { here, AppInfo.BaseDir, extraDir })
                if (!string.IsNullOrEmpty(d)) c.Add(Path.Combine(d, "SimConnect.dll"));
            string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            c.Add(@"C:\MSFS SDK\SimConnect SDK\lib\SimConnect.dll");
            c.Add(@"C:\MSFS 2024 SDK\SimConnect SDK\lib\SimConnect.dll");
            // 12.9 : Little Navmap 3 et autres outils récents livrent une SimConnect.dll de MSFS 2024
            foreach (var root in new[] { Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                                          Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs"), home, Path.Combine(home, "Documents"), @"C:\", @"D:\" })
            {
                try
                {
                    if (string.IsNullOrEmpty(root) || !Directory.Exists(root)) continue;
                    foreach (var d in Directory.GetDirectories(root))
                    {
                        string n = Path.GetFileName(d).ToLowerInvariant();
                        if (!(n.Contains("little nav") || n.Contains("littlenav") || n.Contains("msfs 2024 sdk") || n.Contains("msfs sdk"))) continue;
                        try { foreach (var f in Directory.EnumerateFiles(d, "SimConnect.dll", SearchOption.AllDirectories).Take(12)) c.Add(f); } catch (Exception) { }
                    }
                }
                catch (Exception) { }
            }
            // on préfère une DLL qui sait lire les données de navigation (MSFS 2024), puis une qui sait au moins lire les approches
            string best = null; int bestScore = -1;
            foreach (var p in c.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                try
                {
                    if (!File.Exists(p)) continue;
                    int sc = DllScore(p);
                    if (sc > bestScore) { best = p; bestScore = sc; }
                    if (sc >= 3) break;
                }
                catch (Exception) { }
            }
            if (best == null) return null;
            // copie gardée dans le dossier des réglages pour les prochaines fois (remplacée si on a trouvé mieux)
            try
            {
                string keep = Path.Combine(AppInfo.BaseDir, "SimConnect.dll");
                if (!string.Equals(Path.GetFullPath(best), Path.GetFullPath(keep), StringComparison.OrdinalIgnoreCase) && (!File.Exists(keep) || DllScore(keep) < bestScore))
                    File.Copy(best, keep, true);
            }
            catch (Exception) { }
            return best;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr LoadLibraryEx(string path, IntPtr file, uint flags);
        [DllImport("kernel32.dll", CharSet = CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr mod, string name);
        [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr mod);

        /// <summary>0 : SimConnect seul ; 2 : lit les approches ; 3 : lit aussi les listes mondiales (MSFS 2024).</summary>
        public static int DllScore(string path)
        {
            IntPtr m = IntPtr.Zero;
            try
            {
                m = LoadLibraryEx(path, IntPtr.Zero, 0x00000001 /* DONT_RESOLVE_DLL_REFERENCES : on lit seulement la liste des fonctions */);
                if (m == IntPtr.Zero) return 0;
                bool fac = GetProcAddress(m, "SimConnect_AddToFacilityDefinition") != IntPtr.Zero && GetProcAddress(m, "SimConnect_RequestFacilityData") != IntPtr.Zero;
                bool all = GetProcAddress(m, "SimConnect_RequestAllFacilities") != IntPtr.Zero || GetProcAddress(m, "SimConnect_RequestAllFacilites") != IntPtr.Zero;
                return fac ? (all ? 3 : 2) : 0;
            }
            catch (Exception) { return 0; }
            finally { if (m != IntPtr.Zero) FreeLibrary(m); }
        }
    }

    // ------------------------------------------------------------------ requêtes servies par le relais
    static class RelayApi
    {
        static readonly Dictionary<string, string> UA = new Dictionary<string, string> { { "User-Agent", "HangarFS2024-Relay/1.0" } };

        public static void SimBrief(string query, MiniHttp.Response r)
        {
            var q = MiniHttp.ParseQuery(query);
            string userid, username, qs;
            q.TryGetValue("userid", out userid); q.TryGetValue("username", out username);
            if (!string.IsNullOrEmpty(userid) && Regex.IsMatch(userid, @"^\d{1,12}$")) qs = "userid=" + userid;
            else if (!string.IsNullOrEmpty(username) && Regex.IsMatch(username, @"^[\w .\-]{1,64}$")) qs = "username=" + Uri.EscapeDataString(username);
            else { r.Json(400, new JObject { ["fetch"] = new JObject { ["status"] = Hangar.L("Identifiant SimBrief invalide", "Invalid SimBrief ID") } }); return; }
            var res = Web.Request("https://www.simbrief.com/api/xml.fetcher.php?" + qs + "&json=1", UA, 15000);
            if (res.Error != null) { r.Json(502, new JObject { ["fetch"] = new JObject { ["status"] = Hangar.L("SimBrief injoignable : ", "SimBrief unreachable: ") + res.Error } }); return; }
            var body = Web.ParseOrNull(res.Body) ?? new JObject { ["fetch"] = new JObject { ["status"] = "SimBrief HTTP " + res.Status } };
            r.Json(res.Status == 0 ? 200 : res.Status, body);
        }

        public static void Metar(string query, MiniHttp.Response r)
        {
            string icao;
            MiniHttp.ParseQuery(query).TryGetValue("icao", out icao);
            icao = (icao ?? "").ToUpperInvariant();
            if (!Regex.IsMatch(icao, "^[A-Z0-9]{3,4}$")) { r.Json(400, new JObject { ["error"] = Hangar.L("code aéroport invalide", "invalid airport code") }); return; }
            var sources = new[] { new[] { "https://aviationweather.gov/api/data/metar?format=raw&ids=" + icao, "aviationweather.gov" },
                                  new[] { "https://tgftp.nws.noaa.gov/data/observations/metar/stations/" + icao + ".TXT", "tgftp.nws.noaa.gov" } };
            int down = 0;   // 12.9.3 : sources injoignables (réseau, serveur en panne) ≠ aéroport sans METAR
            foreach (var s in sources)
            {
                var res = Web.Request(s[0], UA, 10000);
                if (res.Error != null || res.Status >= 500) { down++; continue; }
                if (res.Status != 200) continue;
                var lines = res.Body.Split('\n').Select(l => l.Trim()).Where(l => l != "").ToList();
                string metar = lines.FirstOrDefault(l => l.StartsWith(icao)) ?? (lines.Count > 0 ? lines[lines.Count - 1] : "");
                if (metar.Length > 10) { r.Json(200, new JObject { ["metar"] = metar, ["source"] = s[1] }); return; }
            }
            if (down == sources.Length) { r.Json(502, new JObject { ["error"] = Hangar.L("service météo injoignable", "weather service unreachable") }); return; }
            r.Json(404, new JObject { ["error"] = Hangar.L("aucun METAR trouvé", "no METAR found") });
        }

        public static void PlanCurrent(JObject p, MiniHttp.Response r)
        {
            var aps = p != null ? p["airports"] as JArray : null;
            if (aps == null || aps.Count == 0) { r.Json(200, new JObject { ["has"] = false }); return; }
            var prim = aps.Where(a => a["primary"] != null && (bool)a["primary"]).Select(a => JsonStore.Str(a["icao"])).ToList();
            r.Json(200, new JObject { ["has"] = true, ["dep"] = prim.Count > 0 ? prim[0] : "", ["arr"] = prim.Count > 1 ? prim[1] : "",
                ["route"] = JsonStore.Str(p["route"]), ["ofp_id"] = JsonStore.Str(p["ofp_id"]),
                ["generated"] = p["generated"] ?? 0, ["fetched"] = p["fetched"] ?? 0 });
        }

        // ---------------------------------------------------------------- plans d'aéroport (OpenStreetMap, cases de 0,1°)
        static readonly string[] AeroServers = { "https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass.kumi.systems/api/interpreter" };
        static readonly HashSet<string> KeepWays = new HashSet<string>("runway|taxiway|taxilane|apron|parking_position|holding_position|stopway|hangar|terminal".Split('|'));
        static readonly HashSet<string> KeepNodes = new HashSet<string>("parking_position|gate|holding_position".Split('|'));
        static readonly HashSet<string> KeepRels = new HashSet<string> { "apron", "terminal", "hangar" };
        static readonly object aeroLock = new object();
        static string AeroDir { get { return Path.Combine(AppInfo.BaseDir, "plans_aeroports"); } }

        static JArray Pts(JToken geom)
        {
            var pts = new JArray();
            foreach (var g in geom as JArray ?? new JArray())
                if (g is JObject && g["lat"] != null)
                    pts.Add(new JArray(Math.Round((double)g["lat"], 6), Math.Round((double)g["lon"], 6)));
            return pts;
        }

        static JArray Simplify(JToken osm)
        {
            var outp = new JArray();
            foreach (var el in osm["elements"] as JArray ?? new JArray())
            {
                var tags = el["tags"] as JObject ?? new JObject();
                string kind = JsonStore.Str(tags["aeroway"]), typ = JsonStore.Str(el["type"]);
                if (kind == "" || !(typ == "node" ? KeepNodes : typ == "relation" ? KeepRels : KeepWays).Contains(kind)) continue;
                string rf = JsonStore.Str(tags["ref"]);
                if (rf == "") rf = JsonStore.Str(tags["name"]);
                rf = rf.Trim(); if (rf.Length > 24) rf = rf.Substring(0, 24);
                if (typ == "node")
                {
                    if (el["lat"] != null) outp.Add(new JObject { ["t"] = kind, ["r"] = rf, ["g"] = new JArray(new JArray(Math.Round((double)el["lat"], 6), Math.Round((double)el["lon"], 6))) });
                    continue;
                }
                if (typ == "relation")
                {
                    foreach (var mem in el["members"] as JArray ?? new JArray())
                    {
                        var pts = Pts(mem["geometry"]);
                        string role = JsonStore.Str(mem["role"]);
                        if ((role == "outer" || role == "") && pts.Count > 3) outp.Add(new JObject { ["t"] = kind, ["r"] = rf, ["a"] = 1, ["g"] = pts });
                    }
                    continue;
                }
                var p2 = Pts(el["geometry"]);
                if (p2.Count < 2) continue;
                var item = new JObject { ["t"] = kind, ["r"] = rf, ["g"] = p2 };
                if (p2.Count > 3 && JToken.DeepEquals(p2[0], p2[p2.Count - 1]) && (KeepRels.Contains(kind) || JsonStore.Str(tags["area"]) == "yes")) item["a"] = 1;
                double w;
                var ws = JsonStore.Str(tags["width"]).Replace(",", ".").Split(' ');
                if (ws.Length > 0 && double.TryParse(ws[0], NumberStyles.Float, CultureInfo.InvariantCulture, out w) && w > 0 && w < 200) item["w"] = w;
                outp.Add(item);
            }
            return outp;
        }

        // le 1er serveur tout de suite, puis un autre toutes les 8 s ; la 1re bonne réponse gagne
        static JArray FetchBox(double s, double w, double n, double e)
        {
            string q = string.Format(CultureInfo.InvariantCulture, "[out:json][timeout:50];nwr[\"aeroway\"]({0:0.0000},{1:0.0000},{2:0.0000},{3:0.0000});out geom;", s, w, n, e);
            var data = Encoding.ASCII.GetBytes("data=" + Uri.EscapeDataString(q));
            var headers = new Dictionary<string, string> { { "User-Agent", "HangarFS2024/" + AppInfo.Version + " (MSFS add-on manager; airport layouts)" },
                { "Accept", "application/json" }, { "Content-Type", "application/x-www-form-urlencoded" } };
            var tasks = new List<Task<Tuple<bool, string, JToken>>>();
            var errors = new List<string>();
            var deadline = DateTime.UtcNow.AddSeconds(45 + 8 * AeroServers.Length);
            int started = 0;
            Func<string, Task<Tuple<bool, string, JToken>>> launch = url => Task.Run(() =>
            {
                string host = new Uri(url).Host;
                var res = Web.Request(url, headers, 45000, data);
                if (res.Error != null) return Tuple.Create(false, host, (JToken)new JValue(res.Error));
                if (res.Status != 200) return Tuple.Create(false, host, (JToken)new JValue("HTTP " + res.Status));
                var osm = Web.ParseOrNull(res.Body);
                if (osm == null) return Tuple.Create(false, host, (JToken)new JValue("réponse illisible"));
                if (osm["remark"] != null && !((osm["elements"] as JArray ?? new JArray()).Any())) return Tuple.Create(false, host, (JToken)new JValue(JsonStore.Str(osm["remark"])));
                return Tuple.Create(true, host, osm);
            });
            tasks.Add(launch(AeroServers[started++]));
            while (DateTime.UtcNow < deadline && tasks.Count > 0)
            {
                int idx = Task.WaitAny(tasks.Cast<Task>().ToArray(), started < AeroServers.Length ? 8000 : Math.Max(1000, (int)(deadline - DateTime.UtcNow).TotalMilliseconds));
                if (idx < 0)
                {
                    if (started < AeroServers.Length) tasks.Add(launch(AeroServers[started++]));
                    continue;
                }
                var t = tasks[idx];
                tasks.RemoveAt(idx);
                if (t.Result.Item1) return Simplify(t.Result.Item3);
                errors.Add(t.Result.Item2 + " " + JsonStore.Str(t.Result.Item3));
                if (started < AeroServers.Length) tasks.Add(launch(AeroServers[started++]));
            }
            throw new Exception(errors.Count > 0 ? string.Join(" ; ", errors) : Hangar.L("délai dépassé", "timeout"));
        }

        static JArray ReadCell(string k, bool staleOk)
        {
            string path = Path.Combine(AeroDir, k + ".json");
            try
            {
                if (File.Exists(path) && (staleOk || (DateTime.UtcNow - File.GetLastWriteTimeUtc(path)).TotalDays < 30))
                    return JArray.Parse(File.ReadAllText(path, Encoding.UTF8));
            }
            catch (Exception) { }
            return null;
        }

        public static void Aeroway(string query, MiniHttp.Response r)
        {
            var q = MiniHttp.ParseQuery(query);
            string raw;
            if (!q.TryGetValue("cells", out raw)) q.TryGetValue("cell", out raw);
            var keys = new List<string>();
            foreach (var k in (raw ?? "").Split(',').Take(16))
            {
                var m = Regex.Match(k.Trim(), @"^(-?\d{1,3})_(-?\d{1,4})$");
                if (!m.Success) continue;
                int a = int.Parse(m.Groups[1].Value), b = int.Parse(m.Groups[2].Value);
                if (a >= -900 && a < 900 && b >= -1800 && b < 1800) keys.Add(a + "_" + b);
            }
            if (keys.Count == 0) { r.Json(400, new JObject { ["error"] = Hangar.L("case invalide", "invalid cell") }); return; }
            var outc = new JObject();
            var missing = new List<string>();
            foreach (var k in keys) { var it = ReadCell(k, false); if (it == null) missing.Add(k); else outc[k] = it; }
            if (missing.Count == 0) { r.Json(200, new JObject { ["cells"] = outc, ["cached"] = true }); return; }
            lock (aeroLock)
            {
                missing = missing.Where(k => { var it = ReadCell(k, false); if (it != null) { outc[k] = it; return false; } return true; }).ToList();
                if (missing.Count > 0)
                {
                    var idx = missing.Select(k => k.Split('_').Select(int.Parse).ToArray()).ToList();
                    double s = idx.Min(i => i[0]) * 0.1, w = idx.Min(i => i[1]) * 0.1, n = (idx.Max(i => i[0]) + 1) * 0.1, e = (idx.Max(i => i[1]) + 1) * 0.1;
                    JArray items;
                    try { items = FetchBox(s, w, n, e); }
                    catch (Exception ex)
                    {
                        var lost = new List<string>();
                        foreach (var k in missing) { var old = ReadCell(k, true); if (old == null) lost.Add(k); else outc[k] = old; }
                        if (lost.Count == 0) { r.Json(200, new JObject { ["cells"] = outc, ["cached"] = true, ["stale"] = true }); return; }
                        r.Json(502, new JObject { ["error"] = Hangar.L("OpenStreetMap injoignable : ", "OpenStreetMap unreachable: ") + ex.Message, ["cells"] = outc });
                        return;
                    }
                    var parts = missing.ToDictionary(k => k, k => new JArray());
                    foreach (var it in items)
                    {
                        var g = (JArray)it["g"];
                        var mid = (JArray)g[g.Count / 2];
                        string k = (int)Math.Floor((double)mid[0] / 0.1 + 1e-9) + "_" + (int)Math.Floor((double)mid[1] / 0.1 + 1e-9);
                        JArray lst;
                        if (parts.TryGetValue(k, out lst)) lst.Add(it);
                    }
                    try { Directory.CreateDirectory(AeroDir); } catch (Exception) { }
                    foreach (var kv in parts)
                    {
                        outc[kv.Key] = kv.Value;
                        try
                        {
                            string path = Path.Combine(AeroDir, kv.Key + ".json"), tmp = path + ".tmp";
                            File.WriteAllText(tmp, kv.Value.ToString(Formatting.None), new UTF8Encoding(false));
                            if (File.Exists(path)) File.Delete(path);
                            File.Move(tmp, path);
                        }
                        catch (Exception) { }
                    }
                }
            }
            r.Json(200, new JObject { ["cells"] = outc, ["cached"] = false });
        }

        // ---------------------------------------------------------------- FSHub (radar public et vol d'un pilote)
        public static readonly Dictionary<string, string> Phases = new Dictionary<string, string> {
            { "level_flight", "palier" }, { "cruise", "croisière" }, { "climbing", "montée" }, { "descending", "descente" }, { "approach", "approche" },
            { "landing", "atterrissage" }, { "takeoff", "décollage" }, { "taxiing_to_runway", "roulage vers la piste" }, { "taxiing_to_gate", "roulage vers le parking" },
            { "awaiting_departure", "attente au départ" }, { "parked", "au parking" }, { "pushback", "repoussage" }, { "boarding", "embarquement" },
            { "deboarding", "débarquement" }, { "on_approach", "approche" }, { "take_off", "décollage" }, { "taking_off", "décollage" }, { "landed", "atterri" },
            { "taxiing", "roulage" }, { "go_around", "remise de gaz" }, { "holding", "attente" }, { "on_ground", "au sol" }, { "in_flight", "en vol" },
            { "final", "finale" }, { "on_final", "finale" }, { "rejected_takeoff", "décollage interrompu" } };

        static readonly Dictionary<string, string> MoveHeaders = new Dictionary<string, string> {
            { "Accept", "application/json" }, { "Origin", "https://fshub.io" }, { "Referer", "https://fshub.io/" } };

        public static string Icao(JToken v)
        {
            if (v is JObject)
            {
                foreach (var k in new[] { "icao", "ident", "code", "icao_code" })
                    if (v[k] != null && v[k].Type == JTokenType.String && JsonStore.Str(v[k]).Trim() != "") return JsonStore.Str(v[k]).Trim().ToUpperInvariant();
                return "";
            }
            if (v != null && v.Type == JTokenType.String && Regex.IsMatch(JsonStore.Str(v).Trim(), "^[A-Za-z0-9]{3,4}$")) return JsonStore.Str(v).Trim().ToUpperInvariant();
            return "";
        }

        public static JObject ParsePlan(JToken payload)
        {
            JToken d = payload is JObject && payload["data"] != null ? payload["data"] : payload;
            if (d is JArray) d = ((JArray)d).Count > 0 ? d[0] : null;
            var o = d as JObject;
            if (o == null || !o.HasValues) return null;
            Func<string[], string> pick = keys => { foreach (var k in keys) if (o[k] != null) { string c = Icao(o[k]); if (c != "") return c; } return ""; };
            string dep = pick(new[] { "departure", "dep", "origin", "from", "departure_icao", "dep_icao", "departure_airport" });
            string arr = pick(new[] { "arrival", "arr", "destination", "to", "arrival_icao", "arr_icao", "arrival_airport" });
            JToken ac = o["aircraft"] ?? o["aircraft_icao"] ?? o["aircraft_type"];
            string acs;
            if (ac is JObject) acs = JsonStore.Str(ac["icao"] ?? ac["icao_code"] ?? ac["name"] ?? ac["type"]);
            else acs = JsonStore.Str(ac);
            if (acs.Length > 24) acs = acs.Substring(0, 24);
            return new JObject { ["dep"] = dep, ["arr"] = arr, ["aircraft"] = acs };
        }

        static JToken Num(JToken f, string k)
        {
            double v;
            return double.TryParse(JsonStore.Str(f[k]), NumberStyles.Float, CultureInfo.InvariantCulture, out v) ? (JToken)(int)Math.Round(v) : JValue.CreateNull();
        }

        // vols en cours (radar FSHub) : code de VA, ou null pour le radar global
        public static Tuple<JArray, JToken> RadarFlights(string code)
        {
            string url = code == null ? "https://movements.api.fshub.io/all/lite" : "https://movements.api.fshub.io/airline/" + Uri.EscapeDataString(code) + "/lite";
            var res = Web.Request(url, MoveHeaders, 12000);
            if (res.Error != null) throw new Exception(Hangar.L("radar FSHub injoignable (", "FSHub radar unreachable (") + res.Error + ")");
            if (res.Status != 200) throw new Exception("radar FSHub : HTTP " + res.Status);
            var payload = Web.ParseOrNull(res.Body);
            var flights = payload is JObject ? payload["flights"] as JArray : null;
            if (flights == null) throw new Exception(Hangar.L("radar FSHub : réponse inattendue", "FSHub radar: unexpected answer"));
            var outp = new JArray();
            foreach (var f in flights.OfType<JObject>())
            {
                var pilot = f["pilot"] as JObject ?? new JObject();
                double lat, lon;
                JToken jlat = JValue.CreateNull(), jlon = JValue.CreateNull();
                if (double.TryParse(JsonStore.Str(f["lat"]), NumberStyles.Float, CultureInfo.InvariantCulture, out lat)
                    && double.TryParse(JsonStore.Str(f["lng"] ?? f["lon"]), NumberStyles.Float, CultureInfo.InvariantCulture, out lon)
                    && !(Math.Abs(lat) < 1.0 && Math.Abs(lon) < 1.0)) { jlat = lat; jlon = lon; }
                var plan = f["plan"] is JObject ? ParsePlan(f["plan"]) : null;
                if (plan == null || (JsonStore.Str(plan["dep"]) == "" && JsonStore.Str(plan["arr"]) == "")) plan = ParsePlan(f) ?? plan;
                string phase = JsonStore.Str(f["phase"]), ph;
                if (Hangar.Lang == "en" || !Phases.TryGetValue(phase, out ph)) ph = phase.Replace("_", " ");
                string fid = JsonStore.Str(f["id"]), icao = JsonStore.Str(f["icao"]);
                string route = plan == null ? "" : string.Join(" → ", new[] { JsonStore.Str(plan["dep"]), JsonStore.Str(plan["arr"]) }.Where(x => x != ""));
                bool gnd = f["gnd"] != null && f["gnd"].Type == JTokenType.Boolean ? (bool)f["gnd"] : JsonStore.Str(f["gnd"]) != "" && JsonStore.Str(f["gnd"]) != "0" && JsonStore.Str(f["gnd"]).ToLowerInvariant() != "false";
                string pname = JsonStore.Str(pilot["name"]);
                outp.Add(new JObject
                {
                    ["id"] = pilot["id"] ?? f["id"], ["pid"] = pilot["id"], ["fid"] = Regex.IsMatch(fid, "^[A-Za-z0-9_-]{1,64}$") ? (JToken)fid : JValue.CreateNull(),
                    ["name"] = pname != "" ? pname : "Pilote", ["lat"] = jlat, ["lon"] = jlon, ["hdg"] = Num(f, "hdg"), ["gs"] = Num(f, "ktas"), ["alt"] = Num(f, "altf"),
                    ["aircraft"] = Regex.IsMatch(icao, "^[A-Za-z0-9-]{2,8}$") ? icao : "", ["phase"] = ph, ["route"] = route,
                    ["ground"] = gnd, ["flying"] = !gnd, ["live"] = true, ["va"] = f["airline"] != null && f["airline"].Type == JTokenType.Integer ? f["airline"] : JValue.CreateNull(),
                });
            }
            return Tuple.Create(outp, payload);
        }

        static JObject allCache; static double allTime;
        static readonly object allLock = new object();

        public static void FshubAll(MiniHttp.Response r)
        {
            lock (allLock)
            {
                if (allCache != null && RelayState.Now() - allTime < 10) { r.Json(200, allCache); return; }
                Tuple<JArray, JToken> res;
                try { res = RadarFlights(null); }
                catch (Exception e) { r.Json(502, new JObject { ["enabled"] = false, ["error"] = e.Message, ["pilots"] = new JArray() }); return; }
                var keep = new[] { "id", "pid", "fid", "lat", "lon", "hdg", "gs", "alt", "aircraft", "phase", "ground", "va" };
                var pilots = new JArray();
                foreach (var p in res.Item1.OfType<JObject>().Where(p => p["lat"].Type != JTokenType.Null))
                {
                    var o = new JObject();
                    foreach (var k in keep) o[k] = p[k] ?? JValue.CreateNull();
                    pilots.Add(o);
                }
                allCache = new JObject { ["enabled"] = true, ["pilots"] = pilots, ["total"] = res.Item2 is JObject ? (res.Item2["total"] ?? JValue.CreateNull()) : JValue.CreateNull(),
                    ["updated"] = Math.Round(RelayState.Now()) };
                allTime = RelayState.Now();
                r.Json(200, allCache);
            }
        }

        static JToken MovementsGet(string path)
        {
            var res = Web.Request("https://movements.api.fshub.io" + path, MoveHeaders, 10000);
            if (res.Error != null) throw new Exception(Hangar.L("FSHub injoignable (", "FSHub unreachable (") + res.Error + ")");
            if (res.Status == 404) return null;
            if (res.Status != 200) throw new Exception("FSHub : HTTP " + res.Status);
            return Web.ParseOrNull(res.Body);
        }

        static JArray LinesOf(JToken geo)
        {
            if (geo != null && geo.Type == JTokenType.String) geo = Web.ParseOrNull((string)geo);
            var raw = new List<JArray>();
            Action<JToken> walk = null;
            walk = g =>
            {
                var o = g as JObject;
                if (o == null) return;
                string t = JsonStore.Str(o["type"]);
                if (o["features"] is JArray) foreach (var f in (JArray)o["features"]) walk(f);
                else if (o["geometry"] is JObject) walk(o["geometry"]);
                else if (t == "LineString") raw.Add(o["coordinates"] as JArray ?? new JArray());
                else if (t == "MultiLineString") foreach (var l in o["coordinates"] as JArray ?? new JArray()) raw.Add(l as JArray ?? new JArray());
            };
            walk(geo);
            var lines = new JArray();
            foreach (var ln in raw)
            {
                var pts = new JArray();
                foreach (var c in ln)
                {
                    var a = c as JArray;
                    double lon, lat;
                    if (a == null || a.Count < 2) continue;
                    if (!double.TryParse(JsonStore.Str(a[0]), NumberStyles.Float, CultureInfo.InvariantCulture, out lon)
                        || !double.TryParse(JsonStore.Str(a[1]), NumberStyles.Float, CultureInfo.InvariantCulture, out lat)) continue;
                    if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) pts.Add(new JArray(Math.Round(lat, 5), Math.Round(lon, 5)));
                }
                if (pts.Count > 1) lines.Add(pts);
            }
            return lines;
        }

        static readonly Dictionary<string, Tuple<double, JToken>> flightCache = new Dictionary<string, Tuple<double, JToken>>();

        public static void FshubFlight(string query, MiniHttp.Response r)
        {
            var q = MiniHttp.ParseQuery(query);
            string pid, fid;
            q.TryGetValue("pilot", out pid); q.TryGetValue("flight", out fid);
            pid = pid ?? ""; fid = fid ?? "";
            if (pid != "" && !Regex.IsMatch(pid, @"^\d{1,12}$")) pid = "";
            if (fid != "" && !Regex.IsMatch(fid, "^[A-Za-z0-9_-]{1,64}$")) fid = "";
            if (pid == "" && fid == "") { r.Json(400, new JObject { ["ok"] = false, ["error"] = Hangar.L("identifiant manquant", "missing ID") }); return; }
            double now = RelayState.Now();
            var res = new JObject { ["ok"] = true, ["plan"] = null, ["path"] = new JArray() };
            var errors = new List<string>();
            lock (flightCache)
            {
                foreach (var k in flightCache.Where(kv => now - kv.Value.Item1 > 600).Select(kv => kv.Key).ToList()) flightCache.Remove(k);
                Tuple<double, JToken> c;
                if (pid != "")
                {
                    if (flightCache.TryGetValue("p" + pid, out c) && now - c.Item1 < 120) res["plan"] = c.Item2;
                    else
                    {
                        try
                        {
                            var d = MovementsGet("/pilot/" + pid) ?? new JObject();
                            var af = d["active_flight"] is JObject ? d["active_flight"] : d;
                            var pl = af is JObject ? af["plan"] as JObject : null;
                            JToken plan = JValue.CreateNull();
                            if (pl != null)
                            {
                                var lines = LinesOf(pl["geo_json"]);
                                var coords = lines.Count > 0 ? (JArray)lines[0] : new JArray();
                                var wp = (pl["waypoints"] as JArray ?? new JArray()).Where(w => w.Type == JTokenType.String || w.Type == JTokenType.Integer)
                                    .Select(w => { string s = JsonStore.Str(w); return s.Length > 12 ? s.Substring(0, 12) : s; }).Take(coords.Count).ToList();
                                if (coords.Count > 0)
                                {
                                    string cr = JsonStore.Str(pl["cruise_lvl"]), rt = JsonStore.Str(pl["route"]);
                                    plan = new JObject { ["coords"] = coords, ["wpts"] = new JArray(wp), ["dep"] = Icao(pl["departure"]), ["arr"] = Icao(pl["arrival"]),
                                        ["cruise"] = cr.Length > 8 ? cr.Substring(0, 8) : cr, ["route"] = rt.Length > 600 ? rt.Substring(0, 600) : rt };
                                }
                            }
                            flightCache["p" + pid] = Tuple.Create(now, plan);
                            res["plan"] = plan;
                        }
                        catch (Exception e) { errors.Add(e.Message); if (c != null) res["plan"] = c.Item2; }
                    }
                }
                if (fid != "")
                {
                    if (flightCache.TryGetValue("f" + fid, out c) && now - c.Item1 < 30) res["path"] = c.Item2;
                    else
                    {
                        try
                        {
                            var lines = LinesOf(MovementsGet("/path/" + fid + "/geojson"));
                            int total = lines.Sum(x => ((JArray)x).Count);
                            if (total > 2000)
                            {
                                int step = total / 2000 + 1;
                                var light = new JArray();
                                foreach (JArray x in lines)
                                {
                                    var y = new JArray();
                                    for (int i = 0; i < x.Count; i += step) y.Add(x[i]);
                                    if ((x.Count - 1) % step != 0) y.Add(x[x.Count - 1]);
                                    light.Add(y);
                                }
                                lines = light;
                            }
                            flightCache["f" + fid] = Tuple.Create(now, (JToken)lines);
                            res["path"] = lines;
                        }
                        catch (Exception e) { errors.Add(e.Message); if (c != null) res["path"] = c.Item2; }
                    }
                }
            }
            bool noPlan = res["plan"] == null || res["plan"].Type == JTokenType.Null;
            bool noPath = !(res["path"] is JArray) || ((JArray)res["path"]).Count == 0;
            if (errors.Count > 0 && noPlan && noPath) { r.Json(502, new JObject { ["ok"] = false, ["error"] = errors[0] }); return; }
            r.Json(200, res);
        }
    }

    // ------------------------------------------------------------------ pilotes de la VA FSHub (interrogé seulement quand la carte est ouverte)
    class FshubFeed
    {
        readonly Func<string> getToken, getVa;
        readonly object gate = new object();
        double lastRequest;
        JObject me, airline;
        public string IdentToken = "";
        readonly Dictionary<string, double[]> prev = new Dictionary<string, double[]>();
        readonly Dictionary<string, Tuple<double, JObject>> plans = new Dictionary<string, Tuple<double, JObject>>();
        JObject data = new JObject { ["enabled"] = false, ["status"] = "aucune VA FSHub réglée", ["pilots"] = new JArray() };
        readonly AutoResetEvent wake = new AutoResetEvent(false);

        public FshubFeed(Func<string> token, Func<string> va)
        {
            getToken = token; getVa = va;
            new Thread(Loop) { IsBackground = true, Name = "fshub" }.Start();
        }

        public JObject Snapshot()
        {
            lastRequest = RelayState.Now();
            wake.Set();
            lock (gate) return (JObject)data.DeepClone();
        }

        void Set(JObject kw)
        {
            if (kw["pilots"] is JArray) foreach (var p in ((JArray)kw["pilots"]).OfType<JObject>()) p["name"] = "";
            lock (gate) foreach (var prop in kw.Properties()) data[prop.Name] = prop.Value;
        }

        void Loop()
        {
            while (true)
            {
                string token = (getToken() ?? "").Trim();
                if (RelayState.Now() - lastRequest < 120)
                {
                    try { Poll(token); }
                    catch (Exception e) { Set(new JObject { ["enabled"] = true, ["status"] = e.Message }); }
                }
                double t0 = RelayState.Now();
                wake.WaitOne(6000);
                Thread.Sleep((int)(Math.Max(0.5, 4.0 - (RelayState.Now() - t0)) * 1000));
            }
        }

        // ---- API FSHub avec la clé personnelle
        public static JToken Get(string path, string token, int timeout = 12000)
        {
            var res = Web.Request("https://fshub.io/api/v3" + path, new Dictionary<string, string> {
                { "X-Pilot-Token", token }, { "Accept", "application/json" }, { "Content-Type", "application/json" } }, timeout);
            if (res.Error != null) throw new Exception(Hangar.L("FSHub injoignable (", "FSHub unreachable (") + res.Error + ")");
            if (res.Status == 204) return null;
            if (res.Status == 401 || res.Status == 403) throw new UnauthorizedAccessException(Hangar.L("clé FSHub refusée (vérifie ou régénère ta clé)", "FSHub key refused (check or regenerate your key)"));
            if (res.Status != 200) throw new Exception("FSHub HTTP " + res.Status + " " + path.Split('?')[0]);
            return Web.ParseOrNull(res.Body);
        }

        static List<JObject> ListOf(JToken payload)
        {
            var d = payload is JObject ? payload["data"] : payload;
            if (d is JArray) return ((JArray)d).OfType<JObject>().ToList();
            if (d is JObject) return new List<JObject> { (JObject)d };
            return new List<JObject>();
        }

        public static JObject[] Identify(string token, string va)
        {
            var meT = (Get("/user", token) ?? new JObject())["data"];
            var meO = meT is JArray ? (((JArray)meT).Count > 0 ? meT[0] as JObject : null) : meT as JObject;
            if (meO == null || JsonStore.Str(meO["id"]) == "")
                throw new Exception(Hangar.L("profil FSHub introuvable (réponse de /user sans identifiant)", "FSHub profile not found (/user returned no ID)"));
            List<JObject> airlines;
            try { airlines = ListOf(Get("/pilot/" + JsonStore.Str(meO["id"]) + "/airline", token) ?? new JObject()); }
            catch (UnauthorizedAccessException) { throw; }
            catch (Exception) { airlines = new List<JObject>(); }
            if (airlines.Count == 0 && meO["airline"] != null)
                airlines = meO["airline"] is JArray ? ((JArray)meO["airline"]).OfType<JObject>().ToList() : (meO["airline"] is JObject ? new List<JObject> { (JObject)meO["airline"] } : new List<JObject>());
            if (airlines.Count == 0) throw new Exception(Hangar.L("ton profil FSHub n'est membre d'aucune compagnie", "your FSHub profile is not a member of any airline"));
            va = (va ?? "").Trim().ToUpperInvariant();
            var pick = airlines.FirstOrDefault(a => va != "" && JsonStore.Str(a["abbr"]).ToUpperInvariant() == va);
            if (pick == null) pick = va != "" ? new JObject { ["id"] = null, ["name"] = va, ["abbr"] = va } : airlines[0];
            return new[] { new JObject { ["id"] = meO["id"], ["name"] = JsonStore.Str(meO["name"]) },
                           new JObject { ["id"] = pick["id"], ["name"] = JsonStore.Str(pick["name"]), ["abbr"] = JsonStore.Str(pick["abbr"]) } };
        }

        static JObject PilotRec(JObject p)
        {
            var gps = p["gps"] as JObject ?? new JObject();
            double lat, lon;
            bool ok = double.TryParse(JsonStore.Str(gps["lat"]), NumberStyles.Float, CultureInfo.InvariantCulture, out lat)
                    & double.TryParse(JsonStore.Str(gps["lng"] ?? gps["lon"]), NumberStyles.Float, CultureInfo.InvariantCulture, out lon);
            string name = JsonStore.Str(p["name"]);
            return new JObject { ["id"] = p["id"], ["name"] = name != "" ? name : "Pilote", ["lat"] = ok ? (JToken)lat : JValue.CreateNull(), ["lon"] = ok ? (JToken)lon : JValue.CreateNull() };
        }

        static List<JObject> AirlinePages(string token, string airlineId, string firstQ)
        {
            var outp = new List<JObject>();
            string cursor = null;
            for (int page = 0; page < 6; page++)
            {
                string q = cursor == null ? firstQ : "?cursor=" + Uri.EscapeDataString(cursor) + (firstQ != "" ? "&" + firstQ.Substring(1) : "");
                var payload = Get("/airline/" + airlineId + "/pilot" + q, token) ?? new JObject();
                foreach (var p in ListOf(payload)) if (p["is_online"] != null && p["is_online"].Type == JTokenType.Boolean && (bool)p["is_online"]) outp.Add(PilotRec(p));
                string nxt = payload is JObject ? JsonStore.Str(payload.SelectToken("meta.cursor.next")) : "";
                if (nxt == "" || nxt == cursor) break;
                cursor = nxt;
            }
            return outp;
        }

        public static Tuple<List<JObject>, string> OnlinePilots(string token, string airlineId)
        {
            Exception first = null;
            foreach (var fq in new[] { "?limit=100", "", "?limit=50" })
            {
                try { return Tuple.Create(AirlinePages(token, airlineId, fq), "airline"); }
                catch (Exception e) { if (!e.Message.Contains("404")) throw; first = e; }
            }
            JToken payload;
            try { payload = Get("/user/friends", token) ?? new JObject(); }
            catch (Exception) { throw first; }
            return Tuple.Create(ListOf(payload).Where(p => p["is_online"] != null && p["is_online"].Type == JTokenType.Boolean && (bool)p["is_online"]).Select(PilotRec).ToList(), "friends");
        }

        JObject PlanOf(string token, string pilotId, double now)
        {
            Tuple<double, JObject> cached;
            if (plans.TryGetValue(pilotId, out cached) && now - cached.Item1 < 120) return cached.Item2;
            JObject plan;
            try { plan = RelayApi.ParsePlan(Get("/pilot/" + pilotId + "/flight-plan", token, 8000) ?? new JObject()); }
            catch (UnauthorizedAccessException) { throw; }
            catch (Exception e)
            {
                if (e.Message.Contains("404")) plan = null;
                else return cached != null ? cached.Item2 : null;
            }
            plans[pilotId] = Tuple.Create(now, plan);
            return plan;
        }

        static double[] BearingNm(double a, double b, double c, double d)
        {
            double la1 = a * Math.PI / 180, la2 = c * Math.PI / 180, dl = (d - b) * Math.PI / 180;
            double y = Math.Sin(dl) * Math.Cos(la2), x = Math.Cos(la1) * Math.Sin(la2) - Math.Sin(la1) * Math.Cos(la2) * Math.Cos(dl);
            double brg = (Math.Atan2(y, x) * 180 / Math.PI + 360) % 360;
            double h = Math.Pow(Math.Sin((la2 - la1) / 2), 2) + Math.Cos(la1) * Math.Cos(la2) * Math.Pow(Math.Sin(dl / 2), 2);
            return new[] { brg, 2 * 3440.065 * Math.Asin(Math.Min(1, Math.Sqrt(h))) };
        }

        void Poll(string token)
        {
            double now = RelayState.Now();
            string va = Regex.Replace((getVa() ?? "").ToUpperInvariant(), "[^A-Z0-9]", "");
            if (va.Length > 8) va = va.Substring(0, 8);
            string sig = token + "|" + va;
            if (token != "" && (sig != IdentToken || airline == null))
            {
                try { var r = Identify(token, va); me = r[0]; airline = r[1]; IdentToken = sig; }
                catch (Exception) { me = null; airline = va != "" ? new JObject { ["id"] = null, ["name"] = va, ["abbr"] = va } : null; }
            }
            else if (token == "")
            {
                me = null; IdentToken = sig;
                airline = va != "" ? new JObject { ["id"] = null, ["name"] = va, ["abbr"] = va } : null;
            }
            if (airline == null)
            {
                Set(new JObject { ["enabled"] = false, ["status"] = Hangar.L("aucune VA FSHub réglée", "no FSHub VA set"), ["airline"] = null, ["me"] = null, ["pilots"] = new JArray() });
                return;
            }
            Exception radarError;
            try
            {
                if (JsonStore.Str(airline["abbr"]) == "") throw new Exception(Hangar.L("code de la VA inconnu", "unknown VA code"));
                var res = RelayApi.RadarFlights(JsonStore.Str(airline["abbr"]));
                string meId = me != null ? JsonStore.Str(me["id"]) : "";
                foreach (var p in res.Item1.OfType<JObject>()) p["me"] = meId != "" && JsonStore.Str(p["id"]) == meId;
                int nAir = res.Item1.Count(p => (bool)p["flying"]);
                Set(new JObject { ["enabled"] = true, ["status"] = string.Format(Hangar.L("{0} pilote(s) en ligne · {1} en vol", "{0} pilot(s) online · {1} flying"), res.Item1.Count, nAir),
                    ["airline"] = airline.DeepClone(), ["me"] = me != null ? me.DeepClone() : null, ["pilots"] = res.Item1, ["source"] = "radar", ["updated"] = Math.Round(now) });
                return;
            }
            catch (Exception e)
            {
                if (token == "") throw;
                radarError = e;
            }
            if (JsonStore.Str(airline["id"]) == "") throw radarError;
            var found = OnlinePilots(token, JsonStore.Str(airline["id"]));
            var pilots = new JArray();
            foreach (var p in found.Item1)
            {
                string id = JsonStore.Str(p["id"]);
                p["me"] = me != null && id == JsonStore.Str(me["id"]);
                if (p["lat"].Type != JTokenType.Null && Math.Abs((double)p["lat"]) < 1.0 && Math.Abs((double)p["lon"]) < 1.0) { p["lat"] = null; p["lon"] = null; }
                var plan = PlanOf(token, id, now);
                p["route"] = plan != null ? string.Join(" → ", new[] { JsonStore.Str(plan["dep"]), JsonStore.Str(plan["arr"]) }.Where(x => x != "")) : "";
                p["aircraft"] = plan != null ? JsonStore.Str(plan["aircraft"]) : "";
                double[] old;
                prev.TryGetValue(id, out old);
                double hdg = old != null ? old[3] : double.NaN, gs = old != null ? old[4] : double.NaN, until = old != null ? old[5] : 0;
                if (p["lat"].Type != JTokenType.Null)
                {
                    double lat = (double)p["lat"], lon = (double)p["lon"];
                    if (old != null && !double.IsNaN(old[1]))
                    {
                        var bd = BearingNm(old[1], old[2], lat, lon);
                        if (bd[1] > 2)
                        {
                            hdg = bd[0]; gs = bd[1] / (Math.Max(5.0, now - old[0]) / 3600.0); until = now + 300;
                            prev[id] = new[] { now, lat, lon, hdg, gs, until };
                        }
                    }
                    else prev[id] = new[] { now, lat, lon, double.NaN, double.NaN, 0 };
                }
                bool moving = now < until && !double.IsNaN(gs) && gs >= 50;
                bool flying = plan != null || moving;
                p["flying"] = flying;
                p["hdg"] = !double.IsNaN(hdg) && flying ? (JToken)(int)Math.Round(hdg) : JValue.CreateNull();
                p["gs"] = !double.IsNaN(gs) && moving ? (JToken)(int)Math.Round(gs) : JValue.CreateNull();
                p["ground"] = !flying;
                pilots.Add(p);
            }
            int fly = pilots.Count(p => (bool)p["flying"]);
            Set(new JObject { ["enabled"] = true,
                ["status"] = string.Format(Hangar.L("{0} pilote(s) en ligne · {1} en vol{2}", "{0} pilot(s) online · {1} flying{2}"), pilots.Count, fly,
                    found.Item2 == "airline" ? "" : Hangar.L(" (amis FSHub : liste de la compagnie refusée)", " (FSHub friends: airline list refused)")),
                ["airline"] = found.Item2 == "airline" ? airline.DeepClone() : new JObject { ["id"] = null, ["name"] = Hangar.L("Amis FSHub", "FSHub friends"), ["abbr"] = "" },
                ["me"] = me != null ? me.DeepClone() : null, ["pilots"] = pilots, ["source"] = found.Item2, ["updated"] = Math.Round(now) });
        }
    }
}
