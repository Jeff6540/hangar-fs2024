# Hangar FS 2024 — Addon Manager

Gestionnaire d'add-ons pour **Microsoft Flight Simulator 2024**, piloté par ton plan de vol SimBrief.
*Add-on manager for Microsoft Flight Simulator 2024, driven by your SimBrief flight plan.*

## Français

- Bibliothèque d'add-ons rangée par dossiers : l'appli crée et retire de simples liens vers le dossier Community, sans jamais copier ni supprimer tes add-ons.
- Vol SimBrief : seules les scènes des aéroports de ton vol sont activées, puis retirées à la fermeture de MSFS.
- Carte des scènes, profils d'add-ons, démarrage automatique de tes applis de vol.
- Plan & suivi de vol : carte avec ton avion, le trafic IA, ta VA FSHub, le radar global FSHub, plans d'aéroport OpenStreetMap.
- Programme Windows en C# : un simple `Hangar FS 2024.exe`, rien à installer (Windows 10 ou 11), 0 alerte sur VirusTotal.
- Interface en français et en anglais, tutoriel intégré.

**Télécharger** : page [Releases](https://github.com/jeff6540/hangar-fs2024/releases) (ou la page flightsim.to de l'appli). Décompresse le zip dans un dossier fixe, puis lance `Hangar FS 2024.exe`.

## English

- Add-on library sorted in folders: the app creates and removes simple links to the Community folder, never copying or deleting your add-ons.
- SimBrief flight: only the sceneries of your flight's airports are activated, then removed when MSFS closes.
- Scenery map, add-on profiles, auto-launch of your flight apps.
- Flight plan & tracking: map with your aircraft, AI traffic, your FSHub VA, the FSHub global radar, OpenStreetMap airport layouts.
- Windows program written in C#: a single `Hangar FS 2024.exe`, nothing to install (Windows 10 or 11), 0 alerts on VirusTotal.
- French and English interface, built-in tutorial.

**Download**: [Releases](https://github.com/jeff6540/hangar-fs2024/releases) page (or the app's flightsim.to page). Unzip into a fixed folder, then run `Hangar FS 2024.exe`.

## Build / Fabrication

Since version 12, the app is written in C# (.NET Framework 4.8, WebView2): source code in the `csharp` folder, built automatically by GitHub Actions (`.github/workflows/build-csharp.yml`). The former Python version (up to 11.8) stays in the `src` folder. See [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md).

Depuis la version 12, l'appli est écrite en C# : code dans le dossier `csharp`, fabriquée automatiquement par GitHub Actions. L'ancienne version Python (jusqu'à la 11.8) reste dans le dossier `src`.

## License / Licence

MIT © 2026 Jeff40 — see [LICENSE](LICENSE).
Map data © OpenStreetMap contributors (ODbL). Airport data: OurAirports. Map tiles © Esri, OpenStreetMap contributors.
