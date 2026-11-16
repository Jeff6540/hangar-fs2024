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
  var SRC = { vatsim: { label: 'VATSIM', color: '#22c55e', cb: '#56B4E9', leg: T.leg_v },
              ivao:   { label: 'IVAO',   color: '#e11d48', cb: '#D55E00', leg: T.leg_i } };
  var st = {};
  Object.keys(SRC).forEach(function (k) {
    var on = false; try { on = localStorage.getItem('al_net_' + k) === '1'; } catch (e) {}
    st[k] = { on: on, data: null, err: '', mk: {}, layer: null, btn: null, t: 0 };
  });
  window.alNetOn = function () { return st.vatsim.on || st.ivao.on; };
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
    var svg = p.ground ? k2.planeSvg(size, p.hdg, '#8a93a3', color(k), 1.4, p.aircraft) : k2.planeSvg(size, p.hdg, color(k), '#fff', 1.1, p.aircraft);
    var html = (m && m.getZoom() >= 7) ? '<div class="alfs-pin">' + svg + '<span class="lb">' + k2.esc(SRC[k].label + ' · ' + p.callsign + (p.aircraft ? ' · ' + p.aircraft : '')) + '</span></div>' : svg;
    return L.divIcon({ className: 'alfs-icon', html: html, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
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
    var keep = k2.radFilter(), ground = k2.showGround(), seen = {}, n = 0, zoomSig = m.getZoom() >= 7 ? 'z' : '';
    (s.data.pilots || []).forEach(function (p) {
      if (p.ground && !ground) return;
      var ll = pos(p, s.t);
      if (keep && !keep(ll[0], ll[1])) return;
      if (isMe(p, ll)) return;
      seen[p.id] = 1; n++;
      var mk = s.mk[p.id], sig = p.hdg + '|' + p.ground + '|' + zoomSig + '|' + window.alColorblind;
      if (!mk) {
        mk = L.marker(ll, { icon: icon(k, p), keyboard: false, zIndexOffset: 400 }).addTo(s.layer);
        mk.bindTooltip(tip(k, p), { direction: 'top', offset: [0, -10] });
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
        return '<div class="alsh"><svg viewBox="0 0 24 24" width="14" height="14" style="display:inline-block;flex:none;width:14px;height:14px"><g fill="' + color(k) +
          '" stroke="#fff" stroke-width="1.3">' + '<path d="M12 2l1.6 6.5L21 13v1.8l-7.4-2.3-.5 5.6 2.4 1.8V21L12 20l-3.5 1v-1.1l2.4-1.8-.5-5.6L3 14.8V13l7.4-4.5z"/>' +
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
  css.textContent = '#leafletTrafficMap .leaflet-marker-icon.al-smooth{transition:transform 1s linear}' +
    '#leafletTrafficMap.al-nosmooth .leaflet-marker-icon,#leafletTrafficMap.leaflet-zoom-anim .leaflet-marker-icon{transition:none!important}' +
    '.alnet-btn{border-radius:999px!important;padding-left:12px!important;padding-right:12px!important;margin-left:6px;background:rgba(15,20,30,.66)!important;' +
    'color:var(--c)!important;border:1px solid var(--c)!important}' +
    '.alnet-btn.on{background:var(--c)!important;color:#fff!important;box-shadow:inset 0 0 0 1px #fff!important;border:0!important}';
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
