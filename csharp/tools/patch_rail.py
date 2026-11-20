# -*- coding: utf-8 -*-
"""12.7 : menu repliable sur toutes les pages (Avionics Dispatch, carte des scènes, tutoriel).
Une colonne d'icônes à gauche qui s'ouvre au survol ; un clic ramène à la fenêtre principale ou ouvre la page voulue."""
import json, os, sys

ITEMS = [  # clé, icône (chemins SVG du menu principal), libellé FR, libellé EN ; clé "#" = titre de rubrique (12.9)
 ("#", "", "Add-ons", "Add-ons"),
 ("lib", '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 4v16"/>', "Bibliothèque", "Library"),
 ("map", '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>', "Carte addons", "Add-ons map"),
 ("launch", '<path d="M5 12h14M13 6l6 6-6 6"/>', "Démarrage auto", "Auto start"),
 ("#", "", "Préparer", "Prepare"),
 ("vol", '<path d="M2 16l20-6-20-6 4 6z"/>', "Vol SimBrief", "SimBrief flight"),
 ("plan", '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>', "Plan de vol", "Flight plan"),
 ("vfr", '<path d="M3 20l5-9 4 5 3-4 6 8z"/><circle cx="17" cy="6" r="2"/>', "Plan VFR", "VFR plan"),
 ("#", "", "Voler", "Fly"),
 ("track", '<circle cx="12" cy="12" r="9"/><path d="M12 3v4M12 17v4M3 12h4M17 12h4"/>', "Suivi de vol", "Flight tracking"),
 ("journal", '<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M9 9h6M9 13h6M5 17a3 3 0 0 1 3-3h11"/>', "Journal de vol", "Flight log"),
 ("#", "", "Radars", "Radars"),
 ("rglobal", '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/>', "Radar FSHub global", "FSHub global radar"),
 ("rva", '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M15 20c0-2.5 1.5-4.5 4-4.8"/>', "Page de ma VA", "My VA page"),
 ("rvradar", '<path d="M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/>', "Radar de ma VA", "My VA radar"),
 ("#", "", "", ""),
 ("set", '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/>', "Réglages", "Settings"),
]
CSS = r"""<style id="hangar-127-rail">
#hgRail{position:fixed;left:0;top:0;bottom:0;width:52px;z-index:2147483000;background:#0D1219;border-right:1px solid #1E2733;display:flex;flex-direction:column;gap:4px;
  padding:10px 6px;box-sizing:border-box;transition:width .18s ease,box-shadow .18s ease;overflow:hidden;font-family:"Segoe UI Variable Text","Segoe UI",Inter,sans-serif}
#hgRail:hover{width:224px;box-shadow:12px 0 32px rgba(0,0,0,.45)}
#hgRail .lg{display:flex;align-items:center;gap:10px;height:40px;margin:0 0 8px 2px;white-space:nowrap}
#hgRail .lg i{flex:none;width:36px;height:36px;border-radius:10px;background:#38BDF8;display:grid;place-items:center}
#hgRail .lg b{font:800 13px "Segoe UI",Inter,sans-serif;color:#F1F5F9;opacity:0;transition:opacity .15s}
#hgRail:hover .lg b,#hgRail:hover .it span{opacity:1}
#hgRail .it{display:flex;align-items:center;gap:12px;height:38px;padding:0 9px;border-radius:10px;border:0;background:transparent;color:#A9B6C6;cursor:pointer;white-space:nowrap;text-align:left;font:600 13px "Segoe UI",Inter,sans-serif}
#hgRail .it svg{flex:none;width:20px;height:20px;stroke:currentColor}
#hgRail .it span{opacity:0;transition:opacity .15s}
#hgRail .it:hover{background:rgba(56,189,248,.12);color:#FFFFFF}
#hgRail .sec{height:14px;margin:6px 0 0;padding:0 11px;font:700 9.5px "Segoe UI",Inter,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#4B5768;white-space:nowrap;opacity:0;transition:opacity .15s;border-top:1px solid #1E2733;padding-top:6px;box-sizing:content-box}
#hgRail:hover .sec{opacity:1;border-top-color:transparent}
#hgRail .it{height:34px!important}
#hgRail .it.on{background:rgba(56,189,248,.18);color:#7DD3FC;box-shadow:inset 3px 0 0 #38BDF8}
html body{padding-left:52px!important;box-sizing:border-box}
html body #trafficMapModal,html body #interactiveMapModal,html body #hgJournal,html body #aircraftDropdownModal{left:52px!important}
</style>"""
JS = r"""<script id="hangar-127-rail-js">
(function () {
  var ITEMS = __ITEMS__, HERE = '__HERE__', BRAND = '__BRAND__';
  function go(k) {
    if (HERE === 'dispatch' && window.hgShow) { window.hgShow(/^(plan|track|journal|perso|vfr|rglobal|rva|rvradar)$/.test(k) ? k : '') || post(k); return; }
    post(k);
  }
  function post(k) {
    try { if (window.chrome && window.chrome.webview) window.chrome.webview.postMessage({ nav: k }); } catch (e) {}
    return true;
  }
  function build() {
    if (document.getElementById('hgRail') || !document.body) return;
    var r = document.createElement('nav'); r.id = 'hgRail';
    r.innerHTML = '<div class="lg"><i><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06202C" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21V10l9-6 9 6v11"/><path d="M7 21v-6h10v6"/></svg></i><b>' + BRAND + '</b></div>' +
      ITEMS.map(function (it) { if (it[0] === '#') return '<div class="sec">' + it[2] + '</div>'; return '<button class="it' + (it[0] === HERE || (HERE === 'dispatch' && it[0] === 'plan') ? ' on' : '') + '" data-k="' + it[0] + '" title="' + it[2] + '"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + it[1] + '</svg><span>' + it[2] + '</span></button>'; }).join('');
    document.body.appendChild(r);
    r.addEventListener('click', function (e) { var b = e.target.closest('.it'); if (b) go(b.dataset.k); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
</script>"""


def patch(path, lang, here):
    s = open(path, encoding="utf-8").read()
    import re
    s = re.sub(r'<style id="hangar-127-rail">.*?</style>', '', s, flags=re.S)
    s = re.sub(r'<script id="hangar-127-rail-js">.*?</script>', '', s, flags=re.S)
    items = [[k, ic, fr if lang == "fr" else en] for k, ic, fr, en in ITEMS]
    js = JS.replace("__ITEMS__", json.dumps(items, ensure_ascii=False)).replace("__HERE__", here).replace("__BRAND__", "Hangar FS 2024")
    s = s.replace("</head>", CSS + "</head>", 1).replace("</body>", js + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for lang in ("fr", "en"):
        patch(os.path.join(web, "dispatch_%s.html" % lang), lang, "dispatch")
        patch(os.path.join(web, "map_%s.html" % lang), lang, "map")
        patch(os.path.join(web, "tutorial_%s.html" % lang), lang, "tuto")
