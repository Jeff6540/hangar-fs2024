# Ajoute à la page Plan & suivi de vol (web/dispatch_fr.html et dispatch_en.html) :
#  - VATSIM et IVAO (cases à cocher, même cercle de distance que le radar global FSHub)
#  - mouvement fluide des avions et trafic IA relu chaque seconde
# À relancer si les pages sont régénérées depuis la 11.8 :  python patch_dispatch.py <dossier web>
import sys, os

TXT = {
    "fr": {"on": "Afficher les pilotes connectés à %s (données publiques %s, relues toutes les 15 s)",
           "off": "%s indisponible : %s", "hide": "Pilotes connectés à %s — clic pour masquer",
           "ground": "au sol", "air": "en vol", "hdg": "cap", "src": "données %s", "relay": "relais arrêté",
           "leg_v": "Pilotes VATSIM", "leg_i": "Pilotes IVAO"},
    "en": {"on": "Show pilots connected to %s (public %s data, refreshed every 15 s)",
           "off": "%s unavailable: %s", "hide": "Pilots connected to %s — click to hide",
           "ground": "on ground", "air": "airborne", "hdg": "hdg", "src": "%s data", "relay": "relay stopped",
           "leg_v": "VATSIM pilots", "leg_i": "IVAO pilots"},
}

NET_JS = r"""<script>
/* Hangar FS 2024 : pilotes VATSIM et IVAO, mouvement fluide */
(function () {
  var T = __TXT__;
  var RELAY = 'http://localhost:8765/net?src=';
  /* 12.3 : VATSIM et IVAO retirés de l'appli (le module garde seulement le mouvement fluide des avions) */
  var SRC = {};
  /* IVAO : avion sombre bordé de rouge, pour ne pas le confondre avec les gros porteurs (rouges) du trafic IA */
  var DARK = '#1f2937';
  var st = {};
  Object.keys(SRC).forEach(function (k) {
    var on = false; try { on = localStorage.getItem('al_net_' + k) === '1'; } catch (e) {}
    st[k] = { on: on, data: null, err: '', mk: {}, layer: null, btn: null, t: 0 };
  });
  window.alNetOn = function () { return false; };
  function K() { return window.alNetKit; }
  function color(k) { return window.alColorblind ? SRC[k].cb : SRC[k].color; }

  /* position estimée entre deux mises à jour (cap + vitesse), au plus 60 s */
  function pos(p, t0) {
    if (p.ground || !p.gs) return [p.lat, p.lon];
    var dt = Math.min(60, Math.max(0, (Date.now() - t0) / 1000)), d = p.gs * dt / 3600 / 60, h = p.hdg * Math.PI / 180;
    return [p.lat + d * Math.cos(h), p.lon + d * Math.sin(h) / Math.max(0.05, Math.cos(p.lat * Math.PI / 180))];
  }
  function isMe(p, ll) {   /* ton propre avion, s'il est connecté au réseau : pas en double */
    var u = window.alMyPos; if (!u || u.lat == null) return false;
    return K().nmDist(u.lat, u.lon, ll[0], ll[1]) < 1.5;
  }
  function icon(k, p) {
    var k2 = K(), size = k2.catSize(p.aircraft), m = k2.map();
    var svg = p.ground ? k2.planeSvg(size, p.hdg, '#8a93a3', color(k), 1.4, p.aircraft)
      : SRC[k].dark ? k2.planeSvg(size, p.hdg, DARK, color(k), 2, p.aircraft)
      : k2.planeSvg(size, p.hdg, color(k), '#fff', 1.1, p.aircraft);
    return L.divIcon({ className: 'alfs-icon', html: svg, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
  }
  function tip(k, p) {
    var e = K().esc, l1 = [e(p.callsign)], l2 = [];
    if (p.aircraft) l1.push(e(p.aircraft));
    if (p.dep || p.arr) l1.push(e((p.dep || '?') + ' → ' + (p.arr || '?')));
    l1.push(p.ground ? T.ground : T.air);
    if (!p.ground) l2.push(p.alt.toLocaleString() + ' ft');
    if (p.gs) l2.push(p.gs + ' kt');
    if (!p.ground) l2.push(T.hdg + ' ' + String(p.hdg).padStart(3, '0') + '°');
    return '<b style="color:' + color(k) + '">' + SRC[k].label + '</b> · ' + l1.join(' · ') + (l2.length ? '<br>' + l2.join(' · ') : '') +
      '<br><span style="opacity:.6">' + T.src.replace('%s', SRC[k].label) + '</span>';
  }
  function setBtn(k, n) {
    var s = st[k], b = s.btn; if (!b) return;
    b.textContent = SRC[k].label + (s.on && s.data ? ' · ' + n : '');
    b.style.setProperty('--c', color(k));
    b.classList.toggle('on', s.on);
    b.title = !s.on ? T.on.replace(/%s/g, SRC[k].label) : (s.err ? T.off.replace('%s', SRC[k].label).replace('%s', s.err) : T.hide.replace('%s', SRC[k].label));
  }
  function render(k) {
    var s = st[k], k2 = K(), m = k2 && k2.map(); if (!m) return;
    if (!s.layer) s.layer = L.layerGroup().addTo(m);
    if (!s.on || !s.data) { s.layer.clearLayers(); s.mk = {}; setBtn(k, 0); return; }
    var keep = k2.radFilter(), ground = k2.showGround(), seen = {}, n = 0, zoomSig = '';
    (s.data.pilots || []).forEach(function (p) {
      if (p.ground && !ground) return;
      var ll = pos(p, s.t);
      if (keep && !keep(ll[0], ll[1])) return;
      if (isMe(p, ll)) return;
      seen[p.id] = 1; n++;
      var mk = s.mk[p.id], sig = p.hdg + '|' + p.ground + '|' + zoomSig + '|' + window.alColorblind;
      if (!mk) {
        mk = L.marker(ll, { icon: icon(k, p), keyboard: false, zIndexOffset: 400 }).addTo(s.layer);
        mk.bindTooltip(tip(k, p), { direction: 'top', offset: [0, -10] }); window.alClickTip(mk);
        mk._sig = sig; s.mk[p.id] = mk;
      } else {
        mk.setLatLng(ll);
        if (mk._sig !== sig) { mk.setIcon(icon(k, p)); mk._sig = sig; }
        mk.setTooltipContent(tip(k, p));
      }
    });
    Object.keys(s.mk).forEach(function (id) { if (!seen[id]) { s.layer.removeLayer(s.mk[id]); delete s.mk[id]; } });
    setBtn(k, n);
  }
  function renderAll() { Object.keys(SRC).forEach(render); try { if (K()) K().radDraw(); } catch (e) {} }
  window.alNetRender = renderAll;
  function poll(k) {
    var s = st[k]; if (!s.on) return;
    fetch(RELAY + k, { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.enabled) {
        if (!s.data || d.updated !== s.data.updated) { s.data = d; s.t = Date.now(); }
        s.err = '';
      } else { s.err = (d && d.error) || '?'; }
      render(k);
    }).catch(function () { s.err = T.relay; render(k); });
  }

  /* boutons à côté de « Toutes les VA FSHub », le menu du rayon après eux */
  function build() {
    var all = document.getElementById('alFshubAllBtn'); if (!all || !K()) return false;
    var after = all;
    Object.keys(SRC).forEach(function (k) {
      if (st[k].btn) { after = st[k].btn; return; }
      var b = document.createElement('button'); b.type = 'button'; b.id = 'alNet_' + k;
      b.className = all.className.replace(/\boff\b/, '') + ' alnet-btn';
      after.parentNode.insertBefore(b, after.nextSibling); after = b; st[k].btn = b;
      b.addEventListener('click', function () {
        st[k].on = !st[k].on; try { localStorage.setItem('al_net_' + k, st[k].on ? '1' : '0'); } catch (e) {}
        if (st[k].on) poll(k);
        renderAll(); if (K().renderAll) K().renderAll();
      });
      setBtn(k, 0);
    });
    var rad = document.getElementById('alFshubRad'); if (rad) after.parentNode.insertBefore(rad, after.nextSibling);
    var lg = document.getElementById('alVaLegend');
    if (lg && !document.getElementById('alNetLeg')) {
      var d = document.createElement('div'); d.id = 'alNetLeg';
      d.innerHTML = Object.keys(SRC).map(function (k) {
        return '<div class="alsh"><svg viewBox="0 0 24 24" width="14" height="14" style="display:inline-block;flex:none;width:14px;height:14px"><g fill="' + (SRC[k].dark ? DARK : color(k)) +
          '" stroke="' + (SRC[k].dark ? color(k) : '#fff') + '" stroke-width="' + (SRC[k].dark ? 2 : 1.3) + '">' + '<path d="M12 2l1.6 6.5L21 13v1.8l-7.4-2.3-.5 5.6 2.4 1.8V21L12 20l-3.5 1v-1.1l2.4-1.8-.5-5.6L3 14.8V13l7.4-4.5z"/>' +
          '</g></svg> ' + SRC[k].leg + '</div>';
      }).join('');
      lg.insertBefore(d, lg.children[2] || null);
    }
    var gnd = document.getElementById('trafficShowGround');
    if (gnd && !gnd._alnet) { gnd._alnet = true; gnd.addEventListener('change', renderAll); }
    return true;
  }

  /* mouvement fluide : chaque avion glisse vers sa nouvelle position (coupé pendant les zooms) */
  var css = document.createElement('style');
  css.textContent = '#leafletTrafficMap .leaflet-marker-icon.al-smooth{transition:transform 1s linear,left 1s linear,top 1s linear}' +
    '#leafletTrafficMap.al-nosmooth .leaflet-marker-icon{transition:none!important}' +
    '#leafletTrafficMap.leaflet-zoom-anim .leaflet-marker-icon.leaflet-zoom-animated{transition:transform .25s cubic-bezier(0,0,.25,1)!important}' +
    'html body #trafficMapModal button.alnet-btn,html body button.alnet-btn{border-radius:999px!important;padding-left:12px!important;padding-right:12px!important;margin-left:6px;background:rgba(15,20,30,.66)!important;' +
    'color:var(--c)!important;border:1px solid var(--c)!important}' +
    'html body #trafficMapModal button.alnet-btn.on,html body button.alnet-btn.on{background:var(--c)!important;color:#fff!important;box-shadow:inset 0 0 0 1px #fff!important;border:0!important}';
  document.head.appendChild(css);
  var hooked = false;
  function smooth() {
    var el = document.getElementById('leafletTrafficMap'), m = K() && K().map();
    if (!el || !m) return;
    if (!hooked) {
      hooked = true; var t = null;
      var off = function () { el.classList.add('al-nosmooth'); clearTimeout(t); };
      var on = function () { clearTimeout(t); t = setTimeout(function () { el.classList.remove('al-nosmooth'); }, 150); };
      m.on('zoomstart', off); m.on('zoomend', on); m.on('viewreset', off); m.on('resize', function () { off(); on(); });
    }
    el.querySelectorAll('.leaflet-marker-icon:not(.al-smooth)').forEach(function (e) {
      if (!e._alT) { e._alT = Date.now(); return; }       /* un avion qui vient d'apparaître ne glisse pas depuis le coin */
      if (Date.now() - e._alT > 900) e.classList.add('al-smooth');
    });
  }

  function start() {
    var t = setInterval(function () { if (build()) { clearInterval(t); Object.keys(SRC).forEach(poll); renderAll(); } }, 500);
    setInterval(function () { Object.keys(SRC).forEach(function (k) { if (st[k].on) render(k); }); }, 1000);
    setInterval(function () { Object.keys(SRC).forEach(poll); }, 5000);
    setInterval(smooth, 500);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
</script>"""


def patch(path, lang):
    s = open(path, encoding="utf-8").read()
    if "alNetKit" in s:
        print("déjà fait :", path); return
    def rep(a, b):
        nonlocal s
        assert s.count(a) == 1, (path, a[:80], s.count(a))
        s = s.replace(a, b)
    # trafic IA relu chaque seconde (au lieu de 2 s)
    rep("await new Promise(res => setTimeout(res, trafficFails ? 5000 : 2000));", "await new Promise(res => setTimeout(res, trafficFails ? 5000 : 1000));")
    # outils du radar FSHub mis à disposition (cercle, icônes, filtre)
    rep("  function allIcon(p) {", "  window.alNetKit = { radFilter: function () { return radFilter(); }, radDraw: function () { radDraw(); }, renderAll: function () { renderAll(); },\n"
        "    planeSvg: planeSvg, catSize: catSize, showGround: showGround, esc: esc, map: map, nmDist: nmDist };\n  function allIcon(p) {")
    rep("var n = parseInt(rad, 10), c = allOn && n ? myCenter() : null;", "var n = parseInt(rad, 10), c = (allOn || (window.alNetOn && window.alNetOn())) && n ? myCenter() : null;")
    rep("if (radSel) radSel.style.display = allOn ? '' : 'none';", "if (radSel) radSel.style.display = (allOn || (window.alNetOn && window.alNetOn())) ? '' : 'none';")
    rep("try { localStorage.setItem(KEY_RAD, rad); } catch (e) {} renderAll(); });", "try { localStorage.setItem(KEY_RAD, rad); } catch (e) {} renderAll(); if (window.alNetRender) window.alNetRender(); });")
    import json
    js = NET_JS.replace("__TXT__", json.dumps(TXT[lang], ensure_ascii=False))
    rep("<!--HANGAR_CB-->", js + "<!--HANGAR_CB-->")
    open(path, "w", encoding="utf-8").write(s)
    print("ok :", path)

if __name__ == "__main__":
    web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for lang in ("fr", "en"):
        patch(os.path.join(web, "dispatch_%s.html" % lang), lang)


# ---- Infobulles au clic (au lieu du survol) : trafic IA, autres VA FSHub, VATSIM et IVAO ----
CLICK_JS = r"""<script>
/* Hangar FS 2024 : l'infobulle d'un avion s'ouvre d'un clic (et se ferme d'un clic ailleurs) */
window.alClickTip = function (mk) {
  mk.off('mouseover', mk._openTooltip, mk); mk.off('mouseout', mk.closeTooltip, mk); mk.off('click', mk._openTooltip, mk);
  mk.on('click', function () {
    var cur = window.alTipOpen, m = mk._map;
    if (cur && cur !== mk) { try { cur.closeTooltip(); } catch (e) {} }
    if (cur === mk && mk.isTooltipOpen()) { mk.closeTooltip(); window.alTipOpen = null; }
    else { mk.openTooltip(); window.alTipOpen = mk; }
    if (m && !m._alTipHook) {
      m._alTipHook = true;
      m.on('click', function () { if (window.alTipOpen) { try { window.alTipOpen.closeTooltip(); } catch (e) {} window.alTipOpen = null; } });
    }
  });
};
</script>"""


def patch_click(path):
    s = open(path, encoding="utf-8").read()
    if "window.alClickTip = function" in s:
        print("déjà fait (clic) :", path); return
    def rep(a, b):
        nonlocal s
        assert s.count(a) == 1, (path, a[:80], s.count(a))
        s = s.replace(a, b)
    rep("<head>", "<head>\n" + CLICK_JS)
    rep("m.bindTooltip(trafficTooltip(a, isUser), { direction: 'top', offset: [0, -14] });",
        "m.bindTooltip(trafficTooltip(a, isUser), { direction: 'top', offset: [0, -14] }); if (!isUser) window.alClickTip(m);")
    rep("mk.bindTooltip(allTip(p), { direction: 'top', offset: [0, -10] });",
        "mk.bindTooltip(allTip(p), { direction: 'top', offset: [0, -10] }); window.alClickTip(mk);")
    open(path, "w", encoding="utf-8").write(s)
    print("ok (clic) :", path)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_click(os.path.join(_web, "dispatch_%s.html" % _l))


# ---- 12.3 : palette bleu ciel de l'appli et boutons pilules (page Plan & suivi de vol) ----
THEME_123 = r"""<style id="hangar-123">
/* ===== Hangar FS 2024 12.3 : mêmes couleurs que l'appli (bleu ciel), boutons en pilule ===== */
:root{
  --al-bg:#0B0F14; --al-card:#121821; --al-card2:#151D27; --al-field:#0F151C;
  --al-line:#1E2733; --al-line2:#2A3646; --al-text:#E6EDF5; --al-muted:#8B98A9; --al-dim:#64748B;
  --al-blue:#38BDF8; --al-blue-hi:#7DD3FC; --al-sky:#7DD3FC; --al-ink:#06202C;
  --r-card:16px; --r-ctl:10px;
}
html body{background:radial-gradient(1200px 520px at 50% -160px,#0f2233 0%,transparent 70%),#0B0F14!important}
html body header.avionics-panel{border-bottom:1px solid rgba(56,189,248,.45)!important}
html body header.avionics-panel a:hover{background:rgba(56,189,248,.22)!important;border-color:rgba(125,211,252,.6)!important}
html body .avionics-panel:not(header){background:var(--al-card)!important;box-shadow:0 10px 28px rgba(0,0,0,.30)!important}
.avionics-panel h3{font-size:12px!important;text-transform:uppercase;letter-spacing:.08em!important;color:var(--al-blue-hi)!important}
.avionics-panel h3 i{color:var(--al-blue)!important}
/* bouton principal : bleu ciel, texte foncé (comme dans l'appli) */
html body .bg-cockpit-cyan,html body #mapToolbar button.bg-cockpit-cyan,html body #trafficMapModal>.avionics-panel button.bg-cockpit-cyan{
  background:var(--al-blue)!important;color:var(--al-ink)!important;box-shadow:0 4px 16px rgba(56,189,248,.28)!important;border-color:transparent!important;font-weight:700!important}
html body .bg-cockpit-cyan *,html body #mapToolbar button.bg-cockpit-cyan *,html body #trafficMapModal>.avionics-panel button.bg-cockpit-cyan *{color:var(--al-ink)!important}
html body .hover\:bg-cockpit-cyan:hover,html body button.bg-cockpit-cyan:hover{background:var(--al-blue-hi)!important;color:var(--al-ink)!important}
html body .hover\:bg-cockpit-cyan:hover *{color:var(--al-ink)!important}
.bg-cockpit-cyan\/20,.bg-cockpit-cyan\/15,.bg-cockpit-cyan\/10{background-color:rgba(56,189,248,.14)!important}
.border-cockpit-cyan,.border-cockpit-cyan\/50,.border-cockpit-cyan\/40,.border-cockpit-cyan\/30{border-color:rgba(56,189,248,.5)!important}
/* boutons secondaires : gris clair lisible, en pilule */
html body button.bg-cockpit-900,html body button.bg-cockpit-800,html body a.bg-cockpit-900{background:#1B2531!important;border:1px solid #33414F!important;color:var(--al-text)!important}
html body button.bg-cockpit-900:hover,html body button.bg-cockpit-800:hover{background:#243142!important;border-color:#475569!important}
html body button{border-radius:999px!important}
/* champs arrondis */
html body input:not([type=checkbox]):not([type=radio]):not([type=range]),html body select{border-radius:12px!important}
html body textarea{border-radius:12px!important}
html body input:focus,html body select:focus,html body textarea:focus{border-color:var(--al-blue)!important;box-shadow:0 0 0 3px rgba(56,189,248,.22)!important}
:focus-visible{outline:2px solid var(--al-blue)!important}
html body input[type=checkbox],html body input[type=radio],html body input[type=range]{accent-color:var(--al-blue)}
/* encarts, METAR */
html body .raw,html body .taf{color:#D6ECFA!important;border-radius:12px!important}
#mapMiniContainer{border-radius:16px!important}
/* cartes plein écran : liseré bleu ciel */
html body #mapToolbar,html body #trafficMapModal>.avionics-panel{border-bottom:1px solid rgba(56,189,248,.45)!important}
html body #mapToolbar button:hover,html body #trafficMapModal>.avionics-panel button:hover{background:rgba(56,189,248,.25)!important;border-color:rgba(125,211,252,.6)!important}
html body #alFlightCard .alf-open,html body .alf-open{background:#38BDF8!important;color:#06202C!important;border-radius:999px!important;box-shadow:0 4px 16px rgba(56,189,248,.28)!important}
html body #alFlightCard .alf-open *{color:#06202C!important}
html body #alFlightCard .alf-open:hover,html body .alf-open:hover{background:#7DD3FC!important}
::-webkit-scrollbar-thumb{background:#2A3646!important;border-radius:999px}
</style>"""


def patch_theme123(path):
    s = open(path, encoding="utf-8").read()
    if 'id="hangar-123"' in s:
        print("déjà fait (12.3) :", path); return
    a = '<style id="addons-links-theme">'
    i = s.index(a); j = s.index("</style>", i) + len("</style>")
    s = s[:j] + THEME_123 + s[j:]
    open(path, "w", encoding="utf-8").write(s)
    print("ok (12.3) :", path)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_theme123(os.path.join(_web, "dispatch_%s.html" % _l))


# ---- 12.3 étape 8 : fenêtre de suivi — volets repliables, « Tout réduire », VATSIM vert pour les daltoniens ----
TRK_TXT = {
    "fr": {"leg": "Légende", "plan": "Plan SimBrief", "met": "Météo départ / arrivée", "va": "Ma VA en ligne", "perf": "Piste et vent",
           "red": "réduire", "unf": "déplier", "all": "TOUT RÉDUIRE", "open": "TOUT DÉPLIER", "tip": "Réduire ou déplier tous les volets pour agrandir la carte (un clic sur un volet le replie ou le rouvre)"},
    "en": {"leg": "Legend", "plan": "SimBrief plan", "met": "Departure / arrival weather", "va": "My VA online", "perf": "Runway and wind",
           "red": "collapse", "unf": "expand", "all": "COLLAPSE ALL", "open": "EXPAND ALL", "tip": "Collapse or expand all panels to enlarge the map (one click on a panel's title folds or opens it)"},
}

TRK_CSS = r"""<style id="hangar-123-trk">
/* volets repliables de la fenêtre de suivi */
html body #alMainLegend{pointer-events:auto!important}
.al-fold{position:relative}
.al-fold::before{content:attr(data-al-t) "   ▾ " attr(data-al-r);display:block;position:sticky;top:-10px;margin:-2px -2px 6px;padding:2px 2px 6px;border-bottom:1px solid rgba(56,189,248,.25);
  font:700 10px "Segoe UI",Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#7DD3FC;cursor:pointer;background:inherit;z-index:2}
.al-fold.al-col{width:auto!important;min-width:0!important;max-width:none!important;max-height:none!important;height:auto!important;overflow:hidden!important;padding:7px 14px!important;
  border-radius:999px!important;cursor:pointer;border-color:rgba(56,189,248,.55)!important}
.al-fold.al-col>*{display:none!important}
.al-fold.al-col{font-size:0!important;line-height:0!important}
.al-fold.al-col::before{line-height:1.4}
.al-fold.al-col::before{content:attr(data-al-t) "   ▸ " attr(data-al-o);margin:0;padding:0;border:0;position:static}
.al-fold.al-col:hover{background:rgba(56,189,248,.18)!important}
html body #trafficMapModal>.avionics-panel button#alFoldAll{color:#E6EDF5!important}
html body #trafficMapModal>.avionics-panel button#alFoldAll[aria-pressed="true"]{background:#38BDF8!important;color:#06202C!important;border-color:transparent!important}
html body #trafficMapModal>.avionics-panel button#alFoldAll[aria-pressed="true"] *{color:#06202C!important}
</style>"""

TRK_JS = r"""<script>
/* Hangar FS 2024 12.3 : volets repliables (clic sur le titre) et bouton Tout réduire */
(function () {
  var T = __TXT__;
  var P = [['alMainLegend', T.leg], ['sbInfo', T.plan], ['trafficMetarBox', T.met], ['alFshubLegend', T.va], ['alPerfSolo', T.perf]];
  function key(id) { return 'al_fold_' + id; }
  function set(el, col) {
    el.classList.toggle('al-col', col);
    try { localStorage.setItem(key(el.id), col ? '1' : '0'); } catch (e) {}
    sync(); setTimeout(function () { try { window.dispatchEvent(new Event('resize')); } catch (e) {} }, 30);
  }
  function els() { return P.map(function (p) { return document.getElementById(p[0]); }).filter(Boolean); }
  function sync() {
    var b = document.getElementById('alFoldAll'); if (!b) return;
    var all = els().filter(function (e) { return e.style.display !== 'none' && !e.classList.contains('hidden'); });
    var col = all.length && all.every(function (e) { return e.classList.contains('al-col'); });
    b.setAttribute('aria-pressed', col ? 'true' : 'false');
    b.querySelector('span').textContent = col ? T.open : T.all;
  }
  function hook() {
    P.forEach(function (p) {
      var el = document.getElementById(p[0]); if (!el || el._alFold) return;
      el._alFold = true; el.classList.add('al-fold'); el.setAttribute('data-al-t', p[1]); el.setAttribute('data-al-r', T.red); el.setAttribute('data-al-o', T.unf);
      var saved = null; try { saved = localStorage.getItem(key(p[0])); } catch (e) {}
      if (saved === '1') el.classList.add('al-col');
      el.addEventListener('click', function (e) {
        if (el.classList.contains('al-col')) { e.stopPropagation(); e.preventDefault(); set(el, false); return; }
        if (e.target === el && e.clientY - el.getBoundingClientRect().top < 26) { e.stopPropagation(); e.preventDefault(); set(el, true); }
      }, true);
    });
    sync();
  }
  window.alFoldAll = function () {
    var list = els(), col = !list.every(function (e) { return e.classList.contains('al-col'); });
    list.forEach(function (e) { set(e, col); });
  };
  function start() { hook(); setInterval(hook, 1500); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
</script>"""


def patch_tracking123(path, lang):
    s = open(path, encoding="utf-8").read()
    if 'id="hangar-123-trk"' in s:
        print("déjà fait (suivi 12.3) :", path); return
    def rep(a, b):
        nonlocal s
        assert s.count(a) == 1, (path, a[:80], s.count(a))
        s = s.replace(a, b)
    import json
    t = TRK_TXT[lang]
    rep('<div class="absolute top-3 right-3 z-[1000] bg-cockpit-950/90', '<div id="alMainLegend" class="absolute top-3 right-3 z-[1000] bg-cockpit-950/90')
    rep('<button onclick="closeTrafficMapModal()" class="ml-auto w-6 h-6',
        '<button id="alFoldAll" onclick="alFoldAll()" aria-pressed="false" title="%s" class="ml-auto px-2.5 py-1 bg-cockpit-800 text-slate-200 text-[10px] font-bold rounded border border-cockpit-border cursor-pointer whitespace-nowrap">'
        '<i class="fa-solid fa-compress"></i> <span>%s</span></button>\n            <button onclick="closeTrafficMapModal()" class="w-6 h-6' % (t["tip"], t["all"]))
    # daltoniens : VATSIM en vert bleuté (le bleu ciel est déjà le « type non identifié » du trafic IA)
    s = s.replace("vatsim: { label: 'VATSIM', color: '#22c55e', cb: '#56B4E9',", "vatsim: { label: 'VATSIM', color: '#22c55e', cb: '#009E73',")
    rep("<!--HANGAR_CB-->", TRK_CSS + TRK_JS.replace("__TXT__", json.dumps(t, ensure_ascii=False)) + "<!--HANGAR_CB-->")
    open(path, "w", encoding="utf-8").write(s)
    print("ok (suivi 12.3) :", path)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_tracking123(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.3 : page principale (choix en tuiles) et carte plein écran « Plan de vol personnel » (barre sur deux lignes, légende) ----
PLAN_TXT = {
    "fr": {"title": "PLAN DE VOL PERSONNEL", "click": "Je clique pour", "apt": "Aéroports", "ac": "Avion", "leg": "Légende",
           "l1": "Gros aéroport", "l2": "Moyen", "l3": "Aérodrome", "dep": "Départ", "arr": "Arrivée", "route": "Route",
           "hint": "Sans choix, 1er clic = départ, 2e clic = arrivée", "swap": "Inverser", "clear": "Effacer"},
    "en": {"title": "PERSONAL FLIGHT PLAN", "click": "Click sets", "apt": "Airports", "ac": "Aircraft", "leg": "Legend",
           "l1": "Large airport", "l2": "Medium", "l3": "Airfield", "dep": "Departure", "arr": "Arrival", "route": "Route",
           "hint": "With no choice, 1st click = departure, 2nd click = arrival", "swap": "Swap", "clear": "Clear"},
}

PLAN_CSS = r"""<style id="hangar-123-plan">
/* page principale : choix en tuiles avec voyant et ON / OFF */
html body #btnGenModeManual,html body #btnGenModeRandom,html body #btnModeDep,html body #btnModeArr,html body #btnTypeIfr,html body #btnTypeVfr{
  position:relative!important;justify-content:flex-start!important;gap:9px!important;min-height:44px;padding:6px 26px 6px 8px!important;border-radius:14px!important;
  background:#10161E!important;border:1px solid #1E2733!important;color:#B4C0CF!important;font-size:12px!important;text-align:left;box-shadow:none!important;transform:none!important}
html body #btnGenModeManual i,html body #btnGenModeRandom i,html body #btnModeDep i,html body #btnModeArr i,html body #btnTypeIfr i,html body #btnTypeVfr i{
  width:24px;height:24px;border-radius:50%;background:#1E2733;display:inline-grid;place-items:center;font-size:11px;flex:none;color:#8B98A9!important}
html body #btnGenModeManual::before,html body #btnGenModeRandom::before,html body #btnModeDep::before,html body #btnModeArr::before,html body #btnTypeIfr::before,html body #btnTypeVfr::before{
  content:"";position:absolute;top:8px;right:9px;width:7px;height:7px;border-radius:50%;background:#2A3646}
html body #btnGenModeManual::after,html body #btnGenModeRandom::after,html body #btnModeDep::after,html body #btnModeArr::after,html body #btnTypeIfr::after,html body #btnTypeVfr::after{
  content:"OFF";position:absolute;right:9px;bottom:6px;font-size:9px;font-weight:800;letter-spacing:.06em;color:#5B6778}
html body #btnGenModeManual.bg-cockpit-cyan,html body #btnGenModeRandom.bg-cockpit-cyan,html body #btnModeDep.bg-cockpit-cyan,html body #btnModeArr.bg-cockpit-cyan,html body #btnTypeIfr.bg-cockpit-cyan,html body #btnTypeVfr.bg-cockpit-cyan{
  background:linear-gradient(rgba(56,189,248,.16),rgba(56,189,248,.05))!important;border-color:rgba(56,189,248,.6)!important;color:#F1F5F9!important}
html body [id^="btn"].bg-cockpit-cyan i{background:#38BDF8!important;color:#06202C!important}
html body #btnGenModeManual.bg-cockpit-cyan::before,html body #btnGenModeRandom.bg-cockpit-cyan::before,html body #btnModeDep.bg-cockpit-cyan::before,html body #btnModeArr.bg-cockpit-cyan::before,html body #btnTypeIfr.bg-cockpit-cyan::before,html body #btnTypeVfr.bg-cockpit-cyan::before{background:#38BDF8;box-shadow:0 0 8px #38BDF8}
html body #btnGenModeManual.bg-cockpit-cyan::after,html body #btnGenModeRandom.bg-cockpit-cyan::after,html body #btnModeDep.bg-cockpit-cyan::after,html body #btnModeArr.bg-cockpit-cyan::after,html body #btnTypeIfr.bg-cockpit-cyan::after,html body #btnTypeVfr.bg-cockpit-cyan::after{content:"ON";color:#38BDF8}
html body #btnTypeIfr.bg-cockpit-amber,html body #btnTypeVfr.bg-cockpit-amber{background:linear-gradient(rgba(245,165,36,.18),rgba(245,165,36,.05))!important;border-color:rgba(245,165,36,.6)!important;color:#F1F5F9!important}
html body #btnTypeIfr.bg-cockpit-amber i,html body #btnTypeVfr.bg-cockpit-amber i{background:#F5A524!important;color:#1a1204!important}
html body #btnTypeIfr.bg-cockpit-amber::before,html body #btnTypeVfr.bg-cockpit-amber::before{background:#F5A524;box-shadow:0 0 8px #F5A524}
html body #btnTypeIfr.bg-cockpit-amber::after,html body #btnTypeVfr.bg-cockpit-amber::after{content:"ON";color:#F5A524}
html body #btnGenModeManual:hover,html body #btnGenModeRandom:hover,html body #btnModeDep:hover,html body #btnModeArr:hover,html body #btnTypeIfr:hover,html body #btnTypeVfr:hover{border-color:#33404F!important}
.al-seg{background:transparent!important;border:0!important;padding:0!important;gap:8px!important}

/* carte plein écran : barre sur deux lignes */
html body #mapToolbar{display:flex!important;flex-direction:column!important;align-items:stretch!important;gap:10px!important}
#mapToolbar .al-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
#mapToolbar .al-grow{flex:1}
#mapToolbar .al-title{font:700 13px "Segoe UI",Inter,sans-serif;letter-spacing:.06em;color:#E6EDF5;white-space:nowrap}
#mapToolbar .al-grp{display:flex;align-items:center;gap:8px;padding:4px 10px 4px 12px;border:1px solid #1E2733;border-radius:14px;background:rgba(11,15,20,.75)}
#mapToolbar .al-gl{font:700 10px "Segoe UI",Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#8B98A9;white-space:nowrap}
html body #mapToolbar #modalRouteInfo{display:block!important;font-size:12.5px!important;padding:8px 14px!important;border-radius:999px!important;border:1px solid rgba(52,211,153,.45)!important;background:rgba(11,15,20,.8)!important}
/* tuiles Départ / Arrivée et filtres d'aéroports */
html body #mapToolbar #btnChangeDep,html body #mapToolbar #btnChangeArr,html body #mapToolbar #filterBtnLarge,html body #mapToolbar #filterBtnMedium,html body #mapToolbar #filterBtnSmall{
  position:relative!important;display:inline-flex!important;align-items:center;gap:7px;height:38px;padding:0 28px 0 12px!important;border-radius:12px!important;
  background:#10161E!important;border:1px solid #1E2733!important;color:#B4C0CF!important;font:700 12px "Segoe UI",Inter,sans-serif!important;opacity:1!important;transform:none!important;box-shadow:none!important}
html body #mapToolbar #btnChangeDep::before,html body #mapToolbar #btnChangeArr::before,html body #mapToolbar #filterBtnLarge::before,html body #mapToolbar #filterBtnMedium::before,html body #mapToolbar #filterBtnSmall::before{
  content:"";position:absolute;top:7px;right:8px;width:7px;height:7px;border-radius:50%;background:#2A3646}
html body #mapToolbar #btnChangeDep::after,html body #mapToolbar #btnChangeArr::after,html body #mapToolbar #filterBtnLarge::after,html body #mapToolbar #filterBtnMedium::after,html body #mapToolbar #filterBtnSmall::after{
  content:"OFF";position:absolute;right:7px;bottom:5px;font-size:8.5px;font-weight:800;letter-spacing:.06em;color:#5B6778}
html body #mapToolbar #btnChangeDep.scale-105,html body #mapToolbar #btnChangeArr.scale-105,html body #mapToolbar #filterBtnLarge.bg-cockpit-900,html body #mapToolbar #filterBtnMedium.bg-cockpit-900,html body #mapToolbar #filterBtnSmall.bg-cockpit-900{
  background:linear-gradient(rgba(56,189,248,.16),rgba(56,189,248,.05))!important;border-color:rgba(56,189,248,.6)!important;color:#F1F5F9!important}
html body #mapToolbar #btnChangeDep.scale-105::before,html body #mapToolbar #btnChangeArr.scale-105::before,html body #mapToolbar #filterBtnLarge.bg-cockpit-900::before,html body #mapToolbar #filterBtnMedium.bg-cockpit-900::before,html body #mapToolbar #filterBtnSmall.bg-cockpit-900::before{background:#38BDF8;box-shadow:0 0 8px #38BDF8}
html body #mapToolbar #btnChangeDep.scale-105::after,html body #mapToolbar #btnChangeArr.scale-105::after,html body #mapToolbar #filterBtnLarge.bg-cockpit-900::after,html body #mapToolbar #filterBtnMedium.bg-cockpit-900::after,html body #mapToolbar #filterBtnSmall.bg-cockpit-900::after{content:"ON";color:#38BDF8}
html body #mapToolbar #btnChangeArr.scale-105{background:linear-gradient(rgba(245,165,36,.18),rgba(245,165,36,.05))!important;border-color:rgba(245,165,36,.6)!important}
html body #mapToolbar #btnChangeArr.scale-105::before{background:#F5A524;box-shadow:0 0 8px #F5A524}
html body #mapToolbar #btnChangeArr.scale-105::after{color:#F5A524}
#mapToolbar #btnChangeDep b{color:#38BDF8}#mapToolbar #btnChangeArr b{color:#F5A524}
html body #mapToolbar #modalAircraftSearchInput{height:36px}
html body #mapToolbar #mapCruiseAltitudeSelect{max-width:none!important;min-width:160px}
html body #mapToolbar .al-grp > div[class*="relative"]{width:200px!important}
/* légende de la carte plein écran */
#alPlanLegend{position:absolute;right:12px;bottom:12px;z-index:1000;background:rgba(11,15,20,.92);border:1px solid #2A3646;border-radius:12px;padding:10px 12px;font:12px "Segoe UI",Inter,sans-serif;color:#E6EDF5;line-height:1.75}
#alPlanLegend .d{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:0}
#alPlanLegend .m{color:#8B98A9;font-size:11px}
</style>"""

PLAN_JS = r"""<script>
/* Hangar FS 2024 12.3 : barre de la carte plein écran rangée sur deux lignes (mêmes boutons, mêmes fonctions) + légende */
(function () {
  var T = __TXT__;
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function build() {
    var tb = document.getElementById('mapToolbar'); if (!tb || tb._al) return; tb._al = true;
    var q = function (s) { return tb.querySelector(s); };
    var back = q('button[onclick="closeInteractiveMapModal()"]'), theme = q('button[onclick^="toggleMapTheme"]');
    var close = tb.querySelectorAll('button[onclick="closeInteractiveMapModal()"]'); close = close[close.length - 1];
    var info = document.getElementById('modalRouteInfo'), swap = q('button[onclick="swapInteractiveRoute()"]'),
        reset = q('button[onclick="resetInteractiveSelection()"]'), valid = document.getElementById('applyRouteBtn');
    var dep = document.getElementById('btnChangeDep'), arr = document.getElementById('btnChangeArr');
    var fL = document.getElementById('filterBtnLarge'), fM = document.getElementById('filterBtnMedium'), fS = document.getElementById('filterBtnSmall');
    var acBox = document.getElementById('modalAircraftSearchInput'); acBox = acBox && acBox.closest('.relative.z-\\[100\\]') || (acBox && acBox.parentNode.parentNode);
    var alt = document.getElementById('mapCruiseAltitudeSelect'); alt = alt && alt.parentNode;
    if (swap) swap.insertAdjacentHTML('beforeend', ' ' + T.swap); if (reset) reset.insertAdjacentHTML('beforeend', ' ' + T.clear);
    var r1 = el('div', 'al-row'), r2 = el('div', 'al-row');
    [back, el('span', 'al-title', '🗺 ' + T.title), el('span', 'al-grow'), info, swap, reset, valid, close].forEach(function (x) { if (x) r1.appendChild(x); });
    var g1 = el('div', 'al-grp', '<span class="al-gl">' + T.click + '</span>'); g1.title = T.hint; [dep, arr].forEach(function (x) { if (x) g1.appendChild(x); });
    var g2 = el('div', 'al-grp', '<span class="al-gl">' + T.apt + '</span>'); [fL, fM, fS].forEach(function (x) { if (x) g2.appendChild(x); });
    var g3 = el('div', 'al-grp', '<span class="al-gl">' + T.ac + '</span>'); if (acBox) g3.appendChild(acBox);
    var g4 = el('div', 'al-grp'); if (alt) g4.appendChild(alt);
    [g1, g2, g3, g4, el('span', 'al-grow'), theme].forEach(function (x) { if (x) r2.appendChild(x); });
    while (tb.firstChild) tb.removeChild(tb.firstChild);
    tb.appendChild(r1); tb.appendChild(r2);
    var wrap = document.getElementById('fullMapWrapper');
    if (wrap && !document.getElementById('alPlanLegend')) {
      var lg = el('div', '', '<div><span class="d" style="background:#38BDF8"></span>' + T.l1 + ' &nbsp; <span class="d" style="background:#F5B544"></span>' + T.l2 +
        ' &nbsp; <span class="d" style="background:#F0E442"></span>' + T.l3 + '</div><div><b style="color:#38BDF8">▲</b> ' + T.dep + ' &nbsp; <b style="color:#F5A524">■</b> ' + T.arr +
        ' &nbsp; <span style="color:#38BDF8">┅</span> ' + T.route + '</div><div class="m">' + T.hint + '</div>');
      lg.id = 'alPlanLegend'; wrap.appendChild(lg);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
</script>"""


def patch_plan123(path, lang):
    s = open(path, encoding="utf-8").read()
    if 'id="hangar-123-plan"' in s:
        print("déjà fait (plan 12.3) :", path); return
    import re, json
    t = PLAN_TXT[lang]
    # libellés Départ / Arrivée avec une forme (lisible sans les couleurs)
    for bid, sym in (("btnChangeDep", "▲"), ("btnChangeArr", "■")):
        m = re.search(r'(<button id="%s"[^>]*>)\s*([^<]+?)\s*</button>' % bid, s)
        assert m, bid
        s = s.replace(m.group(0), m.group(1) + "<b>%s</b> %s</button>" % (sym, m.group(2).strip().capitalize()), 1)
    # conteneurs des choix de la page principale : plus d'encadré, tuiles espacées
    for bid in ("btnGenModeManual", "btnModeDep", "btnTypeIfr"):
        i = s.index('id="%s"' % bid); j = s.rindex('<div class="grid grid-cols-2 gap-1 p-1', 0, i)
        s = s[:j] + '<div class="al-seg grid grid-cols-2 gap-1 p-1' + s[j + len('<div class="grid grid-cols-2 gap-1 p-1'):]
    # le lien Ma VA / légende : la légende se replie comme celles du suivi
    s = s.replace("['alPerfSolo', T.perf]];", "['alPerfSolo', T.perf], ['alPlanLegend', T.leg]];", 1)
    s = s.replace("<!--HANGAR_CB-->", PLAN_CSS + PLAN_JS.replace("__TXT__", json.dumps(t, ensure_ascii=False)) + "<!--HANGAR_CB-->", 1)
    open(path, "w", encoding="utf-8").write(s)
    print("ok (plan 12.3) :", path)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_plan123(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.3 : pendant un zoom, les avions ne sont plus déplacés (sinon ils « flottent » au-dessus de la carte) ----
ZOOM_JS = r"""<script id="hangar-123-zoom">
/* Hangar FS 2024 12.3 : les positions des avions sont mises à jour chaque seconde ; pendant un zoom, une mise à jour
   les replaçait à l'échelle de l'ancien zoom, et ils semblaient flotter au-dessus de la carte. On la garde pour la fin du zoom. */
(function () {
  function guard() {
    if (!window.L || !L.Marker || L.Marker.prototype._alZoomGuard) return !!(window.L && L.Marker);
    var P = L.Marker.prototype, setLL = P.setLatLng, setIc = P.setIcon;
    P._alZoomGuard = true;
    function busy(m) { return m && (m._alZooming || m._animatingZoom); }
    function later(mk, m) {
      if (mk._alPend) return; mk._alPend = true;
      m.once('zoomend', function () {
        mk._alPend = false;
        if (mk._alIcon) { var ic = mk._alIcon; mk._alIcon = null; setIc.call(mk, ic); }
        if (mk._map) setLL.call(mk, mk._latlng);
      });
    }
    P.setLatLng = function (ll) {
      var m = this._map;
      if (busy(m)) { this._latlng = L.latLng(ll); later(this, m); return this; }
      return setLL.call(this, ll);
    };
    P.setIcon = function (ic) {
      var m = this._map;
      if (busy(m)) { this._alIcon = ic; this.options.icon = ic; later(this, m); return this; }
      return setIc.call(this, ic);
    };
    return true;
  }
  /* fond de carte : pas de fondu entre l'ancien et le nouveau niveau de zoom (sinon les deux cartes se voient l'une sur l'autre) */
  /* sous le fond choisi, une copie très allégée (niveau 6, quelques images seulement) : pendant qu'une zone se charge,
     on voit cette version floue au lieu de rectangles sombres. Et le zoom avance par demi-crans, plus doux. */
  function backdrop(m, l) {
    if (m._alBack && m._alBack._src === l) return;
    if (m._alBack) { m.removeLayer(m._alBack); m._alBack = null; }
    var o = {}; for (var k in l.options) o[k] = l.options[k];
    o.maxNativeZoom = 6; o.minZoom = 0; o.keepBuffer = 1; o.zIndex = 0; o.attribution = '';
    var b = L.tileLayer(l._url, o); b._alBackdrop = true; b._src = l; m._alBack = b;
    l.setZIndex(1); b.addTo(m);
  }
  /* image de carte qui n'arrive pas (serveur surchargé…) : on réessaie 2 fois, après une courte pause */
  function retry(l) {
    l.on('tileerror', function (e) {
      var img = e.tile, n = +(img.getAttribute('data-al-try') || 0);
      if (n >= 2 || !e.coords) return;
      img.setAttribute('data-al-try', n + 1);
      setTimeout(function () {
        if (!img.parentNode) return;                       /* l'image n'est plus à l'écran */
        var u = l.getTileUrl(e.coords);
        img.src = u + (u.indexOf('?') < 0 ? '?' : '&') + 'r=' + (n + 1);
      }, 800 * (n + 1));
    });
  }
  function tiles(m) {
    if (!m) return;
    var base = null;
    m.eachLayer(function (l) {
      if (!(l instanceof L.TileLayer) || l._alBackdrop) return;
      if (!l._alT) { l._alT = true; l.options.keepBuffer = 4; l.options.updateInterval = 150; retry(l); }
      base = l;
    });
    if (base) backdrop(m, base);
    else if (m._alBack) { m.removeLayer(m._alBack); m._alBack = null; }
    if (!m._alTileHook) { m._alTileHook = true; m.on('layeradd layerremove', function (e) { if (e.layer instanceof L.TileLayer && !e.layer._alBackdrop) setTimeout(function () { tiles(m); }, 0); }); }
  }
  function hook() {
    var m = null, f = null; try { m = (typeof trafficMap !== 'undefined') ? trafficMap : null; f = (typeof fullMap !== 'undefined') ? fullMap : null; } catch (e) {}
    if (m && !m._alZoomHook) {
      m._alZoomHook = true;
      m.on('zoomstart', function () { m._alZooming = true; });
      m.on('zoomend', function () { m._alZooming = false; });
    }
    tiles(m); tiles(f);
  }
  var t = setInterval(function () { if (guard()) hook(); }, 500);
})();
</script>"""


def patch_zoom123(path):
    s = open(path, encoding="utf-8").read()
    if 'id="hangar-123-zoom"' in s:
        print("déjà fait (zoom 12.3) :", path); return
    assert s.count("<!--HANGAR_CB-->") == 1
    s = s.replace("<!--HANGAR_CB-->", ZOOM_JS + "<!--HANGAR_CB-->", 1)
    open(path, "w", encoding="utf-8").write(s)
    print("ok (zoom 12.3) :", path)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_zoom123(os.path.join(_web, "dispatch_%s.html" % _l))


# ---- 12.3 : plus de lignes noires entre les carrés de la carte ----
SEAMS_CSS = '<style id="hangar-123-seams">/* 12.3 : plus de lignes noires entre les carrés de la carte (affichage Windows agrandi) */\n.leaflet-container{background:#1A2430!important}/* fond pendant le chargement des carrés : sombre au lieu de blanc */\n\n</style>'


def patch_seams123(path):
    s = open(path, encoding="utf-8").read()
    if 'hangar-123-seams' in s:
        return
    s = s.replace("</head>", SEAMS_CSS + "</head>", 1)
    tag = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"'
    if False:
        s = s.replace(tag, '' + tag, 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_seams123(os.path.join(_web, "dispatch_%s.html" % _l))


# ---- 12.3 : rotation des avions sans redessiner l'icône (appliquée directement dans les pages) ----
ROT_JS = '<script id="hangar-123-rot">\n/* 12.3 : quand seul le cap change, on tourne l\'avion déjà affiché au lieu de redessiner son icône (pas de scintillement) */\nwindow.alTurn = function (mk, oldSig, newSig, hdg) {\n  if (!mk || oldSig == null) return false;\n  var a = String(oldSig), b = String(newSig), i = a.indexOf(\'|\'), j = b.indexOf(\'|\');\n  if (i < 0 || j < 0 || a.slice(i) !== b.slice(j)) return false;      /* autre chose que le cap a changé */\n  var el = mk.getElement && mk.getElement(), svg = el && el.querySelector(\'svg\');\n  if (!svg) return false;\n  svg.style.transform = \'rotate(\' + (hdg || 0) + \'deg)\';\n  return true;\n};\n</script>'


# ---- 12.4 : aéroports sur la carte de suivi (bouton AÉROPORTS, codes OACI selon le zoom, nom au survol) ----
APT_TXT = {
 "fr": {"btn": "AÉROPORTS", "tip": "Afficher les aéroports (codes OACI) : les grands d'abord, les moyens puis les petits en zoomant. Survole un aéroport pour voir son nom.",
        "names": "NOMS", "namesTip": "Afficher aussi le nom sous le code OACI"},
 "en": {"btn": "AIRPORTS", "tip": "Show airports (ICAO codes): large ones first, then medium and small ones as you zoom in. Hover an airport to see its name.",
        "names": "NAMES", "namesTip": "Also show the name under the ICAO code"},
}
APT_CSS = r"""<style id="hangar-124-apt">
.hg-apt{background:none!important;border:none!important}
.hg-apt .d{position:absolute;left:-5px;top:-5px;width:10px;height:10px;border-radius:50%;background:#38BDF8;border:2px solid #06121C;box-shadow:0 0 0 1px rgba(255,255,255,.75)}
.hg-apt.m .d{left:-4px;top:-4px;width:8px;height:8px;background:#7DD3FC}
.hg-apt.s .d{left:-4px;top:-4px;width:8px;height:8px;background:#FFFFFF;border-width:2px}
.hg-apt .c{position:absolute;left:8px;top:-9px;white-space:nowrap;font:800 10.5px/1.25 system-ui,Segoe UI,sans-serif;color:#7DD3FC;letter-spacing:.4px;
  background:rgba(6,18,28,.88);border:1px solid #2B6F92;border-radius:4px;padding:0 4px;text-shadow:none;pointer-events:auto}
.hg-apt.l .c{color:#38BDF8;border-color:#38BDF8}
.hg-apt.s .c{font-size:9.5px;font-weight:700;color:#C8E6F5;border-color:#3A5568}
.hg-apt .n{display:block;font-weight:600;font-size:9.5px;letter-spacing:0;color:#DCE6F0;max-width:160px;overflow:hidden;text-overflow:ellipsis}
.leaflet-tooltip.hg-apt-tip{background:#0E1A24;color:#E6EDF5;border:1px solid #1F5E7E;border-radius:8px;font:12px/1.35 system-ui,Segoe UI,sans-serif;padding:5px 9px}
.leaflet-tooltip.hg-apt-tip:before{display:none}
html body #trafficMapModal>.avionics-panel button#hgAptBtn,html body #trafficMapModal>.avionics-panel button#hgAptNamesBtn{background:#1A2633!important;color:#9FB3C8!important;border:1px solid #33475A!important;opacity:1!important}
html body #trafficMapModal>.avionics-panel button#hgAptBtn[aria-pressed="true"],html body #trafficMapModal>.avionics-panel button#hgAptNamesBtn[aria-pressed="true"]{background:#38BDF8!important;color:#06202C!important;border-color:transparent!important}
</style>"""
APT_JS = r"""<script id="hangar-124-apt-js">
(function () {
  var T = __TXT__;
  var KEY = 'hangar_apt_on', KEYN = 'hangar_apt_names';
  function rd(k) { try { return localStorage.getItem(k) === '1'; } catch (e) { return false; } }
  function wr(k, v) { try { localStorage.setItem(k, v ? '1' : '0'); } catch (e) {} }
  var on = rd(KEY), names = rd(KEYN), map = null, layer = null, lists = null, listsSize = 0, timer = null;
  /* grands visibles dès le zoom 4, moyens dès 8, petits dès 9 ; au plus 350 étiquettes à la fois */
  var MINZ = { large_airport: 4, medium_airport: 8, small_airport: 9, seaplane_base: 10 };
  var CLS = { large_airport: 'l', medium_airport: 'm', small_airport: 's', seaplane_base: 's' };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function db() { try { return (typeof airportsDB !== 'undefined' && airportsDB) ? airportsDB : null; } catch (e) { return null; } }
  function build() {
    var d = db(); if (!d) return false;
    var keys = Object.keys(d); if (lists && keys.length === listsSize) return true;
    lists = { large_airport: [], medium_airport: [], small_airport: [], seaplane_base: [] }; listsSize = keys.length;
    for (var i = 0; i < keys.length; i++) { var a = d[keys[i]]; if (a && lists[a.type]) lists[a.type].push(a); }
    return true;
  }
  function draw() {
    if (!map || !layer) return;
    layer.clearLayers();
    if (!on || !build()) return;
    var z = map.getZoom(), b = map.getBounds().pad(0.1), n = 0, MAX = 350;
    var order = ['large_airport', 'medium_airport', 'small_airport', 'seaplane_base'];
    for (var t = 0; t < order.length && n < MAX; t++) {
      if (z < MINZ[order[t]]) continue;
      var L0 = lists[order[t]];
      for (var i = 0; i < L0.length && n < MAX; i++) {
        var a = L0[i];
        if (!/^[A-Z][A-Z0-9]{3}$/.test(a.icao)) continue;   /* sans vrai code OACI (ex. FR-0931 : petits terrains privés) : on n'affiche pas */
        if (!b.contains([a.lat, a.lon])) continue;
        var html = '<span class="d"></span><span class="c">' + esc(a.icao) + (names ? '<span class="n">' + esc(a.name) + '</span>' : '') + '</span>';
        var mk = L.marker([a.lat, a.lon], { icon: L.divIcon({ className: 'hg-apt ' + CLS[order[t]], html: html, iconSize: [0, 0] }),
                                            pane: 'hgApt', keyboard: false, interactive: true, bubblingMouseEvents: true });
        var place = [a.city, a.country].filter(Boolean).join(', ');
        mk.bindTooltip('<b>' + esc(a.icao) + '</b> — ' + esc(a.name) + (place ? '<br><span style="color:#9FB3C8">' + esc(place) + '</span>' : '') +
                       (a.elevation_ft ? '<br><span style="color:#9FB3C8">' + Math.round(a.elevation_ft) + ' ft</span>' : ''),
                       { className: 'hg-apt-tip', direction: 'top', offset: [0, -6] });
        layer.addLayer(mk); n++;
      }
    }
  }
  function later() { clearTimeout(timer); timer = setTimeout(draw, 120); }
  function paintBtn() {
    var b = document.getElementById('hgAptBtn'); if (b) b.setAttribute('aria-pressed', String(on));
    var n = document.getElementById('hgAptNamesBtn'); if (n) { n.setAttribute('aria-pressed', String(names)); n.style.display = on ? '' : 'none'; }
  }
  window.hgToggleAirports = function () { on = !on; wr(KEY, on); paintBtn(); draw(); };
  window.hgToggleAptNames = function () { names = !names; wr(KEYN, names); paintBtn(); draw(); };
  function mkBtn(id, icon, text, tip, fn) {
    var b = document.createElement('button');
    b.id = id; b.type = 'button'; b.title = tip; b.setAttribute('aria-pressed', 'false');
    b.className = 'px-2.5 py-1 bg-cockpit-800 text-slate-200 text-[10px] font-bold rounded transition border border-cockpit-border cursor-pointer whitespace-nowrap';
    b.innerHTML = '<i class="fa-solid ' + icon + '"></i> ' + text;
    b.onclick = fn; return b;
  }
  function addButton() {
    if (document.getElementById('hgAptBtn')) return true;
    var ref = document.getElementById('trafficToggleBtn'); if (!ref) return false;
    var btn = mkBtn('hgAptBtn', 'fa-plane-departure', T.btn, T.tip, window.hgToggleAirports);
    var nb = mkBtn('hgAptNamesBtn', 'fa-font', T.names, T.namesTip, window.hgToggleAptNames);
    ref.parentNode.insertBefore(btn, ref.nextSibling);
    btn.parentNode.insertBefore(nb, btn.nextSibling);
    paintBtn(); return true;
  }
  function attach() {
    var m = null; try { m = (typeof trafficMap !== 'undefined' && trafficMap) ? trafficMap : null; } catch (e) {}
    if (!m || typeof L === 'undefined') return false;
    if (m === map) return true;
    map = m;
    if (!map.getPane('hgApt')) { var p = map.createPane('hgApt'); p.style.zIndex = 450; }
    layer = L.layerGroup().addTo(map);
    map.on('moveend zoomend', later);
    draw(); return true;
  }
  setInterval(function () {
    addButton(); attach();
    /* la base des aéroports finit de charger après la carte : on redessine une fois qu'elle est complète */
    if (on && map && (!lists || listsSize < 5000) && db() && Object.keys(db()).length !== listsSize) draw();
  }, 1000);
})();
</script>"""


def patch_apt124(path, lang):
    s = open(path, encoding="utf-8").read()
    if 'hangar-124-apt' in s:
        return
    import json
    s = s.replace("</head>", APT_CSS + "</head>", 1)
    s = s.replace("</body>", APT_JS.replace("__TXT__", json.dumps(APT_TXT[lang], ensure_ascii=False)) + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_apt124(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.6 : fin de vol = carte propre ; METAR en vol libre ; import d'un plan .PLN (MSFS ou appli) ----
FLT_TXT = {
 "fr": {"free": "METAR · VOL LIBRE", "dep": "DÉP", "arr": "ARR", "refresh": "Actualiser les METAR",
        "hint": "Pas de plan de vol : le METAR du départ s'affiche quand ton avion est au sol sur un aéroport (ou tape son code). Tape un aéroport d'arrivée pour voir son METAR.",
        "depAuto": "trouvé automatiquement d'après la position de ton avion", "phDep": "auto", "phArr": "OACI",
        "pln": ".PLN", "plnTip": "Afficher un plan de vol .PLN (enregistré depuis la carte du monde de MSFS, ou exporté par Avionics Dispatch)",
        "plnOk": "Plan .PLN chargé", "plnBad": "Fichier .PLN illisible ou sans points de route", "noPlan": "SimBrief : aucun plan importé",
        "ended": "Vol terminé dans Hangar FS 2024 : la carte est remise à zéro."},
 "en": {"free": "METAR · FREE FLIGHT", "dep": "DEP", "arr": "ARR", "refresh": "Refresh METAR",
        "hint": "No flight plan: the departure METAR shows when your aircraft is on the ground at an airport (or type its code). Type an arrival airport to see its METAR.",
        "depAuto": "found automatically from your aircraft's position", "phDep": "auto", "phArr": "ICAO",
        "pln": ".PLN", "plnTip": "Show a .PLN flight plan (saved from the MSFS world map, or exported by Avionics Dispatch)",
        "plnOk": ".PLN plan loaded", "plnBad": "Unreadable .PLN file or no waypoints", "noPlan": "SimBrief: no plan imported",
        "ended": "Flight ended in Hangar FS 2024: the map has been reset."},
}
FLT_CSS = r"""<style id="hangar-126-flt">
#tmFree{display:flex;align-items:center;gap:6px;margin:2px 0 6px;flex-wrap:wrap}
#tmFree label{display:flex;align-items:center;gap:4px;font-weight:700;color:#7DD3FC}
#tmFree input{width:64px;background:#0B1520;border:1px solid #2B6F92;border-radius:5px;color:#E6EDF5;padding:2px 5px;font:700 11px/1.3 ui-monospace,Consolas,monospace;text-transform:uppercase}
#tmFree input:focus{outline:none;border-color:#38BDF8}
#tmFree .auto{font-size:9.5px;color:#8FA3B8}
#hgPlnBtn{white-space:nowrap}
</style>"""
FLT_JS = r"""<script id="hangar-126-flt-js">
(function () {
  var T = __TXT__, RELAY = 'http://localhost:8765';
  var free = { dep: '', arr: '', auto: '' };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function db() { try { return (typeof airportsDB !== 'undefined' && airportsDB) ? airportsDB : null; } catch (e) { return null; } }
  function nm(a, b, c, d) { var r = Math.PI / 180, x = Math.sin((c - a) * r / 2), y = Math.sin((d - b) * r / 2);
    var h = x * x + Math.cos(a * r) * Math.cos(c * r) * y * y; return 3440.065 * 2 * Math.asin(Math.min(1, Math.sqrt(h))); }
  function code(v) { v = String(v || '').trim().toUpperCase(); try { if (typeof resolveAirportCode === 'function') { var r = resolveAirportCode(v); if (r) return String(r).toUpperCase(); } } catch (e) {} return v; }
  function hasPlan() { try { return !!(sbPlanAirports && (sbPlanAirports.dep || sbPlanAirports.arr)); } catch (e) { return false; } }

  /* ---------- aérodrome de départ trouvé d'après la position de ton avion au sol ---------- */
  function nearest(lat, lon) {
    var d = db(); if (!d) return '';
    var best = '', bd = 3;   /* à moins de 3 NM */
    for (var k in d) { var a = d[k]; if (!a || !/^[A-Z][A-Z0-9]{3}$/.test(a.icao) || Math.abs(a.lat - lat) > 0.1) continue;
      var x = nm(lat, lon, a.lat, a.lon); if (x < bd) { bd = x; best = a.icao; } }
    return best;
  }
  function watchDep() {
    var u = window.alUser;
    if (!u || u.lat == null || !u.ground) return;
    var n = nearest(u.lat, u.lon);
    if (n && n !== free.auto) { free.auto = n; if (!hasPlan() && tmSel.label === 'LIBRE') useFree(); }
  }

  /* ---------- METAR : plan s'il y en a un, sinon vol libre (jamais l'ancien plan ni les aéroports d'exemple) ---------- */
  function useFree() {
    tmSel = { dep: free.dep || free.auto || '', arr: free.arr || '', label: 'LIBRE' };
    var n = document.getElementById('tmNote'); if (n) n.style.display = 'none';
    tmRefresh();
  }
  tmUsePlan = function () {
    if (hasPlan()) { tmSet(sbPlanAirports.dep, sbPlanAirports.arr, 'PLAN'); return; }
    useFree();
  };
  var origHeader = tmHeader;
  tmHeader = function (label) {
    if (label !== 'LIBRE') return origHeader(label);
    var depVal = free.dep || '', autoTxt = !free.dep && free.auto ? '<span class="auto" title="' + esc(T.depAuto) + '">auto : ' + esc(free.auto) + '</span>' : '';
    return '<div class="flex items-center gap-2 mb-1"><b class="text-white">' + esc(T.free) + '</b>' +
      '<button onclick="tmUsePlan()" title="' + esc(T.refresh) + '" class="ml-auto px-1.5 py-0.5 bg-cockpit-800 border border-cockpit-border rounded cursor-pointer hover:bg-cockpit-cyan hover:text-cockpit-950"><i class="fa-solid fa-rotate"></i></button></div>' +
      '<div id="tmFree"><label>' + esc(T.dep) + ' <input id="tmFreeDep" maxlength="8" placeholder="' + esc(free.auto || T.phDep) + '" value="' + esc(depVal) + '"></label>' + autoTxt +
      '<label>' + esc(T.arr) + ' <input id="tmFreeArr" maxlength="8" placeholder="' + esc(T.phArr) + '" value="' + esc(free.arr) + '"></label></div>';
  };
  var origRefresh = tmRefresh;
  tmRefresh = function () {
    var box = document.getElementById('tmBody');
    if (box && box.contains(document.activeElement) && document.activeElement.tagName === 'INPUT') return;   /* on ne coupe pas la saisie */
    if (tmSel.label === 'LIBRE' && !tmSel.dep && !tmSel.arr) {
      if (box) box.innerHTML = tmHeader('LIBRE') + '<div class="text-slate-400">' + esc(T.hint) + '</div>';
      return;
    }
    return origRefresh.apply(this, arguments);
  };
  document.addEventListener('change', function (e) {
    var id = e.target && e.target.id;
    if (id !== 'tmFreeDep' && id !== 'tmFreeArr') return;
    if (id === 'tmFreeDep') free.dep = code(e.target.value); else free.arr = code(e.target.value);
    e.target.blur(); useFree();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target && (e.target.id === 'tmFreeDep' || e.target.id === 'tmFreeArr')) e.target.dispatchEvent(new Event('change', { bubbles: true }));
  });

  /* ---------- fin du vol dans Hangar FS 2024 : plus de plan, de trajectoire ni de METAR de l'ancien vol ---------- */
  function clearPlan(silent) {
    try { if (typeof sbLayer !== 'undefined' && sbLayer) sbLayer.clearLayers(); } catch (e) {}
    try { if (typeof sbLabelLayer !== 'undefined' && sbLabelLayer) sbLabelLayer.clearLayers(); } catch (e) {}
    try { sbFixes = []; sbBounds = null; } catch (e) {}
    try { sbPlanAirports = null; } catch (e) {}
    var info = document.getElementById('sbInfo'); if (info) { info.innerHTML = ''; info.classList.add('hidden'); }
    try { if (typeof setSbStatus === 'function') setSbStatus(T.noPlan, false); } catch (e) {}
    window.alPlanData = null; window.alFlightAirports = null;
    try { window.dispatchEvent(new Event('al-plan-clear')); } catch (e) {}
    if (window.alTrackReset) window.alTrackReset();
    free = { dep: '', arr: '', auto: '' };
    useFree();
    if (!silent && window.hgFlightToast) window.hgFlightToast(T.ended);
  }
  window.hgClearPlan = clearPlan;
  var hadPlan = null;
  function pollPlan() {
    fetch(RELAY + '/plan-current', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (p) {
      var has = !!(p && p.has);
      window.hgAppHasPlan = has;
      if (hadPlan === true && !has) clearPlan(false);
      hadPlan = has;
    }).catch(function () {});
  }

  /* ---------- plan .PLN (carte du monde de MSFS, Avionics Dispatch, Little Navmap…) ---------- */
  function dms(s) {
    var m = String(s).trim().match(/^([NSEW])\s*(\d+)[°\s]+(\d+)['\s]+([\d.]+)/i);
    if (!m) { var f = parseFloat(s); return Number.isFinite(f) ? f : NaN; }
    var v = (+m[2]) + (+m[3]) / 60 + parseFloat(m[4]) / 3600;
    return /[SW]/i.test(m[1]) ? -v : v;
  }
  function parsePln(text) {
    var x = new DOMParser().parseFromString(text, 'application/xml');
    if (x.getElementsByTagName('parsererror').length) return null;
    var g = function (n, tag) { var e = n.getElementsByTagName(tag)[0]; return e ? e.textContent.trim() : ''; };
    var wps = Array.prototype.slice.call(x.getElementsByTagName('ATCWaypoint')), fix = [];
    wps.forEach(function (w, i) {
      var pos = g(w, 'WorldPosition').split(','), lat = dms(pos[0]), lon = dms(pos[1]), alt = parseFloat(pos[2]);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
      var type = g(w, 'ATCWaypointType'), id = g(w, 'ICAOIdent') || w.getAttribute('id') || ('WP' + (i + 1));
      fix.push({ ident: id, name: '', type: /airport/i.test(type) ? 'apt' : 'wpt', via_airway: g(w, 'ATCAirway'),
                 pos_lat: lat, pos_long: lon, altitude_feet: Number.isFinite(alt) && alt > 0 ? Math.round(alt) : '',
                 is_sid_star: (g(w, 'DepartureFP') || g(w, 'ArrivalFP') || g(w, 'ApproachTypeFP')) ? 1 : 0 });
    });
    if (fix.length < 2) return null;
    var dep = (g(x, 'DepartureID') || fix[0].ident).toUpperCase(), arr = (g(x, 'DestinationID') || fix[fix.length - 1].ident).toUpperCase();
    var a0 = fix[0], a1 = fix[fix.length - 1], cruise = parseInt(g(x, 'CruisingAlt'), 10) || 0;
    return { navlog: { fix: fix },
      origin: { icao_code: dep, pos_lat: a0.pos_lat, pos_long: a0.pos_long }, destination: { icao_code: arr, pos_lat: a1.pos_lat, pos_long: a1.pos_long },
      general: { route: fix.slice(1, -1).map(function (f) { return f.ident; }).join(' '), initial_altitude: cruise },
      aircraft: {}, atc: {}, tlr: null, params: { time_generated: Math.floor(Date.now() / 1000) } };
  }
  function loadPln(file) {
    var rd = new FileReader();
    rd.onload = function () {
      var d = null; try { d = parsePln(String(rd.result || '')); } catch (e) { d = null; }
      if (!d) { try { setSbStatus(T.plnBad, true); } catch (e) {} return; }
      try { (window.drawSimbriefPlan || drawSimbriefPlan)(d); } catch (e) { try { setSbStatus(T.plnBad, true); } catch (e2) {} return; }
      try { setSbStatus(T.plnOk + ' : ' + d.origin.icao_code + ' → ' + d.destination.icao_code + ' (' + file.name + ')', false); } catch (e) {}
    };
    rd.readAsText(file);
  }
  function addPlnButton() {
    if (document.getElementById('hgPlnBtn')) return;
    var ref = document.querySelector('#trafficMapModal button[onclick="importSimbriefPlan()"]'); if (!ref) return;
    var inp = document.createElement('input'); inp.type = 'file'; inp.accept = '.pln,.PLN,.xml'; inp.style.display = 'none'; inp.id = 'hgPlnFile';
    inp.onchange = function () { if (inp.files && inp.files[0]) loadPln(inp.files[0]); inp.value = ''; };
    var b = document.createElement('button'); b.type = 'button'; b.id = 'hgPlnBtn'; b.title = T.plnTip;
    b.className = 'px-2 py-1 bg-cockpit-800 text-slate-200 text-[10px] font-bold rounded transition border border-cockpit-border cursor-pointer whitespace-nowrap';
    b.innerHTML = '<i class="fa-solid fa-file-import"></i> ' + T.pln;
    b.onclick = function () { inp.click(); };
    ref.parentNode.insertBefore(b, ref.nextSibling); ref.parentNode.insertBefore(inp, b.nextSibling);
  }

  window.hgFlightToast = function (msg) {
    var wrap = document.getElementById('trafficMapWrapper'); if (!wrap) return;
    var t = document.getElementById('alPlanToast');
    if (!t) { t = document.createElement('div'); t.id = 'alPlanToast'; wrap.appendChild(t); }
    t.className = 'ok'; t.textContent = msg; t.style.display = '';
    clearTimeout(t._hg); t._hg = setTimeout(function () { t.style.display = 'none'; }, 6000);
  };

  function start() {
    pollPlan(); setInterval(pollPlan, 4000);
    setInterval(function () { addPlnButton(); watchDep(); }, 3000);
    addPlnButton();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
</script>"""

TRACK_OLD_LOAD = "  function load() { try { var t = JSON.parse(localStorage.getItem(KEY)); if (t && t.pts) return t; } catch (e) {} return { sig: '', pts: [] }; }"
TRACK_NEW_LOAD = ("  /* 12.6 : une trajectoire non mise à jour depuis 30 min (vol terminé, appli fermée) n'est pas reprise */\n"
                  "  function load() { try { var t = JSON.parse(localStorage.getItem(KEY)); if (t && t.pts && t.t && Date.now() - t.t < 30 * 60000) return t; } catch (e) {} return { sig: '', pts: [] }; }")
TRACK_OLD_SAVE = "  function save() { try { localStorage.setItem(KEY, JSON.stringify(tr)); } catch (e) {} }"
TRACK_NEW_SAVE = ("  function save() { tr.t = Date.now(); try { localStorage.setItem(KEY, JSON.stringify(tr)); } catch (e) {} }\n"
                  "  window.alTrackReset = function () { tr = { sig: '', pts: [] }; save(); draw(); };")
FETCH_OLD = "    if (plan || Date.now() - lastPlanTry < 60000) return;"
FETCH_NEW = "    if (plan || window.hgAppHasPlan !== true || Date.now() - lastPlanTry < 60000) return;   /* 12.6 : seulement si un vol est préparé dans Hangar FS 2024 */"
PLAN_OLD = "  function takePlan(data) {"
PLAN_NEW = ("  window.addEventListener('al-plan-clear', function () { plan = null; });   /* 12.6 : vol terminé dans Hangar FS 2024 */\n"
            "  function takePlan(data) {")


def patch_flt126(path, lang):
    s = open(path, encoding="utf-8").read()
    if 'hangar-126-flt' in s:
        return
    import json
    for a, b in ((TRACK_OLD_LOAD, TRACK_NEW_LOAD), (TRACK_OLD_SAVE, TRACK_NEW_SAVE), (PLAN_OLD, PLAN_NEW), (FETCH_OLD, FETCH_NEW)):
        assert s.count(a) == 1, (path, a[:50])
        s = s.replace(a, b)
    s = s.replace("</head>", FLT_CSS + "</head>", 1)
    s = s.replace("</body>", FLT_JS.replace("__TXT__", json.dumps(FLT_TXT[lang], ensure_ascii=False)) + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_flt126(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.6 : carte « Plan de vol personnel » sans les terrains sans vrai code OACI (FR-0901…) ----
FULLMAP_OLD = "                if (!airportFilters[categoryKey]) continue;\n"
FULLMAP_NEW = ("                if (!airportFilters[categoryKey]) continue;\n"
               "                if (!/^[A-Z][A-Z0-9]{3}$/.test(apt.icao)) continue;   /* 12.6 : sans vrai code OACI (petits terrains privés) : pas affiché */\n")


def patch_fullmap126(path):
    s = open(path, encoding="utf-8").read()
    if "12.6 : sans vrai code OACI" in s:
        return
    assert s.count(FULLMAP_OLD) == 1, path
    open(path, "w", encoding="utf-8").write(s.replace(FULLMAP_OLD, FULLMAP_NEW))


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_fullmap126(os.path.join(_web, "dispatch_%s.html" % _l))


# ---- 12.6 : code OACI aussi sur les aérodromes (points jaunes) de la carte Plan de vol personnel, dès le zoom 8 ----
SMALLLBL_OLD = ("                if (showLabels && categoryKey !== 'small') {\n"
                "                    const label = L.divIcon({ className: 'oaci-label', html: escapeHtml(apt.icao), iconSize: [45, 16], iconAnchor: [-8, 12] });")
SMALLLBL_NEW = ("                if (showLabels && (categoryKey !== 'small' || zoom >= 8)) {   /* 12.6 : aérodromes aussi, en plus petit, dès le zoom 8 */\n"
                "                    const label = L.divIcon({ className: categoryKey === 'small' ? 'oaci-label oaci-small' : 'oaci-label', html: escapeHtml(apt.icao), iconSize: [45, 16], iconAnchor: [-8, 12] });")
SMALLLBL_CSS = '<style id="hangar-126-smalllbl">.oaci-label.oaci-small{font-size:9px!important;opacity:.92}</style>'


def patch_smalllbl126(path):
    s = open(path, encoding="utf-8").read()
    if "hangar-126-smalllbl" in s:
        return
    assert s.count(SMALLLBL_OLD) == 1, path
    s = s.replace(SMALLLBL_OLD, SMALLLBL_NEW).replace("</head>", SMALLLBL_CSS + "</head>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_smalllbl126(os.path.join(_web, "dispatch_%s.html" % _l))


# ---- 12.6 : aérodrome sans données de piste = « à vérifier » (et non refusé) ; légende des aérodromes en jaune ----
RWYDATA = {
 "fr": ("? { status: 'blocked', reasons: [`${icao} : données de piste insuffisantes, validation refusée`], detail: null }",
        "? { status: 'conditional', reasons: [`${icao} : données de piste absentes de la base, longueur et revêtement à vérifier`], detail: null }   /* 12.6 */"),
 "en": ("? { status: 'blocked', reasons: [`${icao}: insufficient runway data, validation refused`], detail: null }",
        "? { status: 'conditional', reasons: [`${icao}: runway data missing from the database, check length and surface`], detail: null }   /* 12.6 */"),
}


def patch_rwydata126(path, lang):
    s = open(path, encoding="utf-8").read()
    if "/* 12.6 */" not in s:
        a, b = RWYDATA[lang]
        assert s.count(a) == 1, path
        s = s.replace(a, b)
    s = s.replace("<span class=\"d\" style=\"background:#c084fc\"></span>' + T.l3", "<span class=\"d\" style=\"background:#F0E442\"></span>' + T.l3")
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_rwydata126(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.6 : barre de la carte de suivi rangée en deux lignes et en groupes (comme Plan de vol personnel) ----
LAY_TXT = {"fr": {"plan": "Plan de vol", "map": "Carte", "va": "VA FSHub"},
           "en": {"plan": "Flight plan", "map": "Map", "va": "FSHub VA"}}
LAY_CSS = r"""<style id="hangar-126-lay">
html body #trafficMapModal>.avionics-panel.hg-lay{display:flex!important;flex-direction:column!important;align-items:stretch!important;gap:9px!important}
#trafficMapModal .hg-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
#trafficMapModal .hg-grow{flex:1 1 auto}
#trafficMapModal .hg-grp{display:flex;align-items:center;gap:7px;padding:4px 8px 4px 12px;border:1px solid #1E2733;border-radius:14px;background:rgba(11,15,20,.75);flex-wrap:wrap}
#trafficMapModal .hg-gl{font:700 10px "Segoe UI",Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#8B98A9;white-space:nowrap;margin-right:2px}
html body #trafficMapModal .hg-grp>div[class*="border"]{background:transparent!important;border:0!important;padding:0!important;box-shadow:none!important}
#trafficMapModal .hg-status{display:flex;flex-direction:column;line-height:1.25;min-width:0}
</style>"""
LAY_JS = r"""<script id="hangar-126-lay-js">
(function () {
  var T = __TXT__;
  function q(sel) { return document.querySelector(sel); }
  function byClick(fn, pred) {
    var l = document.querySelectorAll('#trafficMapModal button[onclick="' + fn + '"]');
    for (var i = 0; i < l.length; i++) if (!pred || pred(l[i])) return l[i];
    return null;
  }
  function el(tag, cls, html) { var e = document.createElement(tag); e.className = cls; if (html) e.innerHTML = html; return e; }
  function grp(id, label) { var g = document.getElementById(id); if (!g) { g = el('div', 'hg-grp'); g.id = id; g.appendChild(el('span', 'hg-gl', label)); } return g; }
  function place(box, items, skip) {   /* range les éléments dans l'ordre voulu en ne déplaçant que ceux mal placés
                                           (déplacer une liste ouverte, comme Rayon, la refermerait) */
    items = items.filter(Boolean); skip = skip || 0;
    items.forEach(function (x, i) {
      var at = box.children[skip + i];
      if (at !== x) box.insertBefore(x, at || null);
    });
  }
  function layout() {
    var panel = q('#trafficMapModal>.avionics-panel'); if (!panel) return;
    var r1 = document.getElementById('hgRow1'), r2 = document.getElementById('hgRow2');
    if (!r1) { r1 = el('div', 'hg-row'); r1.id = 'hgRow1'; r2 = el('div', 'hg-row'); r2.id = 'hgRow2'; panel.insertBefore(r2, panel.firstChild); panel.insertBefore(r1, r2); panel.classList.add('hg-lay'); }
    var gPlan = grp('hgGrpPlan', T.plan), gMap = grp('hgGrpMap', T.map), gVa = grp('hgGrpVa', T.va);
    var menu = byClick('closeTrafficMapModal()', function (b) { return !b.classList.contains('w-6'); });
    var close = byClick('closeTrafficMapModal()', function (b) { return b.classList.contains('w-6'); });
    var title = null; Array.prototype.forEach.call(panel.querySelectorAll('span'), function (s) { if (!title && s.querySelector('.fa-tower-broadcast')) title = s; });
    var st = document.getElementById('trafficStatus'), status = st ? st.parentNode : null;
    if (status && status !== r1) status.classList.add('hg-status');
    var sb = document.getElementById('sbUserInput'), sbBox = sb ? sb.parentNode : null;
    var grow = document.getElementById('hgGrow'); if (!grow) { grow = el('span', 'hg-grow'); grow.id = 'hgGrow'; }
    place(r1, [menu, title, gVa, status, grow, document.getElementById('hgJBtn'), document.getElementById('alFoldAll'), close]);
    place(gPlan, [sbBox, byClick('fitSimbriefPlan()')], 1);
    place(gMap, [document.getElementById('trafficToggleBtn'), document.getElementById('trafficShowGroundBtn'), document.getElementById('trafficFollowBtn'),
                 document.getElementById('hgAptBtn'), document.getElementById('hgAptNamesBtn'), document.getElementById('alAerowayBtn')], 1);
    var vaItems = [document.getElementById('alFshubBtn'), document.getElementById('alFshubAllBtn'), document.getElementById('alFshubRad')];
    place(gVa, vaItems, 1);
    gVa.style.display = vaItems.some(function (x) { return x && x.style.display !== 'none'; }) ? '' : 'none';
    place(r2, [gPlan, gMap]);
    /* VA FSHub juste au-dessus du groupe Carte : Menu + titre prennent la largeur du groupe Plan de vol */
    if (menu && title && gPlan.offsetWidth) { var w = gPlan.offsetWidth - menu.offsetWidth - 10; title.style.minWidth = (w > 0 ? w : 0) + 'px'; title.style.display = 'inline-block'; }
  }
  setInterval(layout, 1000);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', layout); else layout();
})();
</script>"""


def patch_lay126(path, lang):
    s = open(path, encoding="utf-8").read()
    if "hangar-126-lay" in s:
        return
    import json
    s = s.replace("</head>", LAY_CSS + "</head>", 1)
    s = s.replace("</body>", LAY_JS.replace("__TXT__", json.dumps(LAY_TXT[lang], ensure_ascii=False)) + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_lay126(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.7 : nouveau look de la carte de suivi (boutons unifiés, encadrés en verre, METAR en tableau de bord) ----
LOOK_TXT = {
 "fr": {"wind": "Vent", "vis": "Visibilité", "cloud": "Nuages", "temp": "Temp. / rosée", "qnh": "QNH", "raw": "METAR brut", "calm": "calme", "var": "variable",
        "gust": "rafales", "clear": "dégagé", "load": "chargement…", "none": "METAR non disponible", "more": "≥ 10 km"},
 "en": {"wind": "Wind", "vis": "Visibility", "cloud": "Clouds", "temp": "Temp / dew", "qnh": "QNH", "raw": "Raw METAR", "calm": "calm", "var": "variable",
        "gust": "gusts", "clear": "clear", "load": "loading…", "none": "METAR not available", "more": "≥ 10 km"},
}
LOOK_CSS = r"""<style id="hangar-127-look">
/* --- barre : un seul style de bouton, allumé = contour bleu ciel ; la couleur du calque devient une pastille --- */
html body #trafficMapModal #hgRow1 button.hg-tg,html body #trafficMapModal #hgRow2 button.hg-tg,
html body #trafficMapModal #hgRow1 button.hg-act,html body #trafficMapModal #hgRow2 button.hg-act{
  background:#121A24!important;color:#A9B6C6!important;border:1px solid #273343!important;border-radius:999px!important;box-shadow:none!important;
  padding:6px 13px 6px 11px!important;font:650 11px/1.2 "Segoe UI Variable Text","Segoe UI",Inter,sans-serif!important;letter-spacing:.03em!important;
  transition:background .15s,border-color .15s,color .15s!important;opacity:1!important;text-shadow:none!important}
html body #trafficMapModal #hgRow1 button.hg-tg *,html body #trafficMapModal #hgRow2 button.hg-tg *,
html body #trafficMapModal #hgRow1 button.hg-act *,html body #trafficMapModal #hgRow2 button.hg-act *{color:inherit!important}
html body #trafficMapModal #hgRow1 button.hg-tg::before,html body #trafficMapModal #hgRow2 button.hg-tg::before{
  content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--dot,#64748B);margin-right:7px;vertical-align:1px;opacity:.45;transition:opacity .15s,box-shadow .15s}
html body #trafficMapModal #hgRow1 button.hg-tg.on,html body #trafficMapModal #hgRow2 button.hg-tg.on{
  background:linear-gradient(180deg,rgba(56,189,248,.20),rgba(56,189,248,.08))!important;border-color:rgba(56,189,248,.85)!important;color:#F1F5F9!important}
html body #trafficMapModal #hgRow1 button.hg-tg.on::before,html body #trafficMapModal #hgRow2 button.hg-tg.on::before{opacity:1;box-shadow:0 0 8px var(--dot,#38BDF8)}
html body #trafficMapModal #hgRow1 button.hg-tg:hover,html body #trafficMapModal #hgRow2 button.hg-tg:hover,
html body #trafficMapModal #hgRow1 button.hg-act:hover,html body #trafficMapModal #hgRow2 button.hg-act:hover{border-color:rgba(125,211,252,.7)!important;color:#FFFFFF!important}
html body #trafficMapModal #hgRow2 button.hg-act.pri{background:#38BDF8!important;color:#06202C!important;border-color:transparent!important}
html body #trafficMapModal #hgRow2 button.hg-act.pri:hover{background:#7DD3FC!important;color:#06202C!important}
html body #trafficMapModal #hgRow1 #alFshubRad{background:#121A24!important;color:#C9D4E0!important;border:1px solid #273343!important;border-radius:999px!important;padding:5px 10px!important;font:650 11px "Segoe UI",Inter,sans-serif!important}
#trafficMapModal .hg-grp{border-color:#1C2633!important;background:rgba(9,13,19,.72)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.03)}

/* --- encadrés sur la carte : même verre fumé, même police, plus d'air --- */
html body #trafficMapWrapper .al-fold:not(.al-col){background:rgba(9,14,21,.93)!important;border:1px solid rgba(125,211,252,.20)!important;border-radius:14px!important;
  box-shadow:0 12px 32px rgba(0,0,0,.45)!important;color:#DCE6F0!important;font-family:"Segoe UI Variable Text","Segoe UI",Inter,sans-serif!important;padding:10px 12px!important}
html body #trafficMapWrapper .al-fold.al-col{background:rgba(9,14,21,.90)!important;box-shadow:0 6px 18px rgba(0,0,0,.4)!important}
html body #trafficMetarBox,html body #tmBody,html body #sbInfo,html body #alPerfSolo,html body #alPerf{font-family:"Segoe UI Variable Text","Segoe UI",Inter,sans-serif!important;font-size:12px!important;line-height:1.45!important}

/* --- METAR en tableau de bord --- */
.hm{margin:2px 0 10px}
.hm-h{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.hm-t{font:700 9.5px "Segoe UI",Inter,sans-serif;letter-spacing:.1em;color:#7DD3FC;text-transform:uppercase}
.hm-i{font:800 14px "Segoe UI",Inter,sans-serif;color:#FFFFFF;letter-spacing:.04em}
.hm-n{font-size:11px;color:#8FA3B8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;flex:1}
.hm-c{font:800 10px "Segoe UI",Inter,sans-serif;letter-spacing:.06em;padding:2px 8px;border-radius:999px;color:#06121C}
.hm-c.VFR{background:#22C55E}.hm-c.MVFR{background:#3B82F6;color:#fff}.hm-c.IFR{background:#EF4444;color:#fff}.hm-c.LIFR{background:#D946EF;color:#fff}
.hm-g{display:grid;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));gap:6px}
.hm-k{background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:6px 8px;min-width:0}
.hm-l{font:700 9px "Segoe UI",Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#7F93A8}
.hm-v{font:700 13px/1.25 "Segoe UI",Inter,sans-serif;color:#F1F5F9;display:flex;align-items:center;flex-wrap:wrap;gap:2px 6px}
.hm-v small{font-size:10.5px;color:#9FB3C8;font-weight:600}
.hm-v .br{flex-basis:100%;height:0}
.hm-v svg{flex:none}
.hm-raw{margin-top:6px}
.hm-raw summary{cursor:pointer;font-size:10.5px;color:#7F93A8;list-style:none}
.hm-raw summary::before{content:"▸ "}.hm-raw[open] summary::before{content:"▾ "}
.hm-raw code{display:block;margin-top:4px;font:11px/1.4 ui-monospace,Consolas,monospace;color:#C8D3DF;white-space:normal;word-break:break-word}
.hm-wait{color:#8FA3B8;font-size:11.5px}.hm-no{color:#F5A524;font-size:11.5px}
</style>"""
LOOK_JS = r"""<script id="hangar-127-look-js">
(function () {
  var T = __TXT__;
  /* boutons : même style partout, une pastille de la couleur du calque */
  var TG = [['trafficToggleBtn', '#38BDF8', 'aria'], ['trafficShowGroundBtn', '#94A3B8', 'aria'], ['trafficFollowBtn', '#F59E0B', 'aria'],
            ['hgAptBtn', '#7DD3FC', 'aria'], ['hgAptNamesBtn', '#CBD5E1', 'aria'], ['alAerowayBtn', '#FACC15', 'off'],
            ['alFshubBtn', '#F5B731', 'off'], ['alFshubAllBtn', '#C04FCF', 'off']];
  function skin() {
    TG.forEach(function (d) {
      var b = document.getElementById(d[0]); if (!b) return;
      b.classList.add('hg-tg'); b.style.setProperty('--dot', d[1]);
      var on = d[2] === 'aria' ? b.getAttribute('aria-pressed') === 'true' : !b.classList.contains('off');
      b.classList.toggle('on', on);
    });
    var acts = [document.querySelector('#trafficMapModal button[onclick="importSimbriefPlan()"]'), document.getElementById('hgPlnBtn'),
                document.querySelector('#trafficMapModal button[onclick="fitSimbriefPlan()"]'), document.getElementById('alFoldAll')];
    acts.forEach(function (b, i) { if (b) { b.classList.add('hg-act'); if (i === 0) b.classList.add('pri'); } });
    var m = document.querySelector('#hgRow1 button[onclick="closeTrafficMapModal()"]:not(.w-6)'); if (m) m.classList.add('hg-act');
  }
  setInterval(skin, 400);

  /* METAR : vent, visibilité, nuages, température, QNH et catégorie de vol, le METAR brut à déplier */
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function parse(raw) {
    var r = { }, s = ' ' + String(raw).split(/\s(?:TEMPO|BECMG|NOSIG|RMK|TREND)\s/)[0] + ' ';   /* partie observée seulement, sans la tendance */
    var w = s.match(/\s(VRB|\d{3})(\d{2,3})(?:G(\d{2,3}))?(KT|MPS)\s/);
    if (w) { var k = w[4] === 'MPS' ? 1.944 : 1; r.dir = w[1]; r.spd = Math.round(parseInt(w[2], 10) * k); r.gust = w[3] ? Math.round(parseInt(w[3], 10) * k) : 0; }
    if (/\sCAVOK\s/.test(s)) { r.vis = 10; r.cavok = true; }
    else {
      var v = s.match(/\s(\d{4})(?:NDV)?\s/), sm = s.match(/\s(?:(\d+)\s)?(\d+)(?:\/(\d+))?SM\s/);
      if (v) r.vis = parseInt(v[1], 10) >= 9999 ? 10 : parseInt(v[1], 10) / 1000;
      else if (sm) { var mi = (sm[1] ? +sm[1] : 0) + (sm[3] ? (+sm[2]) / (+sm[3]) : +sm[2]); r.vis = mi * 1.609; }
    }
    var cl = [], re = /\s(FEW|SCT|BKN|OVC|VV)(\d{3})/g, m;
    while ((m = re.exec(s))) { cl.push([m[1], parseInt(m[2], 10) * 100]); re.lastIndex--; }
    r.clouds = cl;
    var ceil = cl.filter(function (c) { return c[0] === 'BKN' || c[0] === 'OVC' || c[0] === 'VV'; }).map(function (c) { return c[1]; });
    r.ceil = ceil.length ? Math.min.apply(null, ceil) : null;
    var t = s.match(/\s(M?\d{2})\/(M?\d{2})?\s/);
    if (t) { var f = function (x) { return x ? (x[0] === 'M' ? -parseInt(x.slice(1), 10) : parseInt(x, 10)) : null; }; r.t = f(t[1]); r.dp = f(t[2]); }
    var q = s.match(/\sQ(\d{4})\s/), a = s.match(/\sA(\d{4})\s/);
    if (q) r.qnh = q[1] + ' hPa'; else if (a) r.qnh = (parseInt(a[1], 10) / 100).toFixed(2) + ' inHg';
    var c = 'VFR', ce = r.ceil == null ? 99999 : r.ceil, vi = r.vis == null ? 99 : r.vis;
    if (ce < 500 || vi < 1.6) c = 'LIFR'; else if (ce < 1000 || vi < 4.8) c = 'IFR'; else if (ce <= 3000 || vi <= 8) c = 'MVFR';
    r.cat = (r.vis == null && r.ceil == null && !r.cavok) ? '' : c;
    return r;
  }
  function arrow(dir) {   /* flèche dans le sens où souffle le vent */
    return '<svg width="16" height="16" viewBox="0 0 16 16" style="transform:rotate(' + ((+dir + 180) % 360) + 'deg)"><path d="M8 1 L12.5 13 L8 10.3 L3.5 13 Z" fill="#7DD3FC"/></svg>';
  }
  function tile(l, v) { return '<div class="hm-k"><div class="hm-l">' + l + '</div><div class="hm-v">' + v + '</div></div>'; }
  tmCard = function (title, icao, raw) {
    var ap = null; try { ap = airportsDB[icao]; } catch (e) {}
    var name = ap ? (ap.city && ap.name.indexOf(ap.city) < 0 ? ap.city + ' · ' + ap.name : ap.name) : '';
    var body = '', cat = '';
    if (!icao) body = '<div class="hm-wait">—</div>';
    else if (raw === '…') body = '<div class="hm-wait">' + T.load + '</div>';
    else if (!raw) body = '<div class="hm-no">' + T.none + '</div>';
    else {
      var p = parse(raw), tiles = [];
      if (p.dir != null) tiles.push(tile(T.wind, p.spd === 0 ? T.calm : (p.dir === 'VRB' ? T['var'] : arrow(p.dir) + p.dir + '°') + ' ' + p.spd + ' kt' + (p.gust ? '<span class="br"></span><small>' + T.gust + ' ' + p.gust + ' kt</small>' : '')));
      if (p.vis != null) tiles.push(tile(T.vis, p.vis >= 10 ? T.more : (p.vis < 5 ? p.vis.toFixed(1) : Math.round(p.vis)) + ' km'));
      tiles.push(tile(T.cloud, p.cavok ? 'CAVOK' : (p.clouds.length ? p.clouds.slice(0, 2).map(function (c) { return c[0] + ' <small>' + c[1].toLocaleString() + ' ft</small>'; }).join('<span class="br"></span>') : T.clear)));
      if (p.t != null) tiles.push(tile(T.temp, p.t + '° <small>/ ' + (p.dp != null ? p.dp + '°' : '—') + '</small>'));
      if (p.qnh) tiles.push(tile(T.qnh, p.qnh));
      cat = p.cat ? '<span class="hm-c ' + p.cat + '">' + p.cat + '</span>' : '';
      body = '<div class="hm-g">' + tiles.join('') + '</div><details class="hm-raw"><summary>' + T.raw + '</summary><code>' + esc(raw) + '</code></details>';
    }
    return '<div class="hm"><div class="hm-h"><span class="hm-t">' + esc(title) + '</span><span class="hm-i">' + esc(icao || '----') + '</span><span class="hm-n">' + esc(name) + '</span>' + cat + '</div>' + body + '</div>';
  };
})();
</script>"""


def patch_look127(path, lang):
    s = open(path, encoding="utf-8").read()
    if "hangar-127-look" in s:
        return
    import json
    s = s.replace("</head>", LOOK_CSS + "</head>", 1)
    s = s.replace("</body>", LOOK_JS.replace("__TXT__", json.dumps(LOOK_TXT[lang], ensure_ascii=False)) + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_look127(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.7 (suite) : piste et vent en dessin, vol façon carte d'embarquement, finitions ----
LOOK2_TXT = {
 "fr": {"head": "face", "tail": "arrière", "cross": "travers", "calm": "vent calme", "vrb": "vent variable", "rwy": "piste"},
 "en": {"head": "head", "tail": "tail", "cross": "cross", "calm": "calm wind", "vrb": "variable wind", "rwy": "runway"},
}
LOOK2_CSS = r"""<style id="hangar-127-look2">
/* piste et vent : schéma */
.hg-rw{display:flex;align-items:center;gap:12px;margin:2px 0 8px;padding:8px 10px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:12px}
.hg-rw svg{flex:none}
.hg-rw .k{font:700 9px "Segoe UI",Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#7F93A8}
.hg-rw .v{font:800 15px/1.2 "Segoe UI",Inter,sans-serif;color:#F1F5F9}
.hg-rw .v.ok{color:#4ADE80}.hg-rw .v.warn{color:#F5A524}.hg-rw .v.bad{color:#F87171}
.hg-rw .g{display:grid;grid-template-columns:auto auto;gap:2px 14px}
/* vol en cours : carte d'embarquement */
.hg-bp{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:14px;margin:10px 0 4px}
.hg-bp .ap{min-width:0}
.hg-bp .ic{font:800 26px/1 "Segoe UI Variable Display","Segoe UI",Inter,sans-serif;color:#FFFFFF;letter-spacing:.04em}
.hg-bp .ct{font-size:11px;color:#8FA3B8;margin-top:3px;max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hg-bp .ap.r{text-align:right}
.hg-bp .ln{position:relative;height:26px}
.hg-bp .ln::before{content:"";position:absolute;left:0;right:0;top:50%;border-top:2px dashed rgba(148,163,184,.35)}
.hg-bp .ln .done{position:absolute;left:0;top:50%;height:2px;margin-top:-1px;background:linear-gradient(90deg,rgba(56,189,248,.2),#38BDF8);border-radius:2px;transition:width .8s ease}
.hg-bp .ln .pl{position:absolute;top:50%;width:22px;height:22px;margin:-11px 0 0 -11px;transition:left .8s ease;filter:drop-shadow(0 0 6px rgba(56,189,248,.6))}
.hg-bp .ln .dot{position:absolute;top:50%;width:8px;height:8px;margin-top:-4px;border-radius:50%;background:#38BDF8}
.hg-bp .ln .dot.e{right:0;background:#0B1520;border:2px solid #38BDF8;width:10px;height:10px;margin-top:-5px}
#alFlightPanel .hg-bp~.alf-bar{display:none!important}
/* finitions */
@keyframes hgIn{from{opacity:0}to{opacity:1}}
html body #trafficMapWrapper .al-fold:not(.al-col){animation:hgIn .22s ease both}   /* sur l'encadré seulement (à l'ouverture), pas sur son contenu redessiné chaque seconde */
html body #trafficMapWrapper .leaflet-tooltip:not(.hg-apt-tip){background:rgba(9,14,21,.95)!important;color:#E6EDF5!important;border:1px solid rgba(125,211,252,.25)!important;
  border-radius:10px!important;box-shadow:0 8px 24px rgba(0,0,0,.45)!important;font:12px/1.4 "Segoe UI",Inter,sans-serif!important;padding:6px 10px!important}
html body #trafficMapWrapper .leaflet-tooltip::before{display:none!important}
html body #trafficMapWrapper .leaflet-control-zoom a{background:rgba(9,14,21,.92)!important;color:#E6EDF5!important;border-color:rgba(125,211,252,.2)!important}
html body #trafficMapWrapper .leaflet-control-zoom a:hover{background:rgba(56,189,248,.2)!important}
html body #trafficMapWrapper .leaflet-control-zoom{border:1px solid rgba(125,211,252,.2)!important;border-radius:12px!important;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,.4)!important}
#trafficMapModal ::-webkit-scrollbar{width:8px;height:8px}
#trafficMapModal ::-webkit-scrollbar-thumb{background:rgba(125,211,252,.25);border-radius:8px}
#trafficMapModal ::-webkit-scrollbar-track{background:transparent}
</style>"""
LOOK2_JS = r"""<script id="hangar-127-look2-js">
(function () {
  var T = __TXT__;
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  /* ---- piste et vent en dessin : la piste orientée, la flèche du vent, les composantes ---- */
  window.hgRwy = function (name, mt, c) {
    var n = parseInt(String(name || '').replace(/[^0-9]/g, ''), 10); if (!n) return '';
    var hdg = (n % 36) * 10 || 360, opp = ((n + 18 - 1) % 36) + 1;
    var xw = 15; try { var v = parseInt(localStorage.getItem('al_xwind_max'), 10); if (v > 0) xw = v; } catch (e) {}
    var wind = '';
    if (mt && mt.spd != null && !mt.vrb && mt.spd > 0) {
      wind = '<g transform="rotate(' + mt.dir + ' 50 50)"><line x1="50" y1="4" x2="50" y2="30" stroke="#7DD3FC" stroke-width="3" stroke-linecap="round"/>' +
             '<path d="M43 26 L50 38 L57 26 Z" fill="#7DD3FC"/></g>';
    }
    var rw = '<g transform="rotate(' + hdg + ' 50 50)"><rect x="44" y="18" width="12" height="64" rx="2" fill="#2B3644" stroke="#8FA3B8" stroke-width="1"/>' +
             '<line x1="50" y1="24" x2="50" y2="76" stroke="#E6EDF5" stroke-width="1" stroke-dasharray="4 4"/>' +
             '</g>';
    var rad = hdg * Math.PI / 180, dx = Math.sin(rad), dy = -Math.cos(rad);
    rw += '<text x="' + (50 - dx * 43).toFixed(1) + '" y="' + (53 - dy * 43).toFixed(1) + '" text-anchor="middle" font-size="9" font-weight="800" fill="#FFFFFF" font-family="Segoe UI,sans-serif" paint-order="stroke" stroke="#0B121A" stroke-width="3">' + esc(name) + '</text>' +
          '<text x="' + (50 + dx * 43).toFixed(1) + '" y="' + (53 + dy * 43).toFixed(1) + '" text-anchor="middle" font-size="8" font-weight="700" fill="#8FA3B8" font-family="Segoe UI,sans-serif" paint-order="stroke" stroke="#0B121A" stroke-width="3">' + String(opp).padStart(2, '0') + '</text>';
    var svg = '<svg width="92" height="92" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="none" stroke="rgba(148,163,184,.25)" stroke-width="1"/>' +
              '<text x="50" y="9" text-anchor="middle" font-size="7" fill="#64748B" font-family="Segoe UI,sans-serif">N</text>' + rw + wind + '</svg>';
    var info;
    if (!mt || mt.spd == null) info = '';
    else if (mt.vrb) info = '<div class="v">' + T.vrb + ' ' + mt.spd + ' kt</div>';
    else if (!mt.spd) info = '<div class="v ok">' + T.calm + '</div>';
    else if (c) {
      var hc = c.head >= 0 ? 'ok' : (c.head > -3 ? 'warn' : 'bad'), xc = (c.cross > xw || c.gcross > xw) ? 'bad' : (c.cross > xw * 0.7 ? 'warn' : 'ok');
      info = '<div class="g"><div><div class="k">' + (c.head >= 0 ? T.head : T.tail) + '</div><div class="v ' + hc + '">' + Math.abs(c.head) + ' kt</div></div>' +
             '<div><div class="k">' + T.cross + '</div><div class="v ' + xc + '">' + c.cross + (c.gcross > c.cross ? '<small style="font-size:10px"> / ' + c.gcross + '</small>' : '') + ' kt</div></div></div>';
    } else info = '';
    return '<div class="hg-rw">' + svg + '<div><div class="k">' + T.rwy + ' ' + esc(name) + '</div>' + info + '</div></div>';
  };

  /* ---- vol en cours façon carte d'embarquement ---- */
  var PLANE = '<svg class="pl" viewBox="0 0 24 24"><path fill="#FFFFFF" d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z" transform="rotate(90 12 12)"/></svg>';
  function apInfo(icao) { var a = null; try { a = airportsDB[icao]; } catch (e) {} return a ? (a.city || a.name || '') : ''; }
  function pass() {
    var host = document.getElementById('alFlightPanel'); if (!host) return;
    var bar = host.querySelector('.alf-bar'), pd = window.alPlanData;
    var old = host.querySelector('.hg-bp');
    if (!bar || !pd || !pd.origin || !pd.destination) { if (old) old.remove(); return; }
    var dep = String(pd.origin.icao_code || '').toUpperCase(), arr = String(pd.destination.icao_code || '').toUpperCase();
    var b = bar.querySelector('b'), pct = b ? parseFloat(b.style.width) || 0 : 0;
    var key = dep + arr;
    if (!old || old.parentNode !== bar.parentNode) {
      if (old) old.remove();
      old = document.createElement('div'); old.className = 'hg-bp';
      bar.parentNode.insertBefore(old, bar);
    }
    if (old.dataset.k !== key) {
      old.dataset.k = key;
      old.innerHTML = '<div class="ap"><div class="ic">' + esc(dep) + '</div><div class="ct">' + esc(apInfo(dep)) + '</div></div>' +
        '<div class="ln"><span class="dot"></span><span class="done"></span>' + PLANE + '<span class="dot e"></span></div>' +
        '<div class="ap r"><div class="ic">' + esc(arr) + '</div><div class="ct" style="margin-left:auto">' + esc(apInfo(arr)) + '</div></div>';
    }
    old.querySelector('.done').style.width = pct + '%';
    old.querySelector('.pl').style.left = pct + '%';
  }
  setInterval(pass, 1000);
})();
</script>"""
RWY_ANCHORS = [
 ("    var s = head + (t.len ? ' <span class=\"alp-m\">· ' + ft(t.len) + '</span>' : '') +",
  "    var s = (window.hgRwy ? window.hgRwy(t.rwy, t.mt, t.c) : '') + head + (t.len ? ' <span class=\"alp-m\">· ' + ft(t.len) + '</span>' : '') +"),
 ("    var s = head + ' <span class=\"alp-m\">· ' + (l.lda ? ft(l.lda) : '')",
  "    var s = (window.hgRwy ? window.hgRwy(l.rwy, l.mt, l.c) : '') + head + ' <span class=\"alp-m\">· ' + (l.lda ? ft(l.lda) : '')"),
 ("    var h = '<span class=\"alp-l\">▼ ' + esc(icao) + (apt && apt.name",
  "    var h = (window.hgRwy && best ? window.hgRwy(best.name, mt, best.c) : '') + '<span class=\"alp-l\">▼ ' + esc(icao) + (apt && apt.name"),
]


def patch_look127b(path, lang):
    s = open(path, encoding="utf-8").read()
    if "hangar-127-look2" in s:
        return
    import json
    for a, b in RWY_ANCHORS:
        assert s.count(a) == 1, (path, a[:40])
        s = s.replace(a, b)
    s = s.replace("</head>", LOOK2_CSS + "</head>", 1)
    s = s.replace("</body>", LOOK2_JS.replace("__TXT__", json.dumps(LOOK2_TXT[lang], ensure_ascii=False)) + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_look127b(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.7 : journal de vol (enregistrement phase par phase, profil sol-sol TOC/TOD, carte épurée, historique) ----
JRN_TXT = {
 "fr": {"title": "JOURNAL DE VOL", "menu": "MENU PRINCIPAL", "open": "JOURNAL DE VOL", "live": "Vol en cours", "none": "Aucun vol enregistré pour l'instant. Le journal se remplit tout seul pendant ton vol (la fenêtre Plan & suivi de vol doit être ouverte).",
        "del": "Supprimer ce vol", "delQ": "Supprimer ce vol du journal ?", "groups": ["Porte", "Repoussage", "Roulage", "Décollage", "Montée", "Croisière", "Descente", "Approche", "Atterrissage", "Roulage", "Porte d'arrivée"],
        "start": "début", "dur": "durée", "fuel": "carburant", "fob": "carburant à bord", "used": "consommé", "iasMax": "vitesse (IAS) max", "gs": "vitesse sol", "vs": "vario", "alt": "altitude", "ias": "vitesse", "max": "max", "avg": "moy.",
        "rot": "envol à", "td": "toucher", "flaps": "volets", "rate": ["Kiss", "Doux", "Correct", "Ferme", "Dur"],
        "sum": "Résumé", "block": "Temps bloc", "air": "Temps de vol", "fuelT": "Carburant", "dist": "Distance", "maxAlt": "Altitude max", "ldg": "Atterrissage",
        "planned": "prévu", "profile": "Profil du vol", "planProf": "prévu (SimBrief)", "realProf": "réel", "nm": "NM", "ft": "ft", "noPlan": "pas de plan SimBrief : profil réel seulement",
        "wait": "à venir", "now": "en cours", "partial": "enregistrement commencé en vol", "free": "vol libre"},
 "en": {"title": "FLIGHT LOG", "menu": "MAIN MENU", "open": "FLIGHT LOG", "live": "Current flight", "none": "No flight recorded yet. The log fills in by itself during your flight (the Flight plan & tracking window must be open).",
        "del": "Delete this flight", "delQ": "Delete this flight from the log?", "groups": ["Gate", "Pushback", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Taxi", "Arrival gate"],
        "start": "start", "dur": "duration", "fuel": "fuel", "fob": "fuel on board", "used": "burned", "iasMax": "speed (IAS) max", "gs": "ground speed", "vs": "vertical speed", "alt": "altitude", "ias": "speed", "max": "max", "avg": "avg",
        "rot": "liftoff at", "td": "touchdown", "flaps": "flaps", "rate": ["Butter", "Soft", "Good", "Firm", "Hard"],
        "sum": "Summary", "block": "Block time", "air": "Flight time", "fuelT": "Fuel", "dist": "Distance", "maxAlt": "Max altitude", "ldg": "Landing",
        "planned": "planned", "profile": "Flight profile", "planProf": "planned (SimBrief)", "realProf": "actual", "nm": "NM", "ft": "ft", "noPlan": "no SimBrief plan: actual profile only",
        "wait": "to come", "now": "now", "partial": "recording started in flight", "free": "free flight"},
}
JRN_CSS = r"""<style id="hangar-127-jrn">
#hgJournal{position:fixed;inset:0;z-index:9000;display:none;flex-direction:column;background:#0A0E14;color:#DCE6F0;font-family:"Segoe UI Variable Text","Segoe UI",Inter,sans-serif}
#hgJournal.on{display:flex}
#hgJournal .jh{display:flex;align-items:center;gap:10px;padding:12px 16px;background:#0f1724 url(/bg_modal.svg) center 65%/cover no-repeat;border-bottom:1px solid #1E2733;flex-wrap:wrap}
#hgJournal .jt{font:800 12.5px "Segoe UI",Inter,sans-serif;letter-spacing:.08em;color:#E6EDF5}
#hgJournal .jb{background:#121A24;color:#C9D4E0;border:1px solid #273343;border-radius:999px;padding:6px 13px;font:650 11px "Segoe UI",Inter,sans-serif;letter-spacing:.03em;cursor:pointer}
#hgJournal .jb:hover{border-color:rgba(125,211,252,.7);color:#fff}
#hgJournal select.jb{padding:5px 10px;max-width:360px}
#hgJournal .jgrow{flex:1}
#hgJournal .jx{width:28px;height:28px;border-radius:50%;padding:0;display:grid;place-items:center}
#hgJournal .jm{flex:1;display:grid;grid-template-columns:380px minmax(0,1fr);gap:12px;padding:12px;min-height:0}
#hgJournal .jc{background:rgba(9,14,21,.93);border:1px solid rgba(125,211,252,.16);border-radius:14px;box-shadow:0 10px 28px rgba(0,0,0,.35);min-height:0}
#hgJournal .jl{overflow:auto;padding:12px 12px 12px 10px}
#hgJournal .jr{display:grid;grid-template-rows:auto 270px 1fr;grid-template-columns:minmax(0,1fr);gap:12px;min-height:0;min-width:0}
#hgJournal .jk{font:700 9.5px "Segoe UI",Inter,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:#7DD3FC;margin:0 0 8px 2px}
/* frise */
.jp{position:relative;padding:0 0 12px 26px}
.jp::before{content:"";position:absolute;left:8px;top:16px;bottom:-2px;width:2px;background:#1F2A37}
.jp:last-child::before{display:none}
.jp .b{position:absolute;left:1px;top:3px;width:16px;height:16px;border-radius:50%;background:#0B1520;border:2px solid #334155}
.jp.done .b{background:#38BDF8;border-color:#38BDF8}.jp.done::before{background:rgba(56,189,248,.45)}
.jp.now .b{background:#F59E0B;border-color:#F59E0B;box-shadow:0 0 0 4px rgba(245,158,11,.2)}
.jp .n{font:800 14px "Segoe UI",Inter,sans-serif;color:#F1F5F9;display:flex;gap:8px;align-items:baseline}
.jp .n small{font-weight:600;font-size:11.5px;color:#7F93A8}
.jp.wait .n{color:#5B6B7D}
.jp .f{margin-top:5px;display:grid;grid-template-columns:1fr 1fr;gap:4px}
.jp .f div{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.05);border-radius:8px;padding:4px 7px;min-width:0}
.jp .f i{display:block;font-style:normal;font:700 9.5px "Segoe UI",Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#7F93A8}
.jp .f b{font:700 13.5px "Segoe UI",Inter,sans-serif;color:#E6EDF5;white-space:nowrap}
.jp .f .w{grid-column:1/-1}
.jrate{display:inline-block;padding:1px 8px;border-radius:999px;font:800 10px "Segoe UI",Inter,sans-serif;margin-left:4px;color:#06121C}
.jrate.r0,.jrate.r1{background:#22C55E}.jrate.r2{background:#38BDF8}.jrate.r3{background:#F59E0B}.jrate.r4{background:#EF4444;color:#fff}
/* résumé */
.js{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;padding:12px}
.js div{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:8px 10px}
.js i{display:block;font-style:normal;font:700 10px "Segoe UI",Inter,sans-serif;letter-spacing:.09em;text-transform:uppercase;color:#7F93A8}
.js b{font:800 19px "Segoe UI",Inter,sans-serif;color:#FFFFFF}
.js small{display:block;font-size:11.5px;color:#8FA3B8;margin-top:1px}
.jrt{display:flex;align-items:baseline;gap:10px;padding:12px 12px 0;flex-wrap:wrap}
.jrt .ic{font:800 26px "Segoe UI",Inter,sans-serif;color:#fff;letter-spacing:.04em}
.jrt .ar{color:#38BDF8;font-size:18px}
.jrt .meta{font-size:12.5px;color:#8FA3B8}
/* profil */
.jpf{padding:10px 12px;display:flex;flex-direction:column;overflow:hidden;min-width:0}
.jpf svg{display:block}
.jpf .lg{display:flex;gap:14px;font-size:11.5px;color:#8FA3B8;margin:0 0 4px 2px;flex-wrap:wrap}
.jpf .lg span::before{content:"";display:inline-block;width:16px;height:0;border-top:2px solid #38BDF8;margin-right:6px;vertical-align:3px}
.jpf .lg .p::before{border-top:2px dashed #94A3B8}
#hgJMap .hg-jplane{background:none!important;border:0!important;filter:drop-shadow(0 0 6px rgba(245,158,11,.7))}
#hgJMap{border-radius:14px;overflow:hidden;min-height:200px;background:#1A2430!important}
#hgJMap .hg-jdark{filter:invert(1) hue-rotate(180deg) brightness(.85) contrast(.92) saturate(.6)}
.jempty{padding:30px;color:#8FA3B8;font-size:13px;text-align:center}
@media (max-width:1100px){#hgJournal .jm{grid-template-columns:1fr}}
</style>"""
JRN_JS = r"""<script id="hangar-127-jrn-js">
(function () {
  var T = __TXT__;
  var KEY = 'hg_jr_cur', HKEY = 'hg_jr_hist';
  var PLANE_D = 'M12 2c.8 0 1.4.7 1.4 1.5V9l7.6 4.4v2l-7.6-2.3v4.6l2 1.5V21l-3.4-1-3.4 1v-1.8l2-1.5v-4.6L3 15.4v-2L10.6 9V3.5C10.6 2.7 11.2 2 12 2z';
  var GR = [[1, 2], [3], [4], [5], [6], [7], [8], [9, 10], [11], [12], [13, 14]];   /* 12.7 : le repoussage a sa propre phase */
  function grOf(P) { for (var i = 0; i < GR.length; i++) if (GR[i].indexOf(P) >= 0) return i; return -1; }
  function nm(a, b, c, d) { var r = Math.PI / 180, x = Math.sin((c - a) * r / 2), y = Math.sin((d - b) * r / 2);
    var h = x * x + Math.cos(a * r) * Math.cos(c * r) * y * y; return 3440.065 * 2 * Math.asin(Math.min(1, Math.sqrt(h))); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function ld(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }
  function sv(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function bridge() { return window.chrome && window.chrome.webview; }
  function nearest(lat, lon) {
    var d = null; try { d = airportsDB; } catch (e) {} if (!d) return '';
    var best = '', bd = 5;
    for (var k in d) { var a = d[k]; if (!a || !/^[A-Z][A-Z0-9]{3}$/.test(a.icao) || Math.abs(a.lat - lat) > 0.15) continue;
      var x = nm(lat, lon, a.lat, a.lon); if (x < bd) { bd = x; best = a.icao; } }
    return best;
  }

  /* ======================= enregistrement ======================= */
  var rec = ld(KEY), prev = null;
  function planInfo(data) {
    if (!data || !data.navlog) return null;
    var o = data.origin || {}, d = data.destination || {}, fx = [].concat(data.navlog.fix || []);
    var lat0 = parseFloat(o.pos_lat), lon0 = parseFloat(o.pos_long); if (!Number.isFinite(lat0)) return null;
    var cum = 0, pl = lat0, po = lon0, prof = [[0, parseInt(o.elevation, 10) || 0]], route = [[lat0, lon0]], toc = null, tod = null;
    fx.forEach(function (f) {
      var la = parseFloat(f.pos_lat), lo = parseFloat(f.pos_long); if (!Number.isFinite(la) || !Number.isFinite(lo)) return;
      var leg = parseFloat(f.distance); cum += Number.isFinite(leg) && leg >= 0 ? leg : nm(pl, po, la, lo); pl = la; po = lo; route.push([+la.toFixed(4), +lo.toFixed(4)]);   /* distances des étapes SimBrief (SID et STAR comprises) */
      var al = parseInt(f.altitude_feet, 10); if (Number.isFinite(al)) prof.push([+cum.toFixed(1), al]);
      if (f.ident === 'TOC') toc = +cum.toFixed(1); if (f.ident === 'TOD') tod = +cum.toFixed(1);
    });
    var la1 = parseFloat(d.pos_lat), lo1 = parseFloat(d.pos_long);
    var lastFx = fx[fx.length - 1], endsAtDest = lastFx && String(lastFx.ident || '').toUpperCase() === String(d.icao_code || '').toUpperCase();
    if (Number.isFinite(la1)) { if (!endsAtDest) cum += nm(pl, po, la1, lo1); route.push([la1, lo1]); prof.push([+cum.toFixed(1), parseInt(d.elevation, 10) || 0]); }
    var units = String((data.params || {}).units || 'kgs').toLowerCase(), k = /lb/.test(units) ? 0.45359237 : 1;
    var fu = data.fuel || {}, ti = data.times || {};
    return { pv: 2, dep: String(o.icao_code || '').toUpperCase(), arr: String(d.icao_code || '').toUpperCase(),
      fuel: fu.est_burn ? Math.round(parseFloat(fu.est_burn) * k) : null, block: ti.est_block ? Math.round(ti.est_block / 60) : null,
      air: ti.est_time_enroute ? Math.round(ti.est_time_enroute / 60) : null, dist: parseInt((data.general || {}).route_distance, 10) || +cum.toFixed(0),   /* même distance que SimBrief */ cruise: parseInt((data.general || {}).initial_altitude, 10) || null,
      prof: prof, route: route.length > 400 ? route.filter(function (_, i) { return i % 2 === 0; }) : route, toc: toc, tod: tod,
      type: (data.aircraft || {}).icaocode || '', cs: (data.atc || {}).callsign || '', segs: segsOf(data, lat0, lon0) };
  }
  /* SID / route / STAR comme sur la carte de suivi (mêmes couleurs) */
  function segsOf(data, lat0, lon0) {
    try {
      if (typeof parseSimbriefFixes !== 'function' || typeof classifySimbriefLegs !== 'function') return null;
      var fx = parseSimbriefFixes(data); if (fx.length < 2) return null;
      var kinds = classifySimbriefLegs(fx), out = [], cur = null;
      for (var i = 1; i < fx.length; i++) {
        var k = kinds[i - 1];
        if (!cur || cur.k !== k) { cur = { k: k, pts: [[+fx[i - 1].lat.toFixed(4), +fx[i - 1].lon.toFixed(4)]] }; out.push(cur); }
        cur.pts.push([+fx[i].lat.toFixed(4), +fx[i].lon.toFixed(4)]);
      }
      if (out.length && Number.isFinite(lat0)) out[0].pts.unshift([+lat0.toFixed(4), +lon0.toFixed(4)]);
      return { s: out, f: fx.filter(function (f) { return f.type !== 'apt'; }).slice(0, 250).map(function (f, i) { return [+f.lat.toFixed(4), +f.lon.toFixed(4), f.ident]; }) };
    } catch (e) { return null; }
  }
  function attachPlan() {
    if (!rec) return;
    var p = planInfo(window.alPlanFull); if (!p) return;
    if (rec.plan && rec.plan.dep === p.dep && rec.plan.arr === p.arr && rec.plan.pv === 2 && (rec.plan.segs || !p.segs)) return;
    if (rec.dep && p.dep && rec.dep !== p.dep && rec.tko) return;   /* le plan ne correspond pas à ce vol */
    rec.plan = p; rec.dep = p.dep || rec.dep; rec.arr = p.arr || rec.arr; rec.type = p.type || rec.type; rec.cs = p.cs || rec.cs; rec.free = false;
  }
  function finish(keep) {
    if (!rec) return;
    if (keep && rec.tko) {
      rec.t1 = rec.last || Date.now();
      if (!rec.arr && rec.lastPos) rec.arr = nearest(rec.lastPos[0], rec.lastPos[1]);
      var tr = rec.trk || []; while (tr.length > 700) tr = tr.filter(function (_, i) { return i % 2 === 0 || i === tr.length - 1; }); rec.trk = tr;
      var copy = JSON.parse(JSON.stringify(rec)); delete copy.lastPos; delete copy.lastT;
      if (bridge()) { try { window.chrome.webview.postMessage({ journalSave: copy }); } catch (e) {} }
      else { var h = ld(HKEY) || []; h.unshift(copy); sv(HKEY, h.slice(0, 40)); }
      lastSaved = copy;
    }
    rec = null; sv(KEY, null); prev = null;
    if (ui.open) setTimeout(function () { loadList(true); }, 600);
  }
  var lastSaved = null;
  function tick() {
    var u = window.alUser, f = window.alFlight || {}, P = window.alFlightPhase || 0, now = Date.now();
    if (rec && rec.last && now - rec.last > 3 * 3600000) finish(true);   /* vol abandonné (appli fermée…) */
    if (!u || !P) return;
    if (!rec) {
      if (P >= 11) return;   /* pas de vol à commencer au roulage d'arrivée */
      var pd = window.alPlanData, dep = '';
      if (pd && pd.origin && Number.isFinite(parseFloat(pd.origin.pos_lat)) && nm(u.lat, u.lon, parseFloat(pd.origin.pos_lat), parseFloat(pd.origin.pos_long)) < 15) dep = String(pd.origin.icao_code || '').toUpperCase();
      if (!dep && u.ground) dep = nearest(u.lat, u.lon);
      rec = { id: String(now), v: 2, t0: now, dep: dep, arr: '', type: '', cs: u.callsign || '', free: true, partial: !u.ground, g: {}, trk: [], dist: 0,
              fuel0: f.fuel_kg != null ? f.fuel_kg : null, fuelL: f.fuel_kg != null ? f.fuel_kg : null, maxAlt: 0, out: null, tko: null, ldg: null, inT: null };
      attachPlan();
    }
    attachPlan();
    var gi = grOf(P), dt = rec.last ? Math.min(10, (now - rec.last) / 1000) : 0;
    /* plein de carburant au sol avant le départ : on repart du nouveau niveau */
    if (f.fuel_kg != null) {
      if (rec.fuelL != null && f.fuel_kg > rec.fuelL + 5 && !rec.tko) rec.fuel0 = f.fuel_kg;
      var used = rec.fuelL != null ? rec.fuelL - f.fuel_kg : 0;
      if (gi >= 0) { var g0 = rec.g[gi] = rec.g[gi] || {}; if (used > 0 && used < 400) g0.fuel = (g0.fuel || 0) + used; if (g0.fuelS == null) g0.fuelS = f.fuel_kg; g0.fuelE = f.fuel_kg; }
      rec.fuelL = f.fuel_kg; if (rec.fuel0 == null) rec.fuel0 = f.fuel_kg;
    }
    if (gi >= 0) {
      var g = rec.g[gi] = rec.g[gi] || {};
      if (!g.t0) g.t0 = now; g.t1 = now; g.dur = (g.dur || 0) + dt;
      var gs = u.gs || 0, vs = f.vs, alt = f.ialt != null ? f.ialt : (u.alt || 0);   /* altitude de l'altimètre, comme sur le PFD */
      g.gsMax = Math.max(g.gsMax || 0, gs); g.gsSum = (g.gsSum || 0) + gs; g.n = (g.n || 0) + 1;
      if (vs != null) { g.vsMax = Math.max(g.vsMax == null ? -99999 : g.vsMax, vs); g.vsMin = Math.min(g.vsMin == null ? 99999 : g.vsMin, vs); g.vsSum = (g.vsSum || 0) + vs; }
      g.altMax = Math.max(g.altMax || 0, alt); g.altMin = Math.min(g.altMin == null ? 99999 : g.altMin, alt);
      if (f.ias != null) g.iasMax = Math.max(g.iasMax || 0, f.ias);
      rec.cur = gi;
    }
    if (P >= 3 && !rec.out) rec.out = now;
    if (P >= 13 && !rec.inT) rec.inT = now;
    var altI = f.ialt != null ? f.ialt : (u.alt || 0);
    rec.maxAlt = Math.max(rec.maxAlt || 0, altI);
    if (rec.lastPos) { var dd = nm(rec.lastPos[0], rec.lastPos[1], u.lat, u.lon); if (dd > 0.02 && dd < 60) rec.dist += dd; }
    /* envol et toucher */
    if (prev) {
      if (prev.ground && !u.ground && !rec.tko) rec.tko = { t: now, ias: f.ias != null ? f.ias : prev.ias, gs: Math.round(u.gs || 0) };
      if (!prev.ground && u.ground && rec.tko && P >= 9) rec.ldg = { t: now, vs: prev.vs != null ? Math.round(prev.vs) : null, ias: prev.ias, gs: Math.round(u.gs || 0), flaps: f.flaps != null ? f.flaps : prev.flaps };
    }
    /* trajectoire : un point toutes les 15 s, ou plus souvent quand l'altitude change vite */
    var tr = rec.trk, lp = tr[tr.length - 1], ts = Math.round((now - rec.t0) / 1000);
    if (!lp || ts - lp[4] >= 15 || Math.abs(altI - lp[2]) > 400 || (prev && prev.ground !== !!u.ground)) {
      tr.push([+u.lat.toFixed(4), +u.lon.toFixed(4), Math.round(altI), +rec.dist.toFixed(1), ts, P]);
      if (tr.length > 3000) rec.trk = tr.filter(function (_, i) { return i % 2 === 0 || i === tr.length - 1; });
    }
    rec.lastPos = [u.lat, u.lon]; rec.last = now;
    prev = { ground: !!u.ground, vs: f.vs, ias: f.ias, flaps: f.flaps };
    /* fin du vol : débarquement, ou un nouveau vol commence après l'atterrissage */
    if (P === 14 && rec.ldg) { sv(KEY, rec); finish(true); return; }
    if (P <= 2 && rec.ldg) { finish(true); return; }
    sv(KEY, rec);
    if (ui.open && ui.sel === 'cur') renderSoon();
  }
  window.addEventListener('al-tick', tick);
  window.addEventListener('resize', function () { if (ui.open) renderSoon(); });
  window.addEventListener('al-plan-clear', function () { finish(true); });

  /* ======================= page ======================= */
  var ui = { open: false, sel: 'cur', list: [], data: null, map: null, layers: null, rt: null };
  function fmtDur(s) { s = Math.round(s || 0); var h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); if (m === 60) { h++; m = 0; } return h ? h + ' h ' + String(m).padStart(2, '0') : m + ' min'; }
  function hm(t) { if (!t) return '—'; var d = new Date(t); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }
  function kg(v) { return v == null ? '—' : Math.round(v).toLocaleString() + ' kg'; }
  function ftx(v) { return v == null ? '—' : (v >= 18000 ? 'FL' + String(Math.round(v / 100)).padStart(3, '0') : Math.round(v).toLocaleString() + ' ft'); }
  function rate(vs) { var a = Math.abs(vs); return a < 120 ? 0 : a < 250 ? 1 : a < 400 ? 2 : a < 600 ? 3 : 4; }
  function build() {
    if (document.getElementById('hgJournal')) return;
    var d = document.createElement('div'); d.id = 'hgJournal';
    d.innerHTML = '<div class="jh"><button class="jb" id="hgJBack">← ' + T.menu + '</button><span class="jt">▤ ' + T.title + '</span>' +
      '<select class="jb" id="hgJSel"></select><span class="jgrow"></span><button class="jb" id="hgJDel">' + T.del + '</button><button class="jb jx" id="hgJClose">✕</button></div>' +
      '<div class="jm"><div class="jc jl" id="hgJLeft"></div><div class="jr"><div class="jc" id="hgJSum"></div><div class="jc jpf" id="hgJProf"></div><div class="jc" id="hgJMap"></div></div></div>';
    document.body.appendChild(d);
    document.getElementById('hgJBack').onclick = close; document.getElementById('hgJClose').onclick = close;
    document.getElementById('hgJSel').onchange = function () { ui.sel = this.value; show(); };
    document.getElementById('hgJDel').onclick = function () {
      if (ui.sel === 'cur' || !confirm(T.delQ)) return;
      if (bridge()) { try { window.chrome.webview.postMessage({ journalDelete: ui.sel }); } catch (e) {} }
      else sv(HKEY, (ld(HKEY) || []).filter(function (r) { return r.id !== ui.sel; }));
      ui.sel = 'cur'; setTimeout(function () { loadList(true); }, 400);
    };
  }
  function rail(k) { document.querySelectorAll('#hgRail .it').forEach(function (b) { b.classList.toggle('on', b.dataset.k === k); }); }   /* menu : la page affichée est allumée */
  function close() { var d = document.getElementById('hgJournal'); if (d) d.classList.remove('on'); ui.open = false; rail('dispatch'); }
  window.hgCloseAll = close;   /* menu repliable : « Plan & suivi de vol » revient à la page */
  window.hgOpenJournal = function () {
    build(); var d = document.getElementById('hgJournal'); d.classList.add('on'); ui.open = true; rail('journal');
    loadList(true);
  };
  function loadList(reshow) {
    var done = function (arr) {
      ui.list = arr || [];
      var s = document.getElementById('hgJSel'); if (!s) return;
      var o = '<option value="cur">● ' + T.live + (rec ? ' · ' + esc((rec.dep || '????') + ' → ' + (rec.arr || '????')) : '') + '</option>';
      ui.list.forEach(function (r) { var dt = new Date(r.t0); o += '<option value="' + esc(r.id) + '">' + dt.toLocaleDateString() + ' ' + hm(r.t0) + ' · ' + esc((r.dep || '????') + ' → ' + (r.arr || '????')) + (r.type ? ' · ' + esc(r.type) : '') + '</option>'; });
      s.innerHTML = o;
      if (!rec && ui.sel === 'cur' && ui.list.length) ui.sel = ui.list[0].id;
      s.value = ui.sel; if (s.value !== ui.sel) { ui.sel = 'cur'; s.value = 'cur'; }
      if (reshow) show();
    };
    if (bridge()) fetch('/journal-list', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(done).catch(function () { done([]); });
    else done((ld(HKEY) || []).map(function (r) { return { id: r.id, t0: r.t0, dep: r.dep, arr: r.arr, type: r.type }; }));
  }
  function show() {
    document.getElementById('hgJDel').style.display = ui.sel === 'cur' ? 'none' : '';
    if (ui.sel === 'cur') { ui.data = rec; render(); return; }
    var hit = (ld(HKEY) || []).filter(function (r) { return r.id === ui.sel; })[0];
    if (hit || !bridge()) { ui.data = hit || null; render(); return; }
    fetch('/journal-get?id=' + encodeURIComponent(ui.sel), { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (j) { ui.data = j; render(); }).catch(function () { ui.data = null; render(); });
  }
  /* vols enregistrés avant l'ajout du repoussage : on décale les phases */
  function v2(r) {
    if (!r || r.v === 2 || !r.g) return r;
    var c = JSON.parse(JSON.stringify(r)), g = {};
    Object.keys(r.g).forEach(function (k) { var i = +k; g[i === 0 ? 0 : i + 1] = r.g[k]; });
    c.g = g; if (c.cur != null && c.cur > 0) c.cur++; c.v = 2; return c;
  }
  var rsT = null; function renderSoon() { clearTimeout(rsT); rsT = setTimeout(render, 300); }
  function render() {
    var r = v2(ui.data), L = document.getElementById('hgJLeft'), S = document.getElementById('hgJSum'), Pf = document.getElementById('hgJProf');
    if (!L) return;
    if (!r) { L.innerHTML = '<div class="jempty">' + T.none + '</div>'; S.innerHTML = ''; Pf.innerHTML = ''; drawMap(null); return; }
    /* frise des phases */
    var h = '<div class="jk">' + (r.partial ? T.partial : '') + '</div>';
    T.groups.forEach(function (name, i) {
      var g = r.g && r.g[i], cls = !g ? 'wait' : (ui.sel === 'cur' && r.cur === i && !r.t1 ? 'now' : 'done');
      h += '<div class="jp ' + cls + '"><span class="b"></span><div class="n">' + esc(name) + (g ? ' <small>' + hm(g.t0) + ' · ' + fmtDur(g.dur) + '</small>' : ' <small>' + T.wait + '</small>') + '</div>';
      if (g) {
        var cells = [];
        if (g.fuelE != null) cells.push([T.fob, kg(g.fuelE) + (g.fuel >= 1 ? ' <small style="color:#8FA3B8;font-weight:600">−' + Math.round(g.fuel) + '</small>' : '')]);
        else if (g.fuel) cells.push([T.fuel, kg(g.fuel)]);
        if (i === 2 || i === 9) cells.push([T.gs + ' ' + T.max, Math.round(g.gsMax || 0) + ' kt']);   /* au sol : vitesse sol */
        if (i >= 3 && i <= 8 && g.iasMax) cells.push([T.iasMax, Math.round(g.iasMax) + ' kt']);   /* en l'air : vitesse indiquée, comme sur le PFD */
        if (i === 4 || i === 6 || i === 7) { var av = g.n ? Math.round(g.vsSum / g.n) : null; cells.push([T.vs + ' ' + T.avg, av == null ? '—' : (av > 0 ? '+' : '') + av + ' ft/min']); }
        if (i === 4 || i === 5) cells.push([T.alt, ftx(g.altMax)]);
        if (i === 3 && r.tko) cells.push([T.rot, (r.tko.ias != null ? r.tko.ias : r.tko.gs) + ' kt']);
        if (i === 8 && r.ldg) {
          if (r.ldg.vs != null) cells.push([T.td, '<span>' + r.ldg.vs + ' ft/min</span><span class="jrate r' + rate(r.ldg.vs) + '">' + T.rate[rate(r.ldg.vs)] + '</span>', 'w']);
          if (r.ldg.ias != null) cells.push([T.ias, r.ldg.ias + ' kt']);
          if (r.ldg.flaps != null) cells.push([T.flaps, String(r.ldg.flaps)]);
        }
        if (cells.length) h += '<div class="f">' + cells.map(function (c) { return '<div' + (c[2] ? ' class="' + c[2] + '"' : '') + '><i>' + c[0] + '</i><b>' + c[1] + '</b></div>'; }).join('') + '</div>';
      }
      h += '</div>';
    });
    L.innerHTML = h;
    /* résumé */
    var p = r.plan, end = r.t1 || r.last || Date.now();
    var block = r.out ? ((r.inT || end) - r.out) / 1000 : null, air = r.tko ? (((r.ldg && r.ldg.t) || end) - r.tko.t) / 1000 : null;
    var fuelT = r.fuel0 != null && r.fuelL != null ? r.fuel0 - r.fuelL : null;
    function cell(k, v, sub) { return '<div><i>' + k + '</i><b>' + v + '</b>' + (sub ? '<small>' + sub + '</small>' : '') + '</div>'; }
    S.innerHTML = '<div class="jrt"><span class="ic">' + esc(r.dep || '????') + '</span><span class="ar">✈ ⟶</span><span class="ic">' + esc(r.arr || '????') + '</span>' +
      '<span class="meta">' + [new Date(r.t0).toLocaleDateString(), r.type, r.cs, r.free ? T.free : ''].filter(Boolean).map(esc).join(' · ') + '</span></div>' +
      '<div class="js">' + cell(T.block, block == null ? '—' : fmtDur(block), p && p.block ? T.planned + ' ' + fmtDur(p.block * 60) : '') +
      cell(T.air, air == null ? '—' : fmtDur(air), p && p.air ? T.planned + ' ' + fmtDur(p.air * 60) : '') +
      cell(T.fob, kg(r.fuelL), [fuelT != null ? T.used + ' ' + kg(fuelT) : '', p && p.fuel ? T.planned + ' ' + kg(p.fuel) : ''].filter(Boolean).join(' · ')) +
      cell(T.dist, Math.round(r.dist || 0) + ' NM', p && p.dist ? T.planned + ' ' + p.dist + ' NM' : '') +
      cell(T.maxAlt, ftx(r.maxAlt), p && p.cruise ? T.planned + ' ' + ftx(p.cruise) : '') +
      cell(T.ldg, r.ldg && r.ldg.vs != null ? r.ldg.vs + ' ft/min' : '—', r.ldg && r.ldg.vs != null ? T.rate[rate(r.ldg.vs)] : '') + '</div>';
    /* profil du vol */
    Pf.innerHTML = '<div class="jk">' + T.profile + '</div><div class="lg"><span>' + T.realProf + '</span>' + (p ? '<span class="p">' + T.planProf + '</span>' : '<em>' + T.noPlan + '</em>') + '</div>' + profSvg(r, Pf.clientWidth - 24, Pf.clientHeight - 52);
    drawMap(r);
  }
  function profSvg(r, W, H) {
    W = Math.max(300, Math.round(W || 1000)); H = Math.max(120, Math.round(H || 190)); var ml = 46, mr = 12, mt = 10, mb = 22, p = r.plan, tr = r.trk || [];
    var xMax = Math.max(p && p.dist || 0, r.dist || 0, 10), yMax = 1000;
    tr.forEach(function (q) { yMax = Math.max(yMax, q[2]); }); if (p) p.prof.forEach(function (q) { yMax = Math.max(yMax, q[1]); });
    var st = [1000, 2000, 5000, 10000].filter(function (v) { return yMax * 1.1 / v <= 5; })[0] || 10000; yMax = Math.ceil(yMax * 1.1 / st) * st;
    var X = function (v) { return ml + (W - ml - mr) * v / xMax; }, Y = function (v) { return mt + (H - mt - mb) * (1 - v / yMax); };
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '">';
    for (var a = 0; a <= yMax; a += st) s += '<line x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(a) + '" y2="' + Y(a) + '" stroke="rgba(148,163,184,.12)"/><text x="' + (ml - 6) + '" y="' + (Y(a) + 3) + '" text-anchor="end" font-size="10" fill="#7F93A8">' + (a >= 18000 ? 'FL' + Math.round(a / 100) : Math.round(a / 1000) + 'k') + '</text>';
    var step = xMax > 1500 ? 500 : xMax > 600 ? 200 : xMax > 200 ? 50 : 20;
    for (var x = 0; x <= xMax; x += step) s += '<text x="' + X(x) + '" y="' + (H - 6) + '" text-anchor="middle" font-size="10" fill="#7F93A8">' + x + '</text>';
    if (p && p.prof.length > 1) {
      s += '<polyline fill="none" stroke="#94A3B8" stroke-width="1.6" stroke-dasharray="6 5" points="' + p.prof.map(function (q) { return X(q[0]).toFixed(1) + ',' + Y(q[1]).toFixed(1); }).join(' ') + '"/>';
      [['TOC', p.toc], ['TOD', p.tod]].forEach(function (m) {
        if (m[1] == null) return;
        s += '<line x1="' + X(m[1]) + '" x2="' + X(m[1]) + '" y1="' + mt + '" y2="' + (H - mb) + '" stroke="rgba(125,211,252,.35)" stroke-dasharray="3 4"/>' +
             '<text x="' + X(m[1]) + '" y="' + (mt + 10) + '" text-anchor="middle" font-size="10.5" font-weight="800" fill="#7DD3FC">' + m[0] + '</text>';
      });
    }
    if (tr.length > 1) {
      var COL = { 1: '#64748B', 2: '#64748B', 3: '#94A3B8', 4: '#94A3B8', 5: '#F59E0B', 6: '#38BDF8', 7: '#22C55E', 8: '#A78BFA', 9: '#F472B6', 10: '#F472B6', 11: '#F59E0B', 12: '#94A3B8', 13: '#64748B', 14: '#64748B' };
      for (var i = 1; i < tr.length; i++) {
        var a0 = tr[i - 1], a1 = tr[i];
        s += '<line x1="' + X(a0[3]).toFixed(1) + '" y1="' + Y(a0[2]).toFixed(1) + '" x2="' + X(a1[3]).toFixed(1) + '" y2="' + Y(a1[2]).toFixed(1) + '" stroke="' + (COL[a1[5]] || '#38BDF8') + '" stroke-width="2.6" stroke-linecap="round"/>';
      }
      var lt = tr[tr.length - 1];
      if (!r.t1) {   /* petit avion au bout du profil, incliné selon la montée ou la descente */
        var pv = tr[Math.max(0, tr.length - 4)], ang = Math.atan2(Y(lt[2]) - Y(pv[2]), Math.max(1, X(lt[3]) - X(pv[3]))) * 180 / Math.PI;
        s += '<g transform="translate(' + X(lt[3]).toFixed(1) + ',' + Y(lt[2]).toFixed(1) + ') rotate(' + (90 + ang).toFixed(0) + ') translate(-11,-11)"><path fill="#F59E0B" stroke="#0B121A" stroke-width="1" transform="scale(0.92)" d="' + PLANE_D + '"/></g>';
      }
    }
    return s + '</svg>';
  }
  function drawMap(r) {
    var el = document.getElementById('hgJMap'); if (!el || typeof L === 'undefined' || !L.map) return;
    if (!ui.map) {
      ui.map = L.map(el, { zoomControl: true, attributionControl: false, worldCopyJump: true }).setView([46.5, 2.5], 5);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, className: 'hg-jdark' }).addTo(ui.map);
      ui.layers = L.layerGroup().addTo(ui.map);
    }
    setTimeout(function () { try { ui.map.invalidateSize(); } catch (e) {} }, 60);
    ui.layers.clearLayers(); if (!r) return;
    var b = [];
    var COLS = { sid: '#4ADE80', route: '#FF4DDB', star: '#FB923C' };
    try { if (typeof SB_COLORS !== 'undefined') COLS = SB_COLORS; } catch (e) {}
    if (r.plan && r.plan.segs && r.plan.segs.s && r.plan.segs.s.length) {
      r.plan.segs.s.forEach(function (sg) { L.polyline(sg.pts, { color: COLS[sg.k] || '#FF4DDB', weight: sg.k === 'route' ? 3 : 4, opacity: .95 }).addTo(ui.layers); b = b.concat(sg.pts); });
      (r.plan.segs.f || []).forEach(function (f) { L.circleMarker([f[0], f[1]], { radius: 3, color: '#000', weight: 1, fillColor: '#E6EDF5', fillOpacity: 1 }).bindTooltip(String(f[2]), { direction: 'top' }).addTo(ui.layers); });
    } else if (r.plan && r.plan.route && r.plan.route.length > 1) { L.polyline(r.plan.route, { color: '#94A3B8', weight: 2, dashArray: '6 6', opacity: .9 }).addTo(ui.layers); b = b.concat(r.plan.route); }
    var tr = (r.trk || []).map(function (q) { return [q[0], q[1]]; });
    if (tr.length > 1) { L.polyline(tr, { color: '#38BDF8', weight: 3.5, opacity: .95 }).addTo(ui.layers); b = b.concat(tr); }
    function apt(code, ll) { if (!ll) return; L.circleMarker(ll, { radius: 6, color: '#06121C', weight: 2, fillColor: '#38BDF8', fillOpacity: 1 }).bindTooltip(code, { permanent: true, direction: 'right', className: 'hg-apt-tip' }).addTo(ui.layers); }
    if (r.plan && r.plan.route) { apt(r.plan.dep, r.plan.route[0]); apt(r.plan.arr, r.plan.route[r.plan.route.length - 1]); }
    else if (tr.length) { apt(r.dep || '', tr[0]); if (r.t1) apt(r.arr || '', tr[tr.length - 1]); }
    if (!r.t1 && tr.length) {   /* ton avion, orienté selon son cap */
      var u = window.alUser, pos = tr[tr.length - 1], hd = 0;
      if (ui.sel === 'cur' && u && u.lat != null) { pos = [u.lat, u.lon]; hd = u.hdg || 0; }
      else if (tr.length > 1) { var a = tr[tr.length - 2], c = tr[tr.length - 1]; hd = (Math.atan2((c[1] - a[1]) * Math.cos(c[0] * Math.PI / 180), c[0] - a[0]) * 180 / Math.PI + 360) % 360; }
      L.marker(pos, { interactive: false, zIndexOffset: 1000, icon: L.divIcon({ className: 'hg-jplane', iconSize: [30, 30], iconAnchor: [15, 15],
        html: '<svg width="30" height="30" viewBox="0 0 24 24" style="transform:rotate(' + Math.round(hd) + 'deg)"><path fill="#F59E0B" stroke="#0B121A" stroke-width="1" d="' + PLANE_D + '"/></svg>' }) }).addTo(ui.layers);
    }
    if (b.length > 1 && ui.fitId !== r.id) { ui.fitId = r.id; try { ui.map.fitBounds(L.latLngBounds(b).pad(0.15)); } catch (e) {} }   /* recadre une fois par vol, pas à chaque mise à jour */
  }
  /* bouton dans la barre de la carte de suivi, ouverture depuis l'appli */
  setInterval(function () {
    if (document.getElementById('hgJBtn')) return;
    var close = document.getElementById('alFoldAll'); if (!close) return;
    var b = document.createElement('button'); b.id = 'hgJBtn'; b.type = 'button'; b.className = 'hg-act'; b.innerHTML = '▤ ' + T.open; b.onclick = window.hgOpenJournal;
    close.parentNode.insertBefore(b, close);
  }, 1000);
  try { if (bridge()) window.chrome.webview.addEventListener('message', function (e) { var d = e.data; if (d && d.open === 'journal') window.hgOpenJournal(); }); } catch (e) {}
  function startUp() { if (location.hash === '#journal') setTimeout(window.hgOpenJournal, 800); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', startUp); else startUp();
})();
</script>"""
JRN_ANCHORS = [
 ('      i(\'ALTITUDE\', fmt(u.alt) + \' <span class="u">ft</span>\') +',
  '      i(\'ALTITUDE\', fmt(f && f.ialt != null ? f.ialt : u.alt) + \' <span class="u">ft</span>\') +   /* 12.7 : altimètre */'),

 ("        if (P === 5 && !st.off) { /* roulage au décollage pas encore en l'air */ if (gs < 30) P = 4; }",
  "        if (P === 5 && !st.off) { /* roulage au décollage pas encore en l'air */ if (gs < 40) P = 4; }"),
 ('        if (gs >= 30) { st.out = st.out || now; P = 5; }',
  '        if (gs >= 50) { st.out = st.out || now; P = 5; }   /* 12.7 : 50 kt = course au décollage, pas un roulage rapide */'),

 ("      window.alFlightPhase = live.user ? (st.phase || 0) : 0; window.alUser = live.user;",
  "      window.alFlightPhase = live.user ? (st.phase || 0) : 0; window.alUser = live.user; window.alFlight = live.flight;\n"
  "      try { window.dispatchEvent(new Event('al-tick')); } catch (e) {}   /* 12.7 : journal de vol */"),
 ("        plan = p;\n        window.alPlanData =", "        plan = p; window.alPlanFull = data;   /* 12.7 : plan complet pour le journal de vol */\n        window.alPlanData ="),
]


def patch_jrn127(path, lang):
    s = open(path, encoding="utf-8").read()
    if "hangar-127-jrn" in s:
        return
    import json
    for a, b in JRN_ANCHORS:
        assert s.count(a) == 1, (path, a[:50])
        s = s.replace(a, b)
    s = s.replace("</head>", JRN_CSS + "</head>", 1)
    s = s.replace("</body>", JRN_JS.replace("__TXT__", json.dumps(JRN_TXT[lang], ensure_ascii=False)) + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_jrn127(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.7 : plan SimBrief + piste et vent + météo dans un seul encadré ; la légende se replie quand il s'ouvre ----
MRG_TXT = {"fr": {"title": "Mon vol · plan, piste et météo"}, "en": {"title": "My flight · plan, runway and weather"}}
MRG_CSS = r"""<style id="hangar-127-mrg">
#hgMetIn{margin-top:10px;padding-top:10px;border-top:1px solid rgba(125,211,252,.18)}
#hgMetIn .hm:last-of-type{margin-bottom:4px}
html body #sbInfo:not(.al-col){max-height:calc(100% - 80px)!important;overflow:auto!important}
</style>"""
MRG_JS = r"""<script id="hangar-127-mrg-js">
(function () {
  var T = __TXT__, obs = null;
  function visible(el) { return el && !el.classList.contains('hidden') && el.style.display !== 'none' && el.offsetParent !== null; }
  function foldLegend() {
    var lg = document.getElementById('alMainLegend');
    if (lg && !lg.classList.contains('al-col')) { lg.classList.add('al-col'); try { localStorage.setItem('al_fold_alMainLegend', '1'); } catch (e) {} }
  }
  function mirror(src, dst) { if (dst.innerHTML !== src.innerHTML) dst.innerHTML = src.innerHTML; }
  function step() {
    var sb = document.getElementById('sbInfo'), mt = document.getElementById('trafficMetarBox'), body = document.getElementById('tmBody');
    if (!sb || !mt || !body) return;
    var plan = !sb.classList.contains('hidden') && sb.innerHTML.trim() !== '';
    var box = document.getElementById('hgMetIn');
    if (plan) {
      if (sb.getAttribute('data-al-t') !== T.title) sb.setAttribute('data-al-t', T.title);
      if (!box || box.parentNode !== sb) { if (box) box.remove(); box = document.createElement('div'); box.id = 'hgMetIn'; sb.appendChild(box); }
      else if (box !== sb.lastElementChild) sb.appendChild(box);   /* toujours en dernier, après piste et vent */
      mirror(body, box);
      if (!obs) { obs = new MutationObserver(function () { var b = document.getElementById('hgMetIn'); if (b) mirror(body, b); }); obs.observe(body, { childList: true, subtree: true, characterData: true }); }
      if (mt.style.display !== 'none') { mt.dataset.hgHid = '1'; mt.style.display = 'none'; }
    } else {
      if (box) box.remove();
      if (mt.dataset.hgHid) { delete mt.dataset.hgHid; mt.style.display = ''; }
    }
    /* un encadré du vol ouvert = la légende se replie */
    var open = (plan && !sb.classList.contains('al-col')) || (!plan && visible(mt) && !mt.classList.contains('al-col'));
    if (open && !step.wasOpen) foldLegend();
    step.wasOpen = open;
  }
  setInterval(step, 700);
})();
</script>"""


def patch_mrg127(path, lang):
    s = open(path, encoding="utf-8").read()
    if "hangar-127-mrg" in s:
        return
    import json
    s = s.replace("</head>", MRG_CSS + "</head>", 1)
    s = s.replace("</body>", MRG_JS.replace("__TXT__", json.dumps(MRG_TXT[lang], ensure_ascii=False)) + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_mrg127(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.7 : altitude de croisière conseillée (distance, avion, sens du vol) ----
ALT_TXT = {
 "fr": {"adv": "Conseillé", "apply": "Appliquer", "why": "{d} NM · cap {c}° ({side}) · plafond {ac} {fl}", "east": "vers l'est : niveau impair", "west": "vers l'ouest : niveau pair",
        "vfr": "En VFR, vole à {a} ft (+500 ft)", "short": "vol court : croisière basse"},
 "en": {"adv": "Advised", "apply": "Apply", "why": "{d} NM · track {c}° ({side}) · {ac} ceiling {fl}", "east": "eastbound: odd level", "west": "westbound: even level",
        "vfr": "In VFR, fly at {a} ft (+500 ft)", "short": "short flight: low cruise"},
}
ALT_CSS = r"""<style id="hangar-127-alt">
.hg-adv{display:inline-flex;align-items:center;gap:6px;margin-left:6px;padding:3px 4px 3px 9px;border:1px solid rgba(34,197,94,.45);border-radius:999px;background:rgba(34,197,94,.10);
  font:700 10.5px "Segoe UI",Inter,sans-serif;color:#86EFAC;white-space:nowrap;cursor:help}
.hg-adv b{color:#FFFFFF;font-weight:800}
.hg-adv button{border:0;border-radius:999px;background:#22C55E;color:#04210F;font:800 10px "Segoe UI",Inter,sans-serif;padding:3px 9px;cursor:pointer}
.hg-adv button:hover{background:#4ADE80}
.hg-adv.same{border-color:rgba(148,163,184,.3);background:transparent;color:#8FA3B8}.hg-adv.same button{display:none}
.hg-adv-fms{display:flex;margin:6px 0 0}
</style>"""
ALT_JS = r"""<script id="hangar-127-alt-js">
(function () {
  var T = __TXT__;
  var FAC = { heavy: 100, jet: 100, turboprop: 75, prop: 55 }, MIN = { heavy: 10000, jet: 8000, turboprop: 6000, prop: 3000 };
  function nm(a, b, c, d) { var r = Math.PI / 180, x = Math.sin((c - a) * r / 2), y = Math.sin((d - b) * r / 2);
    var h = x * x + Math.cos(a * r) * Math.cos(c * r) * y * y; return 3440.065 * 2 * Math.asin(Math.min(1, Math.sqrt(h))); }
  function brg(a, b, c, d) { var r = Math.PI / 180, y = Math.sin((d - b) * r) * Math.cos(c * r), x = Math.cos(a * r) * Math.sin(c * r) - Math.sin(a * r) * Math.cos(c * r) * Math.cos((d - b) * r);
    return (Math.atan2(y, x) / r + 360) % 360; }
  function flTxt(a) { return a >= 18000 ? 'FL' + String(Math.round(a / 100)).padStart(3, '0') : a.toLocaleString() + ' ft'; }
  /* calcul : distance × facteur de l'avion, sans dépasser son plafond, puis niveau pair/impair selon le sens (règle semi-circulaire) */
  window.hgAdvisedAlt = function (dep, arr, ac) {
    if (!dep || !arr || !Number.isFinite(+dep.lat) || !Number.isFinite(+arr.lat)) return null;
    var d = nm(+dep.lat, +dep.lon, +arr.lat, +arr.lon), c = brg(+dep.lat, +dep.lon, +arr.lat, +arr.lon);
    var cat = FAC[ac.cat] ? ac.cat : 'jet', ceil = parseInt(String(ac.fl || '').replace(/[^0-9]/g, ''), 10) * 100 || (cat === 'prop' ? 12000 : 37000);
    var alt = Math.max(MIN[cat], Math.min(ceil, d * FAC[cat]));
    var k = Math.floor(alt / 1000), east = c < 180;
    if ((k % 2 === 1) !== east) k -= 1;                    /* vers l'est : impair ; vers l'ouest : pair */
    if (k * 1000 > ceil) k -= 2;
    if (k * 1000 < Math.min(MIN[cat], ceil)) k += 2;
    if (k < 1) k = east ? 1 : 2;
    return { alt: k * 1000, d: Math.round(d), c: Math.round(c), east: east, ceil: ceil, short: d * FAC[cat] < MIN[cat] };
  };
  function acNow() {
    var s = document.getElementById('aircraftSelect'); if (!s || !s.value) return null;
    return { code: s.value, fl: s.getAttribute('data-fl'), cat: s.getAttribute('data-cat') };
  }
  function vfr() { try { return flightType === 'VFR'; } catch (e) { return false; } }
  function cur() { try { return selectedCruiseAltitudeFt; } catch (e) { return null; } }
  function pill(id, anchor, after) {
    var p = document.getElementById(id);
    if (!p) { if (!anchor) return null; p = document.createElement('span'); p.id = id; p.className = 'hg-adv'; after ? anchor.parentNode.insertBefore(p, anchor.nextSibling) : anchor.appendChild(p); }
    return p;
  }
  function paint(p, r, ac) {
    if (!p) return;
    if (!r || !ac) { p.style.display = 'none'; return; }
    p.style.display = '';
    var key = r.alt + '|' + r.d + '|' + ac.code + '|' + vfr() + '|' + (cur() === r.alt);
    if (p.dataset.k === key) return; p.dataset.k = key;
    var why = T.why.replace('{d}', r.d).replace('{c}', String(r.c).padStart(3, '0')).replace('{side}', r.east ? T.east : T.west).replace('{ac}', ac.code).replace('{fl}', flTxt(r.ceil)) +
              (r.short ? ' · ' + T.short : '') + (vfr() ? '\n' + T.vfr.replace('{a}', (r.alt + 500).toLocaleString()) : '');
    p.title = why;
    p.classList.toggle('same', cur() === r.alt);
    p.innerHTML = '✓ ' + T.adv + ' <b>' + flTxt(r.alt) + (vfr() ? ' (+500)' : '') + '</b><button type="button">' + T.apply + '</button>';
    p.querySelector('button').onclick = function (e) { e.stopPropagation(); try { setCruiseAltitude(String(r.alt), 'map'); } catch (x) {} p.dataset.k = ''; };
  }
  setInterval(function () {
    var ac = acNow(), dep = null, arr = null;
    try { dep = interactiveDep || currentDep; arr = interactiveArr || currentArr; } catch (e) {}
    var r = ac ? window.hgAdvisedAlt(dep, arr, ac) : null;
    var mapSel = document.getElementById('mapCruiseAltitudeSelect');
    paint(pill('hgAdvMap', mapSel ? mapSel.parentNode : null, true), r, ac);
    var fms = document.getElementById('cruiseAltitudeSelect');
    var pf = document.getElementById('hgAdvFms');
    if (!pf && fms) { pf = document.createElement('span'); pf.id = 'hgAdvFms'; pf.className = 'hg-adv hg-adv-fms'; fms.parentNode.appendChild(pf); }
    var r2 = null; try { r2 = ac ? window.hgAdvisedAlt(currentDep, currentArr, ac) : null; } catch (e) {}
    paint(pf, r2, ac);
  }, 800);
})();
</script>"""


def patch_alt127(path, lang):
    s = open(path, encoding="utf-8").read()
    if "hangar-127-alt" in s:
        return
    import json
    s = s.replace("</head>", ALT_CSS + "</head>", 1)
    s = s.replace("</body>", ALT_JS.replace("__TXT__", json.dumps(ALT_TXT[lang], ensure_ascii=False)) + "</body>", 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_alt127(os.path.join(_web, "dispatch_%s.html" % _l), _l)


# ---- 12.7 : SEL TEMP / FLEX bien visible au décollage ----
SELT = {
 "fr": ("    var thr = t.flex && /D-?TO|FLEX|ATM|DERATE|TO-?\\d/i.test(t.thrust) ? ' · poussée réduite <span class=\"alp-m\">(' + t.flex + ' °C)</span>' : (t.thrust ? ' · ' + esc(t.thrust) : '');",
        "    var acc = String(((window.alPlanData || {}).aircraft || {}).icaocode || '').toUpperCase(), tl = /^B/.test(acc) ? 'SEL TEMP' : (/^A/.test(acc) ? 'FLEX' : 'temp. supposée');   /* 12.7 */\n"
        "    var thr = t.flex && /D-?TO|FLEX|ATM|DERATE|TO-?\\d/i.test(t.thrust) ? ' · poussée réduite ' + esc(t.thrust) + ' · <b class=\"alp-y\">' + tl + ' ' + t.flex + ' °C</b>' : (t.thrust ? ' · ' + esc(t.thrust) : '');"),
 "en": ("    var thr = t.flex && /D-?TO|FLEX|ATM|DERATE|TO-?\\d/i.test(t.thrust) ? ' · reduced thrust <span class=\"alp-m\">(' + t.flex + ' °C)</span>' : (t.thrust ? ' · ' + esc(t.thrust) : '');",
        "    var acc = String(((window.alPlanData || {}).aircraft || {}).icaocode || '').toUpperCase(), tl = /^B/.test(acc) ? 'SEL TEMP' : (/^A/.test(acc) ? 'FLEX' : 'assumed temp');   /* 12.7 */\n"
        "    var thr = t.flex && /D-?TO|FLEX|ATM|DERATE|TO-?\\d/i.test(t.thrust) ? ' · reduced thrust ' + esc(t.thrust) + ' · <b class=\"alp-y\">' + tl + ' ' + t.flex + ' °C</b>' : (t.thrust ? ' · ' + esc(t.thrust) : '');"),
}


def patch_selt127(path, lang):
    s = open(path, encoding="utf-8").read()
    a, b = SELT[lang]
    if b in s:
        return
    assert s.count(a) == 1, path
    open(path, "w", encoding="utf-8").write(s.replace(a, b))


if __name__ == "__main__":
    _web = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "web")
    for _l in ("fr", "en"):
        patch_selt127(os.path.join(_web, "dispatch_%s.html" % _l), _l)
