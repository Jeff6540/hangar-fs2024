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
   "<p><b>Pilotes VATSIM et IVAO</b></p><p>À côté de <b>🌍 TOUTES LES VA FSHUB</b>, les boutons <b>VATSIM</b> (vert) et <b>IVAO</b> (rouge) affichent les pilotes connectés à ces réseaux en ligne. Chaque bouton s'active ou se désactive d'un clic, ils sont désactivés par défaut et ton choix est gardé. Le chiffre du bouton compte les pilotes affichés. Au survol : indicatif, type d'avion, départ → arrivée, altitude, vitesse et cap (pas de nom de pilote). Les avions au sol n'apparaissent que si le bouton <b>Au sol</b> est actif, et ton propre avion n'est pas affiché en double si tu voles connecté.</p><p>Le menu du <b>rayon</b> (partout, 150, 300 ou 500 NM, le long de ma route) s'applique aussi à VATSIM et IVAO : avec plus de 1 000 pilotes connectés dans le monde, un rayon autour de ton avion garde la carte lisible. Les données sont publiques et gratuites, sans compte ni clé ; les réseaux ne les mettent à jour que toutes les 15 secondes, l'appli ne les demande donc pas plus souvent.</p><p><b>Mouvement fluide</b> : ton avion est relu deux fois par seconde et le trafic IA chaque seconde. Entre deux mises à jour, les avions glissent en douceur au lieu de sauter, et ceux de VATSIM et IVAO avancent selon leur cap et leur vitesse jusqu'à la position suivante.</p><p><b>Ta trajectoire</b></p>", "<p><b>Pilotes VATSIM et IVAO</b></p>"),
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
  ("affichent les pilotes connectés à ces réseaux en ligne.",
   "affichent les pilotes connectés à ces réseaux en ligne. Sur la carte, les avions VATSIM sont verts, et les avions IVAO gris foncé bordés de rouge, pour ne pas les confondre avec les gros porteurs du trafic IA (rouges)."),
  ("coche « Démarrer avec Windows » et « En mode administrateur » dans Réglages.",
   "coche « Toujours ouvrir Hangar FS 2024 en mode administrateur » dans Réglages."),
  ("<td>🛡 En mode administrateur</td><td>Au démarrage du PC, l'appli s'ouvre en administrateur sans confirmation Windows</td>",
   "<td>🛡 Toujours ouvrir en mode administrateur</td><td>L'appli s'ouvre toujours en administrateur, sans confirmation Windows. Indépendant de « Démarrer avec Windows »</td>"),
  ("La case « En mode administrateur » est utile",
   "La case « Toujours ouvrir Hangar FS 2024 en mode administrateur » est utile"),
  ("Elle fait passer l'appli en administrateur sans confirmation Windows : au démarrage du PC, et aussi quand tu l'ouvres d'un double-clic.",
   "Elle fait passer l'appli en administrateur sans confirmation Windows chaque fois qu'elle s'ouvre (double-clic, raccourci, ou démarrage du PC si « Démarrer avec Windows » est coché). Les deux cases sont indépendantes : le mode administrateur ne fait pas démarrer l'appli avec Windows."),
  ("ou active le démarrage avec Windows en mode administrateur</td>",
   "ou coche « Toujours ouvrir en mode administrateur » dans Réglages</td>"),
  ("Dans la Bibliothèque, la case d'un add-on présent dans Community devient orange (bleue = simplement cochée)",
   "Dans la Bibliothèque, la case d'un add-on présent dans Community devient bleu ciel, sur une ligne bleu foncé (jaune = simplement cochée)"),
  ("dans la colonne Community = l'add-on est dans Community.</li>",
   "dans la colonne Community = l'add-on est dans Community.</li><li>Quand tu sélectionnes un add-on déjà dans Community (pour le retirer), sa coche disparaît : la case devient <b>vide, bordée de bleu</b>. Elle montre ce qui restera après « Retirer de Community ».</li>"),
  ("<li>Le bandeau en haut, puis les six onglets : Bibliothèque, Carte addons, Démarrage auto, Vol SimBrief, Plan &amp; suivi de vol, Réglages.</li><li>La barre du bas : messages, état du relais (bouton ⏻ pour l'arrêter ou le relancer), état du simulateur et bouton rouge <b>✕ Quitter</b>.</li>",
   "<li>Le <b>menu à gauche</b> : Bibliothèque, Carte addons, Démarrage auto, Vol SimBrief, Plan &amp; suivi de vol, Réglages (la petite flèche ↗ signale une page qui s'ouvre dans sa propre fenêtre).</li><li>En bas du menu : l'état du relais (point vert = MSFS connecté, orange = en attente, gris = arrêté) avec le bouton ⏻ pour l'arrêter ou le relancer, l'état du simulateur et le bouton rouge <b>✕ Quitter</b>.</li><li>Le bouton <b>« Réduire le menu</b> replie le menu en une fine colonne d'icônes, pour laisser plus de place aux listes ; <b>»</b> le redéplie. Ton choix est gardé.</li><li>En haut à droite : les drapeaux de langue et le bouton Tutoriel. En bas de la fenêtre : la ligne des messages.</li>"),
  ("<p><b>Lire la liste de gauche</b></p>",
   "<p><b>Les chiffres en haut</b> : add-ons dans Community, scènes d'aéroport reconnues, dossiers réels (add-ons copiés directement dans Community) et liens cassés (en rouge s'il y en a).</p><p><b>Lire la liste de gauche</b></p>"),
  ("<li>Les <b>drapeaux</b> 🇫🇷 et 🇬🇧, à droite des onglets,", "<li>Les <b>drapeaux</b> 🇫🇷 et 🇬🇧, en haut à droite,"),
  ("avec les drapeaux à droite des onglets (voir", "avec les drapeaux en haut à droite (voir"),
  ("<figcaption>À droite des onglets : les drapeaux", "<figcaption>En haut à droite : les drapeaux"),
  ("<b>La case « 🅿 Vérifier que l'avion est sur un aéroport connu »</b>", "<b>La tuile « Vérifier que l'avion est sur un aéroport connu (🅿) »</b>"),
  ("au survol du 🅿 et de la case.", "au survol du 🅿 et de la tuile."),
  ("<li>Règle le démarrage et les options (tableau ci-dessous), puis <b>Enregistrer</b>.</li>", "<li>Règle le démarrage et les options : chaque choix est une <b>tuile</b> ; un clic l'allume (voyant allumé et « ON ») ou l'éteint (tableau ci-dessous). Puis <b>Enregistrer</b>.</li>"),
  ("<td>Décoche pour garder l'appli dans la liste sans la lancer</td>", "<td>Éteins cette tuile pour garder l'appli dans la liste sans la lancer</td>"),
  ("<li>L'appli affiche la route et les aéroports trouvés (départ, arrivée et, si « Inclure les aéroports de dégagement » est coché, les dégagements), avec les scènes correspondantes de ta bibliothèque.</li>",
   "<li>L'appli affiche le départ et l'arrivée en grand, comme sur un billet, puis la route et les aéroports trouvés (départ, arrivée et, si la tuile « Inclure les aéroports de dégagement » est allumée, les dégagements), avec les scènes correspondantes de ta bibliothèque.</li>"),
  ("si « Retirer les scènes automatiquement à la fermeture du simulateur » est coché, et le plan", "si la tuile « Retirer les scènes automatiquement à la fermeture du simulateur » est allumée, et le plan"),
  ("<li><b>Terminer le vol (retirer les scènes)</b> retire le vol en cours", "<li>Les <b>options du vol</b> sont des tuiles : un clic l'allume (voyant et « ON ») ou l'éteint. Un bandeau vert sous les boutons rappelle le vol en cours.</li><li><b>■ Terminer le vol (retirer les scènes)</b>, le bouton orange, retire le vol en cours"),
  ("<li><b>Ne charger que les scènes du vol</b> : cochée,", "<li><b>Ne charger que les scènes du vol</b> : tuile allumée,"),
 ],
 "en": [
  ("Windows: the app is a ready-to-use folder, nothing else to install. It contains its own official Python (<code>runtime</code> folder, program signed by the Python Software Foundation) and the compiled app (<code>app</code> folder): no unknown .exe that antivirus software could take for a virus.",
   "Windows 10 or 11: the app is a ready-to-use folder, nothing else to install. It is written in C# and uses components already built into Windows (.NET Framework 4.8 and Edge's WebView2 display engine). The <code>Hangar FS 2024.exe</code> program passes VirusTotal without any alert (0 detections, Microsoft Defender included)."),
  ("then double-click <code>Hangar FS 2024.bat</code> (if Windows shows \"Windows protected your PC\": <b>More info</b> then <b>Run anyway</b>). On first launch, the app offers a \"Hangar FS 2024\" shortcut on the Desktop. Deleted it by mistake? Settings &gt; <b>🖥 Create the Desktop shortcut</b> brings it back.",
   "then double-click <code>Hangar FS 2024.exe</code> (if Windows shows \"Windows protected your PC\": <b>More info</b> then <b>Run anyway</b>; this is normal for a recent program, it is not a virus alert). For a \"Hangar FS 2024\" shortcut on the Desktop: Settings &gt; <b>🖥 Create the Desktop shortcut</b>. Your settings from an older version (11.x) are kept as they are."),
  ("<p><b>Your track</b></p>",
   "<p><b>VATSIM and IVAO pilots</b></p><p>Next to <b>🌍 ALL FSHUB VAS</b>, the <b>VATSIM</b> (green) and <b>IVAO</b> (red) buttons show the pilots connected to these online networks. Each button turns on or off with a click; they are off by default and your choice is kept. The number on the button counts the pilots shown. On hover: callsign, aircraft type, departure → arrival, altitude, speed and heading (no pilot name). Aircraft on the ground only show when the <b>On ground</b> button is active, and your own aircraft is not shown twice if you fly connected.</p><p>The <b>range</b> menu (everywhere, 150, 300 or 500 NM, along my route) also applies to VATSIM and IVAO: with more than 1,000 pilots connected worldwide, a range around your aircraft keeps the map readable. The data is public and free, with no account or key; the networks only update it every 15 seconds, so the app doesn't ask more often.</p><p><b>Smooth movement</b>: your aircraft is read twice per second and AI traffic every second. Between two updates, aircraft glide smoothly instead of jumping, and VATSIM and IVAO aircraft move along their heading and speed until the next position.</p><p><b>Your track</b></p>", "<p><b>VATSIM and IVAO pilots</b></p>"),
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
  ("show the pilots connected to these online networks.",
   "show the pilots connected to these online networks. On the map, VATSIM aircraft are green and IVAO aircraft are dark grey with a red outline, so they are not mixed up with AI heavies (red)."),
  ("tick \"Start with Windows\" and \"As administrator\" in Settings.",
   "tick \"Always open Hangar FS 2024 in administrator mode\" in Settings."),
  ("<td>🛡 As administrator</td><td>At PC startup, the app opens as administrator without Windows confirmation</td>",
   "<td>🛡 Always open in administrator mode</td><td>The app always opens as administrator, without Windows confirmation. Independent from \"Start with Windows\"</td>"),
  ("The \"As administrator\" box is useful",
   "The \"Always open Hangar FS 2024 in administrator mode\" box is useful"),
  ("It makes the app run as administrator without Windows confirmation: at PC startup, and also when you open it with a double-click.",
   "It makes the app run as administrator without Windows confirmation every time it opens (double-click, shortcut, or PC startup if \"Start with Windows\" is ticked). Both boxes are independent: administrator mode does not make the app start with Windows."),
  ("or enable Windows startup in administrator mode</td>",
   "or tick \"Always open in administrator mode\" in Settings</td>"),
  ("In the Library, the box of an add-on in Community turns orange (blue = just ticked)",
   "In the Library, the box of an add-on in Community turns sky blue, on a dark blue row (yellow = just ticked)"),
  ("in the Community column = the add-on is in Community.</li>",
   "in the Community column = the add-on is in Community.</li><li>When you select an add-on that is already in Community (to remove it), its tick disappears: the box becomes <b>empty, with a blue outline</b>. It shows what will be left after \"Remove from Community\".</li>"),
  ("<li>The banner at the top, then the six tabs: Library, Add-on map, Auto launch, SimBrief flight, Flight plan &amp; tracking, Settings.</li><li>The bottom bar: messages, relay status (⏻ button to stop or restart it), simulator status and the red <b>✕ Quit</b> button.</li>",
   "<li>The <b>menu on the left</b>: Library, Add-on map, Auto launch, SimBrief flight, Flight plan &amp; tracking, Settings (the small ↗ arrow marks a page that opens in its own window).</li><li>At the bottom of the menu: the relay status (green dot = MSFS connected, orange = waiting, grey = stopped) with the ⏻ button to stop or restart it, the simulator status and the red <b>✕ Quit</b> button.</li><li>The <b>« Collapse menu</b> button folds the menu into a thin column of icons, leaving more room for the lists; <b>»</b> unfolds it. Your choice is kept.</li><li>Top right: the language flags and the Tutorial button. At the bottom of the window: the message line.</li>"),
  ("<p><b>Reading the left list</b></p>",
   "<p><b>The numbers at the top</b>: add-ons in Community, recognised airport sceneries, real folders (add-ons copied straight into Community) and broken links (in red if there are any).</p><p><b>Reading the left list</b></p>"),
  ("The 🇫🇷 and 🇬🇧 <b>flags</b>, right of the tabs,", "The 🇫🇷 and 🇬🇧 <b>flags</b>, at the top right,"),
  ("with the flags right of the tabs (see", "with the flags at the top right (see"),
  ("<figcaption>Right of the tabs: the flags", "<figcaption>Top right: the flags"),
  ("<b>The \"🅿 Check that the aircraft is at a known airport\" box</b>", "<b>The \"Check that the aircraft is at a known airport (🅿)\" tile</b>"),
  ("hovering the 🅿 and the box.", "hovering the 🅿 and the tile."),
  ("Set the start and the options (table below), then <b>Save</b>.", "Set the start and the options: each choice is a <b>tile</b>; one click switches it on (light on and \"ON\") or off (table below). Then <b>Save</b>."),
  ("<td>Untick to keep the app in the list without launching it</td>", "<td>Switch this tile off to keep the app in the list without launching it</td>"),
  ("<li>The app shows the route and the airports found (departure, arrival and, if \"Include alternate airports\" is ticked, the alternates), with the matching sceneries of your library.</li>",
   "<li>The app shows the departure and arrival in large letters, like a ticket, then the route and the airports found (departure, arrival and, if the \"Include alternate airports\" tile is on, the alternates), with the matching sceneries of your library.</li>"),
  ("if \"Remove sceneries automatically when the simulator closes\" is ticked, and the plan", "if the \"Remove sceneries automatically when the simulator closes\" tile is on, and the plan"),
  ("<li><b>End the flight (remove sceneries)</b> removes the current flight", "<li>The <b>flight options</b> are tiles: one click switches a tile on (light and \"ON\") or off. A green banner under the buttons shows the current flight.</li><li><b>■ End the flight (remove sceneries)</b>, the orange button, removes the current flight"),
  ("<li><b>Load only the flight's sceneries</b>: when ticked,", "<li><b>Load only the flight's sceneries</b>: when the tile is on,"),
 ],
}

# 12.3 étape 4 : Réglages en cartes et tuiles
R["fr"] += [
  ("ta VA FSHub ; les dossiers et chemins se valident avec", "ta VA FSHub, rangés en <b>cartes</b> (Dossiers et chemins, Démarrage, Accessibilité, Écrans, FSHub, Raccourci, Sauvegarde, Aide et licence). Les options sont des <b>tuiles</b> : un clic l'allume (voyant et « ON ») ou l'éteint. Les dossiers et chemins se valident avec"),
  ("Les cases, les écrans, le code de ta VA et la clé FSHub s'appliquent tout de suite.", "Les tuiles, l'écran choisi, le code de ta VA et la clé FSHub s'appliquent tout de suite."),
  ("<li>La case « Toujours ouvrir Hangar FS 2024 en mode administrateur » est utile", "<li>La tuile « Toujours ouvrir en mode administrateur » est utile"),
  ("si « Démarrer avec Windows » est coché). Les deux cases sont indépendantes", "si la tuile « Démarrer avec Windows » est allumée). Les deux tuiles sont indépendantes"),
  ("ne le coche que si tu en as besoin.</li>", "ne l'allume que si tu en as besoin.</li>"),
  ("<li>Coche les fenêtres à placer : Hangar FS 2024,", "<li>Allume les tuiles des fenêtres à placer : Hangar FS 2024,"),
  ("<td>Couleurs adaptées aux daltoniens : palette lisible,", "<td>Tuile « Mode daltonien » : palette lisible,"),
]
R["en"] += [
  ("your FSHub VA; folders and paths are confirmed with", "your FSHub VA, arranged in <b>cards</b> (Folders and paths, Startup, Accessibility, Screens, FSHub, Shortcut, Backup, Help and licence). Options are <b>tiles</b>: one click switches a tile on (light and \"ON\") or off. Folders and paths are confirmed with"),
  ("Tick boxes, screens, your VA code and the FSHub key apply immediately.", "Tiles, the chosen screen, your VA code and the FSHub key apply immediately."),
  ("<li>The \"Always open Hangar FS 2024 in administrator mode\" box is useful", "<li>The \"Always open in administrator mode\" tile is useful"),
  ("if \"Start with Windows\" is ticked). Both boxes are independent", "if the \"Start with Windows\" tile is on). Both tiles are independent"),
  ("only tick it if you need it.</li>", "only switch it on if you need it.</li>"),
  ("<li>Tick the windows to place: Hangar FS 2024,", "<li>Switch on the tiles of the windows to place: Hangar FS 2024,"),
  ("<td>Colour-blind friendly colours: safe palette,", "<td>\"Colorblind mode\" tile: safe palette,"),
]

# 12.3 étape 5 : petites fenêtres
R["fr"] += [
  ("<li>Pour chaque profil, choisis ce qu'il remplace : <b>Seulement", "<li>Pour chaque profil, choisis ce qu'il remplace, en cliquant sur une des tuiles à droite de la liste : <b>Seulement"),
  ("sauf si tu coches <b>Ne pas tenir compte des add-ons ★ protégés</b>", "sauf si tu allumes la tuile <b>Ne pas tenir compte des add-ons ★ protégés</b>"),
]
R["en"] += [
  ("<li>For each profile, choose what it replaces: <b>Airport", "<li>For each profile, choose what it replaces, by clicking one of the tiles right of the list: <b>Airport"),
  ("unless you tick <b>Ignore ★ protected add-ons</b>", "unless you switch on the <b>Ignore ★ protected add-ons</b> tile"),
]

# 12.3 étape 6 : Carte addons
R["fr"] += [
  ("<li><b>Recherche</b> : tape un code OACI ou un nom puis Entrée pour zoomer dessus.</li>",
   "<li>Chaque ligne de la légende est un <b>interrupteur</b> : un clic masque ce type de scène sur la carte (la ligne s'éteint et affiche « OFF »), un autre clic le réaffiche (« ON »). Le chiffre donne le nombre de scènes.</li><li>Le bouton <b>»</b> en haut du panneau le <b>masque</b> pour agrandir la carte ; le bouton <b>« Légende et réglages</b>, en haut à droite de la carte, le fait revenir. Ton choix est gardé.</li><li><b>Recherche</b> : tape un code OACI ou un nom puis Entrée pour zoomer dessus.</li>"),
  ("<li><b>Daltoniens</b> : coche « Couleurs adaptées aux daltoniens » dans Réglages.", "<li><b>Daltoniens</b> : allume la tuile « Mode daltonien » dans Réglages."),
]
R["en"] += [
  ("<li><b>Search</b>: type an ICAO code or a name then Enter to zoom on it.</li>",
   "<li>Each legend line is a <b>switch</b>: one click hides that scenery type on the map (the line dims and shows \"OFF\"), another click shows it again (\"ON\"). The number gives how many sceneries there are.</li><li>The <b>»</b> button at the top of the panel <b>hides</b> it to enlarge the map; the <b>« Legend and settings</b> button, at the top right of the map, brings it back. Your choice is kept.</li><li><b>Search</b>: type an ICAO code or a name then Enter to zoom on it.</li>"),
  ("<li><b>Colour blindness</b>: tick \"Colour-blind friendly colours\" in Settings.", "<li><b>Colour blindness</b>: switch on the \"Colorblind mode\" tile in Settings."),
]

# 12.3 étape 7 : Plan & suivi de vol aux couleurs de l'appli
R["fr"] += [
  ("s'ouvrent dans ton navigateur habituel.</p><h3>La page principale</h3>",
   "s'ouvrent dans ton navigateur habituel.</p><p>La page reprend les couleurs de l'appli : cartes sombres, titres et bouton principal en bleu ciel, boutons arrondis.</p><h3>La page principale</h3>"),
]
R["en"] += [
  ("open in your usual browser.</p><h3>The main page</h3>",
   "open in your usual browser.</p><p>The page uses the app's colours: dark cards, sky-blue titles and main button, rounded buttons.</p><h3>The main page</h3>"),
]

# 12.3 étape 8 : volets repliables de la fenêtre de suivi
R["fr"] += [
  ("La légende en haut à droite indique aussi les couleurs : doré pour ta VA, violet pour les autres VA FSHub.</p>",
   "La légende en haut à droite indique aussi les couleurs : doré pour ta VA, violet pour les autres VA FSHub.</p><p><b>Volets repliables</b> : un clic sur le titre bleu d'un volet, marqué « ▾ réduire » (Légende, Plan SimBrief, Météo départ / arrivée, Ma VA en ligne, Piste et vent) le replie en une petite étiquette marquée « ▸ déplier » ; un clic sur l'étiquette le rouvre. Le bouton <b>Tout réduire</b>, en haut à droite, replie tous les volets d'un coup pour agrandir la carte (il devient <b>Tout déplier</b>). L'appli garde ton choix pour la prochaine fois.</p>"),
  ("les avions VATSIM sont verts, et les avions IVAO", "les avions VATSIM sont verts (vert bleuté en mode daltonien, pour ne pas les confondre avec le bleu ciel des avions IA de type non identifié), et les avions IVAO"),
]
R["en"] += [
  ("The legend at the top right also shows the colours: gold for your VA, purple for the other FSHub VAs.</p>",
   "The legend at the top right also shows the colours: gold for your VA, purple for the other FSHub VAs.</p><p><b>Folding panels</b>: one click on a panel's blue title, marked \"▾ collapse\" (Legend, SimBrief plan, Departure / arrival weather, My VA online, Runway and wind) folds it into a small label marked \"▸ expand\"; one click on the label opens it again. The <b>Collapse all</b> button, top right, folds every panel at once to enlarge the map (it then reads <b>Expand all</b>). The app remembers your choice.</p>"),
  ("VATSIM aircraft are green and IVAO aircraft", "VATSIM aircraft are green (bluish green in colorblind mode, so they are not mixed up with the sky blue of unidentified AI aircraft) and IVAO aircraft"),
]

# 12.3 : Avionics Dispatch — tuiles et carte plein écran sur deux lignes
R["fr"] += [
  ("IFR ou VFR, et l'altitude de croisière.</li>", "IFR ou VFR, et l'altitude de croisière. Chaque choix (Départ → Arrivée / Aléatoire, Départs / Arrivées, IFR / VFR) est une tuile : celle qui est allumée affiche un voyant et « ON ».</li>", "Chaque choix (Départ → Arrivée"),
  ("(Plan, Plan sombre, Satellite, Relief).</li></ul>",
   "(Plan, Plan sombre, Satellite, Relief).</li></ul><p><b>La carte plein écran (Agrandir)</b> : la barre du haut est rangée sur deux lignes. En haut : Menu principal, le résumé de la route (départ → arrivée, distance, compatibilité), <b>Inverser</b>, <b>Effacer</b>, <b>Valider</b> et la croix pour fermer. En bas : <b>Je clique pour</b> (tuiles <b>▲ Départ</b> et <b>■ Arrivée</b> : choisis ce que fera ton prochain clic ; sans choix, le 1er clic donne le départ et le 2e l'arrivée), les filtres d'<b>aéroports</b> (Gros, Moyens, Aérodromes, chacun avec ON / OFF), l'<b>avion</b>, l'<b>altitude</b> et Fond sombre. Une <b>légende</b>, en bas à droite, rappelle les couleurs et se replie d'un clic sur son titre.</p>"),
]
R["en"] += [
  ("IFR or VFR, and the cruise altitude.</li>", "IFR or VFR, and the cruise altitude. Each choice (Departure → Arrival / Random, Departures / Arrivals, IFR / VFR) is a tile: the one switched on shows a light and \"ON\".</li>", "Each choice (Departure → Arrival"),
  ("(Map, Dark map, Satellite, Terrain).</li></ul>",
   "(Map, Dark map, Satellite, Terrain).</li></ul><p><b>The full-screen map (Enlarge)</b>: the top bar is arranged on two rows. Top: Main menu, the route summary (departure → arrival, distance, compatibility), <b>Swap</b>, <b>Clear</b>, <b>Validate</b> and the cross to close. Bottom: <b>Click sets</b> (<b>▲ Departure</b> and <b>■ Arrival</b> tiles: choose what your next click does; with no choice, the 1st click sets the departure and the 2nd the arrival), the <b>airport</b> filters (Large, Medium, Airfields, each with ON / OFF), the <b>aircraft</b>, the <b>altitude</b> and Dark background. A <b>legend</b>, bottom right, recalls the colours and folds with a click on its title.</p>"),
]

# 12.3 : altitude d'interception du glide expliquée
R["fr"] += [
  ("case <b>Interception glide</b> à remplir d'après ta carte (retenue pour chaque aéroport et piste)",
   "case <b>Altitude d'interception du glide</b> : l'altitude à laquelle tu captes le glide de l'ILS, écrite sur ta carte d'approche (ex. 3000) ; tu la tapes une fois, elle est retenue pour cet aéroport et cette piste et rappelée dans la ligne courte (si SimBrief ne donne pas de fréquence ILS, seul l'axe de piste est affiché)"),
]
R["en"] += [
  ("a <b>Glideslope intercept</b> box to fill in from your chart (kept for each airport and runway)",
   "a <b>Glideslope intercept altitude</b> box: the altitude at which you capture the ILS glideslope, printed on your approach chart (e.g. 3000); type it once, it is kept for that airport and runway and shown in the short line (if SimBrief gives no ILS frequency, only the runway course is shown)"),
]


# 12.3 : mise à jour en un clic
R["fr"] += [
 ("Vérifie la version dans le titre. Quitte avec ✕ Quitter, remplace le dossier de l'appli par le nouveau, relance, puis F5 dans la fenêtre de la page</td></tr>",
  "Vérifie la version dans le titre. Si besoin, Réglages → À propos → <b>Vérifier maintenant</b> puis <b>Mettre à jour</b>. Puis F5 dans la fenêtre de la page</td></tr>"
  "<tr><td>La mise à jour automatique échoue (« dossier protégé en écriture »)</td><td>L'appli est installée dans un dossier protégé (ex. Program Files). Relance-la en administrateur et clique à nouveau sur Mettre à jour, ou télécharge la nouvelle version à la main et remplace le dossier de l'appli</td></tr>"),
 ("<tr><td>Accessibilité</td><td>Tuile « Mode daltonien »",
  "<tr><td>À propos / Mises à jour</td><td>Tuile « Vérifier les mises à jour au démarrage » (allumée par défaut) et bouton <b>Vérifier maintenant</b>. Quand une nouvelle version sort, un bandeau bleu apparaît en haut : <b>Mettre à jour</b> télécharge, vérifie, installe et relance l'appli tout seul (seulement quand Flight Simulator est fermé) ; tes réglages, profils et liens sont conservés. <b>Nouveautés</b> ouvre la page de la version, <b>Plus tard</b> masque le bandeau</td></tr>"
  "<tr><td>Accessibilité</td><td>Tuile « Mode daltonien »", "Vérifier les mises à jour au démarrage"),
]
R["en"] += [
 ("Check the version in the title. Quit with ✕ Quit, replace the app folder with the new one, restart, then F5 in the page window</td></tr>",
  "Check the version in the title. If needed, Settings → About → <b>Check now</b> then <b>Update</b>. Then F5 in the page window</td></tr>"
  "<tr><td>Automatic update fails (\"write-protected folder\")</td><td>The app is installed in a protected folder (e.g. Program Files). Restart it as administrator and click Update again, or download the new version manually and replace the app folder</td></tr>"),
 ("<tr><td>Accessibility</td><td>\"Colorblind mode\" tile",
  "<tr><td>About / Updates</td><td>\"Check for updates at startup\" tile (on by default) and <b>Check now</b> button. When a new version is out, a blue banner appears at the top: <b>Update</b> downloads, verifies, installs and restarts the app by itself (only when Flight Simulator is closed); your settings, profiles and links are kept. <b>What's new</b> opens the release page, <b>Later</b> hides the banner</td></tr>"
  "<tr><td>Accessibility</td><td>\"Colorblind mode\" tile", "Check for updates at startup"),
]


# 12.5 : aéroports sur la carte de suivi
R["fr"] += [("<tr><td>Suivre mon avion</td><td>Bouton actif (bleu) ou inactif : la carte suit ton avion (en orange)</td></tr>",
  "<tr><td>Suivre mon avion</td><td>Bouton actif (bleu) ou inactif : la carte suit ton avion (en orange)</td></tr>"
  "<tr><td>Aéroports · Noms</td><td>Bouton actif (bleu) ou inactif : affiche les aéroports avec leur code OACI en petit. Les grands aéroports d'abord, puis les moyens et les petits quand tu zoomes. Survole un aéroport pour voir son nom, sa ville et son altitude. <b>Noms</b> écrit aussi le nom sous chaque code. L'appli retient ton choix</td></tr>")]
R["en"] += [("<tr><td>Follow my aircraft</td><td>Active (blue) or inactive button: the map follows your aircraft (in orange)</td></tr>",
  "<tr><td>Follow my aircraft</td><td>Active (blue) or inactive button: the map follows your aircraft (in orange)</td></tr>"
  "<tr><td>Airports · Names</td><td>Active (blue) or inactive button: shows airports with their ICAO code in small letters. Large airports first, then medium and small ones as you zoom in. Hover an airport to see its name, city and elevation. <b>Names</b> also writes the name under each code. The app remembers your choice</td></tr>")]


# 12.6 : carte propre en fin de vol, METAR en vol libre, plan .PLN
R["fr"] += [
 ("Importer le plan</td><td>Dessine ton plan SimBrief avec SID, route et STAR</td></tr>",
  "Importer le plan</td><td>Dessine ton plan SimBrief avec SID, route et STAR</td></tr>"
  "<tr><td>.PLN</td><td>Affiche un plan de vol au format .PLN : celui que tu enregistres depuis la carte du monde de MSFS (bouton Enregistrer), celui exporté par Avionics Dispatch, ou un autre logiciel (Little Navmap…). Choisis le fichier, la route s'affiche comme un plan SimBrief</td></tr>", ".PLN</td><td>"),
 ("<tr><td>METAR · Mon plan</td><td>Météo du départ et de l'arrivée, actualisée toutes les 60 s</td></tr>",
  "<tr><td>METAR · Mon plan</td><td>Météo du départ et de l'arrivée, actualisée toutes les 60 s</td></tr>"
  "<tr><td>METAR · Vol libre</td><td>Sans plan de vol : le METAR du départ s'affiche tout seul quand ton avion est au sol sur un aéroport (ou tape son code dans DÉP). Tape un code OACI dans ARR puis Entrée pour voir le METAR de ton arrivée</td></tr>"
  "<tr><td>Fin du vol</td><td>Quand tu cliques sur Terminer le vol dans Vol SimBrief, la carte se remet à zéro : plus de plan, de trajectoire, de METAR ni de piste et vent de l'ancien vol. Une trajectoire de vol libre arrêtée depuis plus de 30 minutes n'est pas reprise au prochain lancement</td></tr>", "METAR · Vol libre"),
]
R["en"] += [
 ("Import plan</td><td>Draws your SimBrief plan with SID, route and STAR</td></tr>",
  "Import plan</td><td>Draws your SimBrief plan with SID, route and STAR</td></tr>"
  "<tr><td>.PLN</td><td>Shows a .PLN flight plan: the one you save from the MSFS world map (Save button), the one exported by Avionics Dispatch, or from other software (Little Navmap…). Pick the file and the route appears like a SimBrief plan</td></tr>", ".PLN</td><td>"),
 ("<tr><td>METAR · My plan</td><td>Departure and arrival weather, refreshed every 60 s</td></tr>",
  "<tr><td>METAR · My plan</td><td>Departure and arrival weather, refreshed every 60 s</td></tr>"
  "<tr><td>METAR · Free flight</td><td>Without a flight plan: the departure METAR shows by itself when your aircraft is on the ground at an airport (or type its code in DEP). Type an ICAO code in ARR then Enter to see your arrival METAR</td></tr>"
  "<tr><td>End of flight</td><td>When you click End the flight in SimBrief flight, the map resets: no more plan, track, METAR or runway and wind from the previous flight. A free-flight track stopped for more than 30 minutes is not restored at the next launch</td></tr>", "METAR · Free flight"),
]


# 12.6 : terrains sans code OACI masqués sur la carte Plan de vol personnel
R["fr"] += [("(Gros, Moyens, Aérodromes, chacun avec ON / OFF),", "(Gros, Moyens, Aérodromes, chacun avec ON / OFF ; seuls les terrains avec un vrai code OACI à 4 lettres sont affichés, pas les « FR-0901 » ; leur code OACI s'affiche quand tu zoomes),")]
R["en"] += [("(Large, Medium, Airfields, each with ON / OFF),", "(Large, Medium, Airfields, each with ON / OFF; only fields with a real 4-letter ICAO code are shown, not \"FR-0901\" ones; their ICAO code shows when you zoom in),")]


# 12.6 : pistes inconnues = à vérifier
R["fr"] += [("distance, temps de vol et compatibilité des pistes avec ton avion.</li>", "distance, temps de vol et compatibilité des pistes avec ton avion. Si la base ne connaît pas les pistes d'un aérodrome, il est marqué « à vérifier » (orange) au lieu d'être refusé.</li>")]
R["en"] += [("distance, flight time and runway compatibility with your aircraft.</li>", "distance, flight time and runway compatibility with your aircraft. If the database doesn't know an airfield's runways, it is marked \"to check\" (orange) instead of being refused.</li>")]


# 12.6 : barre de la fenêtre de suivi rangée en groupes
R["fr"] += [("<h3>La fenêtre de suivi (bouton « Ouvrir le suivi »)</h3>", "<h3>La fenêtre de suivi (bouton « Ouvrir le suivi »)</h3><p>La barre du haut tient sur deux lignes. En haut : Menu principal, le titre, le groupe <b>VA FSHub</b> (ta VA, toutes les VA, rayon), l'état du relais et de SimBrief, puis <b>Tout réduire / Tout déplier</b> et la croix. En bas : le groupe <b>Plan de vol</b> (SimBrief, Importer le plan, .PLN, Centrer sur le plan) et, juste sous VA FSHub, le groupe <b>Carte</b> (Trafic IA, Au sol, Suivre mon avion, Aéroports, Noms, Taxiways).</p>", "juste sous VA FSHub")]
R["en"] += [("<h3>The tracking window (\"Open tracking\" button)</h3>", "<h3>The tracking window (\"Open tracking\" button)</h3><p>The top bar uses two rows. Top: Main menu, the title, the <b>FSHub VA</b> group (your VA, all VAs, radius), the relay and SimBrief status, then <b>Collapse all / Expand all</b> and the cross. Bottom: the <b>Flight plan</b> group (SimBrief, Import plan, .PLN, Center on plan) and, right below FSHub VA, the <b>Map</b> group (AI traffic, On ground, Follow my aircraft, Airports, Names, Taxiways).</p>", "right below FSHub VA")]


# 12.7 : METAR en tableau de bord, boutons unifiés
R["fr"] += [("<tr><td>METAR · Mon plan</td><td>Météo du départ et de l'arrivée, actualisée toutes les 60 s</td></tr>",
  "<tr><td>METAR · Mon plan</td><td>Météo du départ et de l'arrivée, actualisée toutes les 60 s, en petites cases : vent (la flèche montre où il souffle), visibilité, nuages, température / rosée, QNH. La pastille de couleur donne la catégorie : <b>VFR</b> vert, <b>MVFR</b> bleu, <b>IFR</b> rouge, <b>LIFR</b> violet. « METAR brut » déplie le texte d'origine. Dans la barre, un bouton allumé a un contour bleu ciel ; sa pastille rappelle la couleur du calque sur la carte</td></tr>", "LIFR</b> violet")]
R["en"] += [("<tr><td>METAR · My plan</td><td>Departure and arrival weather, refreshed every 60 s</td></tr>",
  "<tr><td>METAR · My plan</td><td>Departure and arrival weather, refreshed every 60 s, in small boxes: wind (the arrow shows where it blows), visibility, clouds, temperature / dew point, QNH. The coloured badge gives the category: <b>VFR</b> green, <b>MVFR</b> blue, <b>IFR</b> red, <b>LIFR</b> purple. \"Raw METAR\" unfolds the original text. In the bar, a switched-on button has a sky-blue outline; its dot recalls the layer's colour on the map</td></tr>", "LIFR</b> purple")]


# 12.7 (suite) : piste et vent dessinés, carte d'embarquement
R["fr"] += [("<tr><td>METAR · Vol libre</td>", "<tr><td>Piste et vent</td><td>Un petit dessin montre la piste orientée et la flèche du vent. À côté, le vent de face (vert) ou arrière (orange ou rouge) et le vent de travers (rouge s'il dépasse ton seuil)</td></tr><tr><td>Mon vol</td><td>Façon carte d'embarquement : départ et arrivée en grand, l'avion avance sur la ligne entre les deux selon la distance parcourue</td></tr><tr><td>METAR · Vol libre</td>", "<tr><td>Mon vol</td>")]
R["en"] += [("<tr><td>METAR · Free flight</td>", "<tr><td>Runway and wind</td><td>A small drawing shows the runway oriented and the wind arrow. Next to it, the headwind (green) or tailwind (orange or red) and the crosswind (red above your limit)</td></tr><tr><td>My flight</td><td>Like a boarding pass: departure and arrival in large letters, the aircraft moves along the line between them with the distance flown</td></tr><tr><td>METAR · Free flight</td>", "<tr><td>My flight</td>")]


# 12.7 : journal de vol et menu repliable
R["fr"] += [("<h3>La fenêtre de suivi (bouton « Ouvrir le suivi »)</h3>",
  "<h3>Le journal de vol</h3><p>Ouvre-le avec <b>Journal de vol</b> dans le menu de gauche, ou le bouton <b>Journal de vol</b> de la carte de suivi. Il se remplit tout seul pendant le vol, tant que la fenêtre Plan &amp; suivi de vol est ouverte.</p><ul>"
  "<li><b>À gauche, la frise</b> : Porte, Roulage, Décollage, Montée, Croisière, Descente, Approche, Atterrissage, Roulage, Porte d'arrivée. La phase en cours est en orange, les phases faites en bleu. Chaque phase montre son heure, sa durée, le carburant consommé, la vitesse sol, le vario et l'altitude ; au décollage la vitesse d'envol, à l'atterrissage le <b>taux de toucher</b> (Kiss, Doux, Correct, Ferme, Dur), la vitesse et les volets.</li>"
  "<li><b>En haut, le résumé</b> : temps bloc, temps de vol, carburant, distance, altitude max et atterrissage, comparés au plan SimBrief.</li>"
  "<li><b>Le profil du vol</b>, du sol au sol : en pointillé le profil prévu par SimBrief avec le <b>TOC</b> (fin de montée) et le <b>TOD</b> (début de descente), en couleur ton profil réel, phase par phase.</li>"
  "<li><b>La carte</b> : seulement ta route et ta trajectoire, sans trafic ni VA.</li>"
  "<li>Chaque vol terminé est gardé : choisis-le dans la liste en haut pour le revoir, ou supprime-le. Les vols sont rangés dans le dossier des réglages de l'appli, pas dans le dossier de l'appli.</li></ul>"
  "<h3>Le menu repliable</h3><p>Sur Avionics Dispatch, la carte des scènes et le tutoriel, une colonne d'icônes à gauche s'ouvre quand tu passes la souris dessus : Bibliothèque, Carte addons, Démarrage auto, Vol SimBrief, Plan &amp; suivi de vol, Journal de vol, Réglages. Un clic ramène la fenêtre principale ou ouvre la page voulue.</p>"
  "<h3>La fenêtre de suivi (bouton « Ouvrir le suivi »)</h3>", "<h3>Le journal de vol</h3>")]
R["en"] += [("<h3>The tracking window (\"Open tracking\" button)</h3>",
  "<h3>The flight log</h3><p>Open it with <b>Flight log</b> in the left menu, or the <b>Flight log</b> button of the tracking map. It fills in by itself during the flight, as long as the Flight plan &amp; tracking window is open.</p><ul>"
  "<li><b>On the left, the timeline</b>: Gate, Taxi, Takeoff, Climb, Cruise, Descent, Approach, Landing, Taxi, Arrival gate. The current phase is orange, completed phases blue. Each phase shows its time, duration, fuel burned, ground speed, vertical speed and altitude; at takeoff the liftoff speed, at landing the <b>touchdown rate</b> (Butter, Soft, Good, Firm, Hard), speed and flaps.</li>"
  "<li><b>At the top, the summary</b>: block time, flight time, fuel, distance, max altitude and landing, compared with the SimBrief plan.</li>"
  "<li><b>The flight profile</b>, ground to ground: dashed, the profile planned by SimBrief with <b>TOC</b> (top of climb) and <b>TOD</b> (top of descent); in colour, your actual profile, phase by phase.</li>"
  "<li><b>The map</b>: only your route and track, no traffic or VA.</li>"
  "<li>Each finished flight is kept: pick it in the list at the top to review it, or delete it. Flights are stored in the app's settings folder, not in the app folder.</li></ul>"
  "<h3>The collapsible menu</h3><p>On Avionics Dispatch, the sceneries map and the tutorial, a column of icons on the left opens when you hover it: Library, Add-ons map, Auto start, SimBrief flight, Flight plan &amp; tracking, Flight log, Settings. One click brings back the main window or opens the page.</p>"
  "<h3>The tracking window (\"Open tracking\" button)</h3>", "<h3>The flight log</h3>")]


# 12.7 : encadré unique Mon vol
R["fr"] += [("<tr><td>METAR · Vol libre</td>", "<tr><td>Mon vol · plan, piste et météo</td><td>Avec un plan SimBrief, un seul encadré réunit le plan, la piste et le vent, et la météo du départ et de l'arrivée. Quand il s'ouvre, la légende se replie toute seule pour laisser la place (clique sur « Légende » pour la rouvrir)</td></tr><tr><td>METAR · Vol libre</td>", "Mon vol · plan, piste et météo")]
R["en"] += [("<tr><td>METAR · Free flight</td>", "<tr><td>My flight · plan, runway and weather</td><td>With a SimBrief plan, a single panel gathers the plan, the runway and wind, and the departure and arrival weather. When it opens, the legend folds away by itself to make room (click \"Legend\" to reopen it)</td></tr><tr><td>METAR · Free flight</td>", "My flight · plan, runway and weather")]


# 12.7 : altitude conseillée
R["fr"] += [("(Gros, Moyens, Aérodromes, chacun avec ON / OFF ;", "(à côté du choix Altitude, une pastille verte « Conseillé » propose une altitude de croisière selon la distance, l'avion et le sens du vol — niveau impair vers l'est, pair vers l'ouest, +500 ft en VFR — ; « Appliquer » la prend, survole-la pour voir le calcul) (Gros, Moyens, Aérodromes, chacun avec ON / OFF ;", "pastille verte « Conseillé »")]
R["en"] += [("(Large, Medium, Airfields, each with ON / OFF;", "(next to the Altitude choice, a green \"Advised\" pill suggests a cruise altitude from the distance, the aircraft and the direction of flight — odd levels eastbound, even westbound, +500 ft in VFR —; \"Apply\" takes it, hover it to see the calculation) (Large, Medium, Airfields, each with ON / OFF;", "green \"Advised\" pill")]

# 12.3 : VATSIM et IVAO retirés de l'appli — on enlève leur partie du tutoriel (expression régulière, idempotent)
CUT = {
 "fr": [(r"<p><b>Pilotes VATSIM et IVAO</b></p>.*?jusqu'à la position suivante\.</p>",
         "<p><b>Mouvement des avions</b></p><p>Entre deux mises à jour, les avions glissent en douceur au lieu de sauter. Les avions FSHub (ta VA et les autres VA) avancent selon leur cap et leur vitesse depuis leur dernier relevé, sans jamais reculer ; pendant un zoom, ils suivent la carte.</p>")],
 "en": [(r"<p><b>VATSIM and IVAO pilots</b></p>.*?until the next position\.</p>",
         "<p><b>Aircraft movement</b></p><p>Between two updates, aircraft glide smoothly instead of jumping. FSHub aircraft (your VA and the other VAs) move along their heading and speed since their last report, never backwards; during a zoom, they follow the map.</p>")],
}

# remplacements faits partout dans la page (texte qui revient plusieurs fois)
GLOBAL = {
 "fr": [(" de la barre du bas ;", " en bas du menu ;"), ("Bouton ⏻ dans la barre du bas de Hangar FS 2024", "Bouton ⏻ en bas du menu de Hangar FS 2024"),
        ("bouton ⏻ de la barre du bas", "bouton ⏻ en bas du menu")],
 "en": [(" button in the bottom bar;", " button at the bottom of the menu;"), ("with the ⏻ button in the bottom bar,", "with the ⏻ button at the bottom of the menu,")],
}
# 12.3 : bouton LFV Planner retiré de la page Vol SimBrief
GLOBAL.setdefault("fr", []).append((", ou <b>🌐 LFV Planner</b> pour le planificateur des Fous Volants.</li>", ".</li>"))

if __name__ == "__main__":
    web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for lang, pairs in R.items():
        p = os.path.join(web, "tutorial_%s.html" % lang)
        s = open(p, encoding="utf-8").read()
        for pr in pairs:
            a, b = pr[0], pr[1]
            if b in s or a not in s or (len(pr) > 2 and pr[2] in s):
                continue  # déjà fait
            assert s.count(a) == 1, (lang, a[:60], s.count(a))
            s = s.replace(a, b)
        for a, b in GLOBAL.get(lang, []):   # remplacements partout (idempotents)
            s = s.replace(a, b)
        import re
        for rx, b in CUT.get(lang, []):
            s = re.sub(rx, lambda m: b, s, flags=re.S)
        open(p, "w", encoding="utf-8").write(s)
        print("ok :", p)
