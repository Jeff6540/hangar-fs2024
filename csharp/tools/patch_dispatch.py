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
  function place(box, items, skip) {   /* range les éléments dans l'ordre voulu, sans rien toucher si c'est déjà bon */
    items = items.filter(Boolean);
    var cur = Array.prototype.slice.call(box.children).slice(skip || 0);
    var same = cur.length >= items.length && items.every(function (x, i) { return cur[i] === x; });
    if (!same) items.forEach(function (x) { box.appendChild(x); });
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
    place(r1, [menu, title, gVa, status, grow, document.getElementById('alFoldAll'), close]);
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
@keyframes hgIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
html body #trafficMapWrapper .al-fold:not(.al-col)>*{animation:hgIn .22s ease both}
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
