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
        ' &nbsp; <span class="d" style="background:#c084fc"></span>' + T.l3 + '</div><div><b style="color:#38BDF8">▲</b> ' + T.dep + ' &nbsp; <b style="color:#F5A524">■</b> ' + T.arr +
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
