# Met le tutoriel (web/tutorial_fr.html et tutorial_en.html) à jour pour la version C# :
# installation (un .exe), VATSIM / IVAO, trafic plus rapide et mouvement fluide.
import sys, os

R = {
 "fr": [
  ("Windows : l'appli est un dossier prêt à l'emploi, rien d'autre à installer. Il contient son propre Python officiel (dossier <code>runtime</code>, programme signé par la Python Software Foundation) et l'appli compilée (dossier <code>app</code>) : pas de .exe inconnu que les antivirus pourraient prendre pour un virus.",
   "Windows 10 ou 11 : l'appli est un dossier prêt à l'emploi, rien d'autre à installer. Elle est écrite en C# et utilise des éléments déjà présents dans Windows (.NET Framework 4.8 et le moteur d'affichage WebView2 d'Edge). Le programme <code>Hangar FS 2024.exe</code> passe sans alerte sur VirusTotal (0 détection, Microsoft Defender compris)."),
  ("puis double-clique sur <code>Hangar FS 2024.bat</code> (si Windows affiche « Windows a protégé votre ordinateur » : <b>Informations complémentaires</b> puis <b>Exécuter quand même</b>). Au premier lancement, l'appli propose un raccourci « Hangar FS 2024 » sur le Bureau. Supprimé par erreur ? Réglages &gt; <b>🖥 Créer le raccourci sur le Bureau</b> le recrée.",
   "puis double-clique sur <code>Hangar FS 2024.exe</code> (si Windows affiche « Windows a protégé votre ordinateur » : <b>Informations complémentaires</b> puis <b>Exécuter quand même</b> ; c'est normal pour un programme récent, ce n'est pas une alerte virus). Pour avoir un raccourci « Hangar FS 2024 » sur le Bureau : Réglages &gt; <b>🖥 Créer le raccourci sur le Bureau</b>. Tes réglages d'une ancienne version (11.x) sont repris tels quels."),
  ("<p><b>Ta trajectoire</b></p>",
   "<p><b>Pilotes VATSIM et IVAO</b></p><p>À côté de <b>🌍 TOUTES LES VA FSHUB</b>, les boutons <b>VATSIM</b> (vert) et <b>IVAO</b> (rouge) affichent les pilotes connectés à ces réseaux en ligne. Chaque bouton s'active ou se désactive d'un clic, ils sont désactivés par défaut et ton choix est gardé. Le chiffre du bouton compte les pilotes affichés. Au survol : indicatif, type d'avion, départ → arrivée, altitude, vitesse et cap (pas de nom de pilote). Les avions au sol n'apparaissent que si le bouton <b>Au sol</b> est actif, et ton propre avion n'est pas affiché en double si tu voles connecté.</p><p>Le menu du <b>rayon</b> (partout, 150, 300 ou 500 NM, le long de ma route) s'applique aussi à VATSIM et IVAO : avec plus de 1 000 pilotes connectés dans le monde, un rayon autour de ton avion garde la carte lisible. Les données sont publiques et gratuites, sans compte ni clé ; les réseaux ne les mettent à jour que toutes les 15 secondes, l'appli ne les demande donc pas plus souvent.</p><p><b>Mouvement fluide</b> : ton avion est relu deux fois par seconde et le trafic IA chaque seconde. Entre deux mises à jour, les avions glissent en douceur au lieu de sauter, et ceux de VATSIM et IVAO avancent selon leur cap et leur vitesse jusqu'à la position suivante.</p><p><b>Ta trajectoire</b></p>"),
  ("Quitte avec ✕ Quitter, termine les pythonw.exe restants dans le Gestionnaire des tâches, remplace le fichier, relance, puis Ctrl+F5 dans la fenêtre de la page",
   "Quitte avec ✕ Quitter, remplace le dossier de l'appli par le nouveau, relance, puis F5 dans la fenêtre de la page"),
  ("<tr><td>Plan &amp; suivi de vol : « Relais arrêté »</td>",
   "<tr><td>Ni trafic IA ni suivi de mon avion alors que MSFS tourne</td><td>Le fichier SimConnect.dll, fourni à côté de Hangar FS 2024.exe, a été supprimé ou bloqué : remets le dossier de l'appli d'origine, ou indique le dossier de SimConnect.dll dans Réglages, puis relance l'appli</td></tr><tr><td>Plan &amp; suivi de vol : « Relais arrêté »</td>"),
  ("<p><b>Partager l'appli</b> : envoie le zip fabriqué par FABRIQUER.bat (dossier A PARTAGER). Rien à installer pour tes amis ;",
   "<p><b>Partager l'appli</b> : donne plutôt le lien de la page flightsim.to ou de GitHub, pour que chacun ait la version officielle. Rien à installer pour tes amis ;"),
  ("c'est un faux positif fréquent avec les applis Python non signées",
   "c'est un faux positif possible avec les applis non signées (la version 12.0 est à 0 alerte sur VirusTotal)"),  ("avec, au survol, le type d'avion, la phase de vol",
   "avec, d'un clic sur l'avion, le type d'avion, la phase de vol"),
  ("Le chiffre du bouton compte les pilotes affichés. Au survol : indicatif,",
   "Le chiffre du bouton compte les pilotes affichés. Pour garder la carte lisible, ces avions n'ont pas d'étiquette : un clic sur un avion affiche son indicatif,"),
  ("(pas de nom de pilote). Les avions au sol n'apparaissent que si",
   "(pas de nom de pilote) ; un clic ailleurs sur la carte referme la bulle. Les avions au sol n'apparaissent que si"),
  ("Affiche les avions IA de MSFS, colorés par catégorie ; au sol ils restent gris",
   "Affiche les avions IA de MSFS, colorés par catégorie ; au sol ils restent gris. Un clic sur un avion affiche ses informations"),
 ],
 "en": [
  ("Windows: the app is a ready-to-use folder, nothing else to install. It contains its own official Python (<code>runtime</code> folder, program signed by the Python Software Foundation) and the compiled app (<code>app</code> folder): no unknown .exe that antivirus software could take for a virus.",
   "Windows 10 or 11: the app is a ready-to-use folder, nothing else to install. It is written in C# and uses components already built into Windows (.NET Framework 4.8 and Edge's WebView2 display engine). The <code>Hangar FS 2024.exe</code> program passes VirusTotal without any alert (0 detections, Microsoft Defender included)."),
  ("then double-click <code>Hangar FS 2024.bat</code> (if Windows shows \"Windows protected your PC\": <b>More info</b> then <b>Run anyway</b>). On first launch, the app offers a \"Hangar FS 2024\" shortcut on the Desktop. Deleted it by mistake? Settings &gt; <b>🖥 Create the Desktop shortcut</b> brings it back.",
   "then double-click <code>Hangar FS 2024.exe</code> (if Windows shows \"Windows protected your PC\": <b>More info</b> then <b>Run anyway</b>; this is normal for a recent program, it is not a virus alert). For a \"Hangar FS 2024\" shortcut on the Desktop: Settings &gt; <b>🖥 Create the Desktop shortcut</b>. Your settings from an older version (11.x) are kept as they are."),
  ("<p><b>Your track</b></p>",
   "<p><b>VATSIM and IVAO pilots</b></p><p>Next to <b>🌍 ALL FSHUB VAS</b>, the <b>VATSIM</b> (green) and <b>IVAO</b> (red) buttons show the pilots connected to these online networks. Each button turns on or off with a click; they are off by default and your choice is kept. The number on the button counts the pilots shown. On hover: callsign, aircraft type, departure → arrival, altitude, speed and heading (no pilot name). Aircraft on the ground only show when the <b>On ground</b> button is active, and your own aircraft is not shown twice if you fly connected.</p><p>The <b>range</b> menu (everywhere, 150, 300 or 500 NM, along my route) also applies to VATSIM and IVAO: with more than 1,000 pilots connected worldwide, a range around your aircraft keeps the map readable. The data is public and free, with no account or key; the networks only update it every 15 seconds, so the app doesn't ask more often.</p><p><b>Smooth movement</b>: your aircraft is read twice per second and AI traffic every second. Between two updates, aircraft glide smoothly instead of jumping, and VATSIM and IVAO aircraft move along their heading and speed until the next position.</p><p><b>Your track</b></p>"),
  ("Quit with ✕ Quit, end any remaining pythonw.exe in Task Manager, replace the file and restart",
   "Quit with ✕ Quit, replace the app folder with the new one, restart, then F5 in the page window"),
  ("<tr><td>Port 8765 is already taken</td>",
   "<tr><td>No AI traffic and no tracking of my aircraft while MSFS is running</td><td>The SimConnect.dll file, supplied next to Hangar FS 2024.exe, was deleted or blocked: put back the original app folder, or set the SimConnect.dll folder in Settings, then restart the app</td></tr><tr><td>Port 8765 is already taken</td>"),
  ("<p><b>Sharing the app</b>: send the zip made by FABRIQUER.bat (A PARTAGER folder). Nothing to install for your friends;",
   "<p><b>Sharing the app</b>: share the flightsim.to or GitHub page link instead, so everyone gets the official version. Nothing to install for your friends;"),
  ("it is a common false positive with unsigned Python apps",
   "it is a possible false positive with unsigned apps (version 12.0 has 0 alerts on VirusTotal)"),  ("showing, on hover, the aircraft type, flight phase",
   "showing, when you click the aircraft, the aircraft type, flight phase"),
  ("The number on the button counts the pilots shown. On hover: callsign,",
   "The number on the button counts the pilots shown. To keep the map readable, these aircraft have no label: click an aircraft to see its callsign,"),
  ("(no pilot name). Aircraft on the ground only",
   "(no pilot name); click elsewhere on the map to close the bubble. Aircraft on the ground only"),
  ("Shows MSFS AI aircraft, coloured by category; on the ground they stay grey",
   "Shows MSFS AI aircraft, coloured by category; on the ground they stay grey. Click an aircraft to see its details"),
 ],
}

if __name__ == "__main__":
    web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for lang, pairs in R.items():
        p = os.path.join(web, "tutorial_%s.html" % lang)
        s = open(p, encoding="utf-8").read()
        for a, b in pairs:
            if b in s or a not in s:
                continue  # déjà fait
            assert s.count(a) == 1, (lang, a[:60], s.count(a))
            s = s.replace(a, b)
        open(p, "w", encoding="utf-8").write(s)
        print("ok :", p)
