===============================================================
  HANGAR FS 2024 - Addon Manager for Microsoft Flight Simulator 2024
===============================================================

Hangar FS 2024 manages your MSFS 2024 add-ons without ever copying
them: it creates simple links between your add-on library and the
Community folder, so you can activate or remove add-ons in one click.

Features:
  - Library: activate / remove add-ons in Community, keep some
    protected (star), quarantine a faulty add-on, fix broken links.
  - ICAO duplicates: compares your add-on airports with the MSFS 2024
    default airports and lets you choose which one to keep.
  - Scenery map: a world map of your airport sceneries
    (active / inactive), with several map backgrounds.
  - Auto launch: starts your flight apps (GSX, SayIntentions,
    AutoFPS...) when MSFS starts or when your aircraft is parked,
    and closes them when you quit the simulator.
  - SimBrief flight: activates only the sceneries of your SimBrief
    flight, and removes them automatically when MSFS closes.
  - Profiles: a set of add-ons (sceneries, aircraft...) saved under a
    name and activated in one click ("Profiles..." button).
  - Flight plan & tracking: built-in flight planner, your aircraft,
    MSFS AI traffic, the pilots of your FSHub VA live, and airport
    runways, taxiways and parking spots when you zoom in
    (OpenStreetMap).
  - Colour-blind friendly mode (Settings > Accessibility).
  - Multi-screen support, Windows startup, administrator mode.

A complete illustrated tutorial is built into the app:
"? Tutorial" button at the top right.

Made by a pilot of LES FOUS VOLANTS, a French-speaking virtual
airline on FSHub. Want to fly with us?
  -> https://fshub.io/airline/LFV/overview


---------------------------------------------------------------
1. INSTALLATION
---------------------------------------------------------------

1. Unzip the archive into a folder that will not move,
   for example: Documents\Hangar FS 2024
2. Double-click "Hangar FS 2024.bat".
3. On first launch, the app offers to create a "Hangar FS 2024"
   shortcut on the Desktop: use it afterwards.
   Deleted by mistake? Settings > "Create the Desktop shortcut".

Nothing else to install: the folder contains its own official Python
("runtime" folder, program signed by the Python Software Foundation)
and the app ("app" folder). Do not move anything inside the folder.

FIRST LAUNCH - THE APP OPENS IN FRENCH:
  Click the British flag at the top right, next to the tabs, and
  answer "Yes" to restart. The app then stays in English.

If Windows shows "Windows protected your PC": click "More info", then
"Run anyway".

If Microsoft Defender or your antivirus flags the app: this is a
possible false positive with unsigned Python apps. The app
contains nothing harmful and only connects to SimBrief, FSHub, weather
services, OurAirports and OpenStreetMap (airport layouts). If Defender quarantined the file:
Windows Security > Virus & threat protection > Protection history >
the alert > Actions > Allow / Restore.
Tip: only tick "As administrator" (Settings) if you launch apps that
require it (SayIntentions, REX Atmos...).


---------------------------------------------------------------
2. FIRST SETUP (once, "Settings" tab)
---------------------------------------------------------------

1. Add-on library: choose (Browse…) the folder where you keep your
   add-ons, OUTSIDE Community.
   Example: D:\MSFS Addons  (sub-folders by category are fine:
   AIRPORTS, AIRCRAFT, VFR...).
2. Community folder: click "Detect".
3. Default sceneries (StreamedPackages): click "Detect".
4. MSFS 2024 launch: click "Detect".
5. Click "Save".

Then, WITH THE SIMULATOR CLOSED, move to your library ONLY the add-ons
you installed yourself (downloaded then unzipped into Community).
Hangar FS 2024 puts them back in Community (as links) when you
activate them. DO NOT EMPTY THE WHOLE COMMUNITY FOLDER:

  MOVE: the folders shown as "Real folder" in the app's Community
    list: airport sceneries, VFR packs, scenery packs, freeware
    aircraft and liveries, sounds, small tools (flightsim.to...).
  LEAVE IN COMMUNITY: anything an installer or manager installs and
    updates itself (it would no longer find it): PMDG (Operations
    Center), GSX (FSDT), Navigraph (navdata), Orbx Central, iniBuilds
    Manager, Aerosoft One, FlyByWire Installer...
  NEVER TOUCH: the Official and StreamedPackages folders (MSFS and
    Marketplace content).
  When in doubt, leave the folder in Community.

Optional:
  - Start with Windows: the app opens minimised when the PC starts
    (needed for auto launch to work).
  - As administrator: useful if you launch apps that require it
    (SayIntentions, weathercreator...).
  - Screens: with 2 screens, the app and its map can open on the
    2nd screen while MSFS stays on the primary one.


---------------------------------------------------------------
3. QUICK START
---------------------------------------------------------------

GOLDEN RULE: MSFS only reads Community when it starts.
Prepare your add-ons BEFORE launching the simulator. While MSFS is
running, the app locks itself (red banner) to prevent mistakes.

- Library tab: tick add-ons (or Ctrl + click rows), then
  "Activate ... in Community" or "Remove ... from Community".
  "Protect" (star) keeps an add-on active during every flight.
- Add-on map tab: the map of your airport sceneries.
- Settings > Backup: "Export my settings" saves your settings,
  profiles and auto-launch apps in a .zip file; "Restore" puts them
  back (new PC, Windows reinstall). This file is personal: do not
  share it.
- Auto launch tab: add your flight apps (Add... button), choose
  when they start, their delay and their screen.
- SimBrief flight tab: enter your SimBrief ID, click "Fetch the
  latest flight plan", then "Prepare the flight": only your flight's
  sceneries are activated, and removed when MSFS closes.
- Flight plan & tracking tab: flight planner, weather, a map with
  your aircraft and AI traffic, the "All FSHub VAs" button (FSHub
  global radar, off by default; click an FSHub aircraft to see its
  filed route and track; "Range" menu to show only nearby flights or
  those along your route), your own track in blue, your SimBrief
  plan shown automatically if fetched in the SimBrief flight tab
  (less than 12 h old), the "My FSHub VA" button (set your
  VA code, e.g. LFV, in Settings > "My FSHub VA") and the
  "Taxiways" button (airport layouts when you zoom in).


---------------------------------------------------------------
4. PARKED-AIRCRAFT DETECTION (AUTO LAUNCH)
---------------------------------------------------------------

Starting apps "when the aircraft is parked" reads MSFS through the
SimConnect.dll file. If it does not trigger while MSFS is running,
copy SimConnect.dll (provided with the MSFS 2024 SDK, folder
"SimConnect SDK\lib") next to "Hangar FS 2024.bat", then restart
the app.

The relay status is shown at the bottom of the app (on/off button).


---------------------------------------------------------------
5. SAFETY AND DATA
---------------------------------------------------------------

- Hangar FS 2024 NEVER deletes a real add-on folder:
  it only creates and removes links.
- Your settings stay on your PC, in: %APPDATA%\HangarFS2024
  (nothing is sent anywhere; only SimBrief and weather services
  are queried online).

===============================================================
  IMPORTANT - MSFS 2024 CONTENT.XML FILE (ICAO duplicates)
===============================================================

What the app does:
  The "Disable the default scenery" button (ICAO duplicates window)
  also disables the scenery in the MSFS My Library. To do so, the app
  edits the MSFS 2024 Content.xml file: it ONLY changes the line of the
  chosen scenery, from "Activated" to "UserDisabled", exactly like
  unticking it in My Library.

What it does not do:
  It deletes no file, touches no other content, sends nothing over the
  internet and does nothing while MSFS is running.

Where the file is:
  - Microsoft Store version: Windows + R, paste
      %LOCALAPPDATA%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalCache
    then open the sub-folder named after your Xbox account: "Content" file.
  - Steam version: Windows + R, paste
      %APPDATA%\Microsoft Flight Simulator 2024
  - Otherwise: in that folder, type content.xml in the Search box.

Backup (RECOMMENDED BEFORE THE FIRST USE):
  - Initial backup: on first use, a window explains everything and
    offers "Back up and continue". The copy goes to your Desktop, in the
    "fs_2024_xml_backup" folder, with the same name as the original:
    Content.xml. The "Change location..." button lets you pick another
    folder.
  - It is made only ONCE and never overwritten: as long as it exists, the
    app asks nothing again (neither to disable nor to re-enable a
    scenery).
  - Safety net: the app also keeps the last 2 automatic copies next to
    the file (Content.xml.hangar_YYYYMMDD.bak); older ones are deleted
    automatically.
  - No copy is ever put back automatically.

If anything goes wrong:
  - ICAO duplicates window > "Restore Content.xml..." button: choose a
    backup (the initial backup is offered first) and confirm. MSFS must
    be closed. The current file is first copied to the backup folder,
    so you can go back.
  - Or by hand: with MSFS and the app closed, copy
    Desktop\fs_2024_xml_backup\Content.xml in place of the "Content" file.

Uninstall: quit the app ("Quit" button), untick "Start with Windows"
if you had ticked it, then delete the app folder, the Desktop
shortcut and the %APPDATA%\HangarFS2024 folder.


---------------------------------------------------------------
6. TROUBLESHOOTING
---------------------------------------------------------------

- Library buttons are greyed out: MSFS is running, close it.
- Orange "View and fix" banner: an add-on was moved, click it.
- A scenery is not recognised: "ICAO codes..." button in the
  Library.
- Port 8765 already in use: an old relay is still running,
  click "Close the old relay".
- When reporting a problem, always give the version number shown
  in the window title, with a screenshot.


---------------------------------------------------------------
7. LEGAL
---------------------------------------------------------------

Hangar FS 2024 is free software provided "as is", without any
warranty. Use it at your own risk.
It is not affiliated with, endorsed by or sponsored by Microsoft,
Asobo Studio, SimBrief or Navigraph. Microsoft Flight Simulator is
a trademark of Microsoft Corporation.
Map data (c) OpenStreetMap contributors. Airport data: OurAirports.

---------------------------------------------------------------
8. LICENSE AND OFFICIAL DOWNLOAD
---------------------------------------------------------------

Hangar FS 2024 (c) 2026 Jeff40 - free software under the MIT license
(LICENSE file). You may use, modify and redistribute it, keeping the
author and license notice.

Source code and official releases: github.com/jeff6540/hangar-fs2024
and the Hangar FS 2024 page on flightsim.to (or the zip sent directly
by the author). A copy found on another site may have been modified.

Happy flying!
