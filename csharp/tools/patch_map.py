# -*- coding: utf-8 -*-
"""12.3 : nouveau style de la page Carte addons (web/map_fr.html et web/map_en.html).
Volet de droite rétractable, sections en cartes, légende en interrupteurs ON/OFF, boutons pilules.
Idempotent : relancer le script ne change rien une deuxième fois."""
import os, sys

MARK = "/* ==== style 12.3 ==== */"
CSS = MARK + """
:root{--bg:#0B0F14;--panel:#10161E;--card:#121821;--field:#0F151C;--hover:#18222E;--fg:#E6EDF5;--muted:#8B98A9;--border:#1E2733;--line:#253041;--accent:#38BDF8;--accent-hi:#7DD3FC}
html,body{font:14px "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif}
#app{grid-template-columns:1fr 340px;transition:grid-template-columns .2s}
body.nopanel #app{grid-template-columns:1fr 0}
@media (max-width:760px){#app{grid-template-columns:1fr}body.nopanel #app{grid-template-columns:1fr;grid-template-rows:1fr 0}}
body.nopanel aside{padding:0;border:0;overflow:hidden}
aside{background:var(--panel);border-left:1px solid var(--border);padding:14px}
.hd{margin:-14px -14px 12px;height:96px;border-bottom:1px solid rgba(56,189,248,.45);position:relative}
#hidePanel{position:absolute;top:10px;right:10px;width:30px;height:30px;padding:0;justify-content:center;border-radius:50%;background:rgba(11,15,20,.65);border:1px solid #33414F;font-size:15px}
.hd{padding-right:48px}
.cnt:empty{display:none}
#showPanel{display:none;position:absolute;top:12px;right:12px;z-index:1000;height:36px;padding:0 15px;border-radius:999px;background:#1B2531;border:1px solid #33414F;color:var(--fg);font-weight:600;box-shadow:0 4px 14px rgba(0,0,0,.5)}
body.nopanel #showPanel{display:inline-flex;align-items:center;gap:6px}
#meta{padding:0 2px}
.sec{margin-top:12px;background:var(--card);border:1px solid var(--border);border-radius:16px;padding:12px}
.sec:first-of-type{margin-top:12px}
.sec h2{color:var(--accent-hi);font-weight:700;margin:0 0 8px}
.sec.plain{background:none;border:0;padding:0 2px}
input[type=search]{background:var(--field);border:1px solid var(--line);border-radius:999px;padding:9px 14px}
input[type=search]:focus{outline:2px solid var(--accent)}
label.row{position:relative;padding:7px 10px;margin:5px 0;border-radius:12px;border:1px solid var(--border);background:#0F151C;transition:opacity .15s}
label.row:hover{border-color:#33404F}
label.row input[type=checkbox]{position:absolute;opacity:0;width:1px;height:1px;pointer-events:none}
label.row::after{content:"OFF";flex:none;margin-left:8px;font-size:10px;font-weight:700;letter-spacing:.06em;color:#5B6778;min-width:22px;text-align:right}
label.row:has(input:checked){border-color:rgba(56,189,248,.45);background:linear-gradient(rgba(56,189,248,.10),rgba(56,189,248,.03))}
label.row:has(input:checked)::after{content:"ON";color:var(--accent)}
label.row:not(:has(input:checked)){opacity:.55}
label.row:not(:has(input:checked)) .sw{filter:grayscale(1)}
label.row:has(input:focus-visible){outline:2px solid var(--accent);outline-offset:1px}
.cnt{background:#1E2733;border-radius:999px;padding:1px 8px;min-width:14px;text-align:center}
label.rng input{accent-color:var(--accent)}
.btns{display:flex;flex-wrap:wrap;gap:8px}
button{display:inline-flex;align-items:center;gap:7px;height:36px;background:#1B2531;border:1px solid #33414F;border-radius:999px;padding:0 13px;font-weight:600;color:var(--fg)}
button:hover{background:#243142;border-color:#475569}
button .bi{width:24px;height:24px;margin-left:-9px;border-radius:50%;background:#2A3646;display:grid;place-items:center;font-size:13px}
#closeMap{justify-content:center;color:#FCA5A5;border-color:rgba(229,72,77,.6);background:rgba(229,72,77,.08)}
#closeMap .bi{background:rgba(229,72,77,.25)}
#closeMap:hover{background:#E5484D;color:#fff;border-color:#E5484D}
.leaflet-popup-content-wrapper{border-radius:14px;border:1px solid var(--line)}
.leaflet-control-layers,.leaflet-bar{border-radius:12px!important;overflow:hidden;border:1px solid var(--line)!important}
#nopos{background:var(--field);border-radius:10px;padding:6px 8px 6px 22px}
"""

T = {
 "fr": {"hide": "»", "show": "« Légende et réglages", "hideT": "Masquer le volet pour agrandir la carte"},
 "en": {"hide": "»", "show": "« Legend and settings", "hideT": "Hide the panel to enlarge the map"},
}

def patch(s, lang):
    if MARK in s:
        return s
    t = T[lang]
    s = s.replace("</style>", CSS + "</style>", 1)
    # bouton masquer dans l'en-tête du volet, bouton afficher sur la carte
    a = '<div class="hd">'
    assert s.count(a) == 1
    s = s.replace(a, a + '<button id="hidePanel" title="%s">%s</button>' % (t["hideT"], t["hide"]), 1)
    a = '<div id="map"></div>'
    assert s.count(a) == 1
    s = s.replace(a, '<div id="map"></div><button id="showPanel">%s</button>' % t["show"], 1)
    s = s.replace('<div id="map"></div>', '<div id="map" style="position:relative"></div>', 1)
    # boutons pilules
    import re
    m = re.search(r'<button id="refresh">⟳ ([^<]*)</button> <button id="fit">([^<]*)</button>', s)
    assert m, "refresh/fit"
    s = s.replace(m.group(0), '<div class="btns"><button id="refresh"><span class="bi">⟳</span>%s</button><button id="fit"><span class="bi">⤢</span>%s</button></div>' % (m.group(1), m.group(2)))
    m = re.search(r'<button id="closeMap" style="margin-top:8px;width:100%">✕ ([^<]*)</button>', s)
    assert m, "closeMap"
    s = s.replace(m.group(0), '<button id="closeMap" style="margin-top:10px;width:100%%"><span class="bi">✕</span>%s</button>' % m.group(1))
    # le pied de page (crédits) sans cadre
    s = s.replace('<div class="sec muted">', '<div class="sec plain muted">', 1)
    # JS : volet rétractable mémorisé
    js = """
function setPanel(hide){ document.body.classList.toggle("nopanel", hide); try { localStorage.setItem("volet", hide ? "1" : "0"); } catch (e) {} setTimeout(() => map.invalidateSize(), 230); }
$("hidePanel").addEventListener("click", () => setPanel(true));
$("showPanel").addEventListener("click", () => setPanel(false));
try { if (localStorage.getItem("volet") === "1") setPanel(true); } catch (e) {}
"""
    a = '$("refresh").addEventListener("click", load);'
    assert s.count(a) == 1
    s = s.replace(a, js.strip() + "\n" + a, 1)
    # trajet SimBrief : bleu ciel
    s = s.replace('#3b82f6', '#38BDF8')
    return s

if __name__ == "__main__":
    web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for lang in ("fr", "en"):
        p = os.path.join(web, "map_%s.html" % lang)
        s = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(patch(s, lang))
        print("ok :", p)
