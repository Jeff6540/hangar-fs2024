using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json.Linq;

namespace HangarFS2024
{
    /// <summary>
    /// Mise à jour en un clic depuis les versions publiées sur GitHub.
    /// Les réglages, profils et liens sont dans %AppData%\HangarFS2024 : ils ne sont jamais touchés.
    /// Les fichiers en cours d'utilisation (l'appli elle-même, ses DLL) sont renommés en .old — Windows le permet —
    /// puis remplacés ; les .old sont effacés au démarrage suivant.
    /// </summary>
    public static class Updater
    {
        const string Repo = "Jeff6540/hangar-fs2024";
        static string LatestApi { get { return "https://api.github.com/repos/" + Repo + "/releases/latest"; } }
        public static string AppDir { get { return AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/'); } }

        /// <summary>Compare deux numéros de version (12.3 &lt; 12.10).</summary>
        public static int Compare(string a, string b)
        {
            int[] pa = Parts(a), pb = Parts(b);
            for (int i = 0; i < Math.Max(pa.Length, pb.Length); i++)
            {
                int x = i < pa.Length ? pa[i] : 0, y = i < pb.Length ? pb[i] : 0;
                if (x != y) return x < y ? -1 : 1;
            }
            return 0;
        }
        static int[] Parts(string v)
        {
            v = (v ?? "").Trim().TrimStart('v', 'V');
            return v.Split('.').Select(p => { int n; return int.TryParse(new string(p.TakeWhile(char.IsDigit).ToArray()), out n) ? n : 0; }).ToArray();
        }

        static string Get(string url)
        {
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.UserAgent = AppInfo.Name + "/" + AppInfo.Version;
            req.Accept = "application/vnd.github+json";
            req.Timeout = 15000;
            using (var resp = req.GetResponse())
            using (var sr = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                return sr.ReadToEnd();
        }

        /// <summary>Renvoie la nouvelle version si elle est plus récente, sinon null.</summary>
        public static JObject Check()
        {
            var rel = JObject.Parse(Get(LatestApi));
            string tag = JsonStore.Str(rel["tag_name"]);
            if (tag == "" || Compare(tag, AppInfo.Version) <= 0) return null;
            var asset = (rel["assets"] as JArray ?? new JArray()).OfType<JObject>()
                .FirstOrDefault(x => JsonStore.Str(x["name"]).StartsWith("Hangar_FS2024_v") && JsonStore.Str(x["name"]).EndsWith(".zip"));
            if (asset == null) return null;
            string url = JsonStore.Str(asset["browser_download_url"]);
            if (!url.StartsWith("https://github.com/" + Repo + "/releases/download/")) return null;   // uniquement les versions officielles
            return new JObject
            {
                ["version"] = tag.TrimStart('v', 'V'),
                ["url"] = url,
                ["size"] = asset["size"],
                ["digest"] = JsonStore.Str(asset["digest"]),
                ["page"] = JsonStore.Str(rel["html_url"]),
                ["notes"] = JsonStore.Str(rel["body"]),   // texte de la page de version (FR, puis EN après ---)
            };
        }

        /// <summary>Supprime les fichiers .old laissés par une mise à jour précédente.</summary>
        public static void CleanupOld()
        {
            try
            {
                foreach (var f in Directory.GetFiles(AppDir, "*.old", SearchOption.AllDirectories))
                    try { File.Delete(f); } catch (Exception) { }
                string tmp = Path.Combine(Path.GetTempPath(), "HangarFS2024_update");
                if (Directory.Exists(tmp)) try { Directory.Delete(tmp, true); } catch (Exception) { }
            }
            catch (Exception) { }
        }

        static bool CanWrite(string dir)
        {
            try
            {
                string t = Path.Combine(dir, ".write_test_" + Guid.NewGuid().ToString("N"));
                File.WriteAllText(t, "x"); File.Delete(t); return true;
            }
            catch (Exception) { return false; }
        }

        /// <summary>Télécharge, vérifie et installe la nouvelle version, puis relance l'appli. progress(0..100, texte).</summary>
        public static void Apply(JObject info, Action<int, string> progress)
        {
            string app = AppDir;
            if (!CanWrite(app))
                throw new Exception(Hangar.L("Le dossier de l'appli est protégé en écriture. Relance Hangar FS 2024 en administrateur, ou télécharge la nouvelle version à la main.",
                                             "The app folder is write-protected. Restart Hangar FS 2024 as administrator, or download the new version manually."));
            string tmp = Path.Combine(Path.GetTempPath(), "HangarFS2024_update");
            if (Directory.Exists(tmp)) try { Directory.Delete(tmp, true); } catch (Exception) { }
            Directory.CreateDirectory(tmp);
            string zip = Path.Combine(tmp, "update.zip");

            // 1) téléchargement
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            var req = (HttpWebRequest)WebRequest.Create(JsonStore.Str(info["url"]));
            req.UserAgent = AppInfo.Name + "/" + AppInfo.Version;
            req.Timeout = 30000;
            using (var resp = req.GetResponse())
            using (var src = resp.GetResponseStream())
            using (var dst = File.Create(zip))
            {
                long total = resp.ContentLength > 0 ? resp.ContentLength : (info["size"] != null ? (long)info["size"] : 0), done = 0;
                var buf = new byte[81920]; int n, last = -1;
                while ((n = src.Read(buf, 0, buf.Length)) > 0)
                {
                    dst.Write(buf, 0, n); done += n;
                    int pc = total > 0 ? (int)(done * 90 / total) : 0;
                    if (pc != last) { last = pc; progress(pc, Hangar.L("Téléchargement…", "Downloading…")); }
                }
            }

            // 2) vérification de l'empreinte publiée par GitHub (quand elle est fournie)
            string digest = JsonStore.Str(info["digest"]);
            if (digest.StartsWith("sha256:"))
            {
                string want = digest.Substring(7).ToLowerInvariant(), got;
                using (var sha = SHA256.Create())
                using (var fs = File.OpenRead(zip))
                    got = BitConverter.ToString(sha.ComputeHash(fs)).Replace("-", "").ToLowerInvariant();
                if (got != want) throw new Exception(Hangar.L("Le fichier téléchargé est abîmé (empreinte différente). Réessaie plus tard.",
                                                              "The downloaded file is damaged (checksum mismatch). Try again later."));
            }

            // 3) décompression
            progress(92, Hangar.L("Installation…", "Installing…"));
            string unz = Path.Combine(tmp, "new");
            ZipFile.ExtractToDirectory(zip, unz);
            string root = unz;
            var exe = Directory.GetFiles(unz, "Hangar FS 2024.exe", SearchOption.AllDirectories).FirstOrDefault();
            if (exe == null) throw new Exception(Hangar.L("Archive de mise à jour invalide.", "Invalid update archive."));
            root = Path.GetDirectoryName(exe);

            // 4) remplacement des fichiers (les fichiers en cours d'utilisation sont d'abord renommés en .old)
            foreach (var f in Directory.GetFiles(root, "*", SearchOption.AllDirectories))
            {
                string rel = f.Substring(root.Length).TrimStart('\\', '/');
                string target = Path.Combine(app, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                if (File.Exists(target))
                {
                    try { File.Copy(f, target, true); continue; } catch (Exception) { }
                    string old = target + ".old";
                    try { if (File.Exists(old)) File.Delete(old); } catch (Exception) { }
                    File.Move(target, old);
                }
                File.Copy(f, target, true);
            }
            progress(100, Hangar.L("Redémarrage…", "Restarting…"));

            // 5) relance : la nouvelle appli attend que celle-ci soit fermée (--wait-mutex)
            string newExe = Path.Combine(app, "Hangar FS 2024.exe");
            Process.Start(new ProcessStartInfo(newExe, "--wait-mutex --updated") { UseShellExecute = false, WorkingDirectory = app });
        }
    }
}
