# Hangar FS 2024 — Addon Manager

Gestionnaire d'add-ons pour **Microsoft Flight Simulator 2024**, piloté par ton plan de vol SimBrief.
*Add-on manager for Microsoft Flight Simulator 2024, driven by your SimBrief flight plan.*

## Français

- Bibliothèque d'add-ons rangée par dossiers : l'appli crée et retire de simples liens vers le dossier Community, sans jamais copier ni supprimer tes add-ons.
- Vol SimBrief : seules les scènes des aéroports de ton vol sont activées, puis retirées à la fermeture de MSFS.
- Carte des scènes, profils d'add-ons, démarrage automatique de tes applis de vol.
- Plan & suivi de vol : carte avec ton avion, le trafic IA, ta VA FSHub et le radar global FSHub, plans d'aéroport OpenStreetMap.
- Interface en français et en anglais, tutoriel intégré.

**Télécharger** : page [Releases](https://github.com/jeff6540/hangar-fs2024/releases) (ou la page flightsim.to de l'appli). Décompresse le zip dans un dossier fixe, puis lance `Hangar FS 2024.exe`.

## English

- Add-on library sorted in folders: the app creates and removes simple links to the Community folder, never copying or deleting your add-ons.
- SimBrief flight: only the sceneries of your flight's airports are activated, then removed when MSFS closes.
- Scenery map, add-on profiles, auto-launch of your flight apps.
- Flight plan & tracking: map with your aircraft, AI traffic, your FSHub VA and the FSHub global radar, OpenStreetMap airport layouts.
- French and English interface, built-in tutorial.

**Download**: [Releases](https://github.com/jeff6540/hangar-fs2024/releases) page (or the app's flightsim.to page). Unzip into a fixed folder, then run `Hangar FS 2024.exe`.

## Build / Fabrication

Windows builds are made automatically by GitHub Actions (`.github/workflows/build.yml`) from `src/Hangar_FS2024.pyw` with PyInstaller. See [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md).

## License / Licence

MIT © 2026 Jeff40 — see [LICENSE](LICENSE).
Map data © OpenStreetMap contributors (ODbL). Airport data: OurAirports. Map tiles © Esri, OpenStreetMap contributors.
