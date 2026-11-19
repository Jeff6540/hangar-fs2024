using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    /// <summary>Journal de vol : un fichier par vol terminé dans %AppData%\HangarFS2024\journal.</summary>
    public static class Journal
    {
        static string Dir { get { return Path.Combine(AppInfo.BaseDir, "journal"); } }
        static string FileOf(string id) { return Regex.IsMatch(id ?? "", "^[0-9]{6,16}$") ? Path.Combine(Dir, id + ".json") : null; }

        public static void Save(JObject rec)
        {
            try
            {
                string f = FileOf(JsonStore.Str(rec["id"])); if (f == null) return;
                Directory.CreateDirectory(Dir);
                File.WriteAllText(f, rec.ToString(Formatting.None), Encoding.UTF8);
            }
            catch (Exception) { }
        }

        public static void Delete(string id)
        {
            try { string f = FileOf(id); if (f != null && File.Exists(f)) File.Delete(f); } catch (Exception) { }
        }

        public static string Get(string id)
        {
            try { string f = FileOf(id); return f != null && File.Exists(f) ? File.ReadAllText(f, Encoding.UTF8) : "null"; } catch (Exception) { return "null"; }
        }

        /// <summary>Liste des vols (le plus récent d'abord), sans les points de trajectoire.</summary>
        public static JArray List()
        {
            var arr = new JArray();
            try
            {
                if (!Directory.Exists(Dir)) return arr;
                foreach (var f in Directory.GetFiles(Dir, "*.json").OrderByDescending(x => Path.GetFileName(x)).Take(300))
                {
                    try
                    {
                        var j = JObject.Parse(File.ReadAllText(f, Encoding.UTF8));
                        arr.Add(new JObject { ["id"] = j["id"], ["t0"] = j["t0"], ["t1"] = j["t1"], ["dep"] = j["dep"], ["arr"] = j["arr"], ["type"] = j["type"], ["cs"] = j["cs"] });
                    }
                    catch (Exception) { }
                }
            }
            catch (Exception) { }
            return arr;
        }
    }
}
