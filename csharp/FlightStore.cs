// FMS — étape 1 : mémoire commune du plan de vol.
// Une seule copie du vol en cours, partagée par toutes les fenêtres (FMS, Plan de vol, Plan VFR, Suivi de vol).
// Elle est gardée sur le disque : changer de page, fermer une fenêtre ou relancer l'appli ne fait rien perdre.
// Les pages parlent au coffre par chrome.webview.postMessage({ fms: { op: "get" | "set" | "reset", ... } })
// et reçoivent chaque changement sous la forme { fmsState: {...} } (voir web/fms_store.js).
using System;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    static class FlightStore
    {
        static readonly object Gate = new object();
        static JObject state;

        static string FilePath { get { return Path.Combine(AppInfo.BaseDir, "fms_state.json"); } }

        /// <summary>Prévient toutes les fenêtres ouvertes : texte JSON { fmsState: ... } prêt à envoyer.</summary>
        public static event Action<string> Changed;

        static JObject Empty()
        {
            return new JObject
            {
                ["rev"] = 0,
                ["updated"] = "",
                ["source"] = "",
                ["plan"] = new JObject
                {
                    ["origin"] = new JObject { ["icao"] = "", ["rwy"] = "" },
                    ["dest"] = new JObject { ["icao"] = "", ["rwy"] = "" },
                    ["cruiseAlt"] = 0,
                    ["route"] = new JArray(),      // [{ ident, lat, lon, alt, type, via }]
                    ["departure"] = "",            // procédure de départ choisie
                    ["arrival"] = "",              // procédure d'arrivée choisie
                    ["approach"] = "",             // ex. "ILS 31"
                    ["activeLeg"] = 0              // index du point vers lequel l'avion vole
                },
                ["settings"] = new JObject()       // réglages du FMS (COM auto, pente VPATH…) : étapes suivantes
            };
        }

        static void EnsureLoaded()
        {
            if (state != null) return;
            state = JsonStore.Load(FilePath, Empty());
        }

        /// <summary>Copie du vol en cours.</summary>
        public static JObject Get()
        {
            lock (Gate) { EnsureLoaded(); return (JObject)state.DeepClone(); }
        }

        /// <summary>Applique une modification (seules les parties envoyées changent ; une liste remplace l'ancienne).</summary>
        public static JObject Set(JObject patch, string source)
        {
            JObject copy;
            lock (Gate)
            {
                EnsureLoaded();
                if (patch != null)
                {
                    patch.Remove("rev"); patch.Remove("updated"); patch.Remove("source");
                    state.Merge(patch, new JsonMergeSettings { MergeArrayHandling = MergeArrayHandling.Replace, MergeNullValueHandling = MergeNullValueHandling.Merge });
                }
                Stamp(source);
                copy = (JObject)state.DeepClone();
            }
            Announce(copy);
            return copy;
        }

        /// <summary>« Nouveau vol » : on repart de zéro (les réglages du FMS sont gardés).</summary>
        public static JObject Reset(string source)
        {
            JObject copy;
            lock (Gate)
            {
                EnsureLoaded();
                var settings = state["settings"] as JObject ?? new JObject();
                int rev = (int?)state["rev"] ?? 0;
                state = Empty();
                state["settings"] = settings;
                state["rev"] = rev;
                Stamp(source);
                copy = (JObject)state.DeepClone();
            }
            Announce(copy);
            return copy;
        }

        static void Stamp(string source)
        {
            state["rev"] = ((int?)state["rev"] ?? 0) + 1;
            state["updated"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
            state["source"] = source ?? "";
            try { JsonStore.Save(FilePath, state); } catch (Exception) { }
        }

        static void Announce(JObject copy)
        {
            var h = Changed;
            if (h == null) return;
            string json = new JObject { ["fmsState"] = copy }.ToString(Formatting.None);
            try { h(json); } catch (Exception) { }
        }

        /// <summary>Message { op, patch?, source? } venu d'une page. Renvoie la réponse à lui envoyer (ou null).</summary>
        public static string Handle(JObject msg)
        {
            string op = JsonStore.Str(msg["op"]);
            string source = JsonStore.Str(msg["source"]);
            switch (op)
            {
                case "set": Set(msg["patch"] as JObject, source); return null;         // tout le monde reçoit le changement
                case "reset": Reset(source); return null;
                default: return new JObject { ["fmsState"] = Get() }.ToString(Formatting.None);   // "get"
            }
        }
    }
}
