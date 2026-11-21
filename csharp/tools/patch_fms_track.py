# -*- coding: utf-8 -*-
"""FMS : la carte du Suivi de vol affiche la route du FMS, les altitudes prévues, T/C, T/D et un cadre « prochain changement d'altitude »."""
import os, json
here = os.path.dirname(os.path.abspath(__file__))
TXT = {
 "fr": {"title": "FMS", "next": "Prochain point", "alt": "Altitude", "climb": "Montée vers {a} ft", "path": "Descente VPATH vers {a} ft à {p}",
        "tod": "T/D dans {d} NM → {a} ft à {p}", "todPlan": "T/D prévu à {d} NM de {p} → {a} ft", "cruise": "Croisière {a} ft", "none": "Pas de plan dans le FMS",
        "ils": "ILS", "tc": "T/C (estimé)", "td": "T/D", "lvl": "palier", "fold": "Réduire", "unfold": "FMS", "nm": "NM", "ft": "ft", "vnavOff": "VNAV non engagé"},
 "en": {"title": "FMS", "next": "Next fix", "alt": "Altitude", "climb": "Climb to {a} ft", "path": "VPATH descent to {a} ft at {p}",
        "tod": "T/D in {d} NM → {a} ft at {p}", "todPlan": "T/D planned {d} NM before {p} → {a} ft", "cruise": "Cruise {a} ft", "none": "No plan in the FMS",
        "ils": "ILS", "tc": "T/C (estimated)", "td": "T/D", "lvl": "level", "fold": "Collapse", "unfold": "FMS", "nm": "NM", "ft": "ft", "vnavOff": "VNAV not engaged"},
}
JS = r"""<script id="hangar-fms-track">
/* FMS : route du FMS sur la carte du Suivi de vol (points avec altitude prévue, tronçon actif, T/C, T/D) et cadre « FMS » rétractable */
(function () {
  var T = __TXT__, layer = null, box = null, lastRev = -1, ap = null, folded = false;
  try { folded = localStorage.getItem('hg_fms_track_fold') === '1'; } catch (e) {}
  function map() { try { return typeof trafficMap !== 'undefined' ? trafficMap : null; } catch (e) { return null; } }
  function open() { var m = document.getElementById('trafficMapModal'); return m && !m.classList.contains('hidden'); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function f(k, v) { var s = T[k] || k; Object.keys(v || {}).forEach(function (x) { s = s.replace('{' + x + '}', v[x]); }); return s; }
  var R = Math.PI / 180;
  function nm(a, b) { var dLa = (b.lat - a.lat) * R, dLo = (b.lon - a.lon) * R, h = Math.sin(dLa / 2) * Math.sin(dLa / 2) + Math.cos(a.lat * R) * Math.cos(b.lat * R) * Math.sin(dLo / 2) * Math.sin(dLo / 2); return 3440.065 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h)); }
  function along(route, s) {   // point de la route à s NM du départ
    var c = 0;
    for (var i = 1; i < route.length; i++) { var d = nm(route[i - 1], route[i]); if (c + d >= s) { var k = d ? (s - c) / d : 0; return { lat: route[i - 1].lat + (route[i].lat - route[i - 1].lat) * k, lon: route[i - 1].lon + (route[i].lon - route[i - 1].lon) * k, leg: i }; } c += d; }
    return null;
  }
  // T/D prévu (même calcul que le VNAV du FMS) et T/C estimé (montée ≈ 250 ft par NM)
  function profile(p) {
    var r = p.route || [], cum = [0], i; if (r.length < 2) return {};
    for (i = 1; i < r.length; i++) cum[i] = cum[i - 1] + nm(r[i - 1], r[i]);
    var top = 0; for (i = 1; i < r.length - 1; i++) if ((r[i].alt || 0) > top) top = r[i].alt;
    var cruise = Math.max(p.cruiseAlt || 0, top), out = { cum: cum, cruise: cruise };
    var peak = 0; for (i = 1; i < r.length - 1; i++) if ((r[i].alt || 0) >= cruise - 300) peak = i;   // dernier point à la croisière (aucun : le départ)
    if (cruise <= 0) return out;
    var best = null;
    for (i = Math.max(1, peak); i < r.length; i++) {
      var a = r[i].alt || 0, d = cum[i], dest = i === r.length - 1;
      if (dest) { if (!(r[i].elev === true || (r[i].alt > 0 && r[i].elev !== false))) continue; a += 1500; d = Math.max(0, d - 5); }
      if (a <= 0 || a >= cruise - 300) continue;
      var s = d - (cruise - a) / 318.4; if (!best || s < best.s) best = { s: Math.max(s, cum[peak]), alt: a, to: r[i].ident, toS: d };
    }
    if (best) { out.td = best; out.tdPt = along(r, best.s); }
    var elev = r[0].alt || 0, tcS = (cruise - elev) / 250;
    if (tcS > 0 && (!best || tcS < best.s)) { out.tc = { s: tcS }; out.tcPt = along(r, tcS); }
    return out;
  }
  function draw(st) {
    var m = map(); if (!m || !window.L) return;
    if (!layer) layer = L.layerGroup().addTo(m);
    layer.clearLayers();
    var p = (st && st.plan) || {}, r = (p.route || []).filter(function (w) { return isFinite(w.lat) && isFinite(w.lon) && !(w.lat === 0 && w.lon === 0); });
    if (r.length < 2) return;
    var act = Math.max(1, Math.min(r.length - 1, p.activeLeg || 1));
    for (var i = 1; i < r.length; i++) {
      var done = i < act, on = i === act;
      L.polyline([[r[i - 1].lat, r[i - 1].lon], [r[i].lat, r[i].lon]], { color: '#1e1b4b', weight: 7, opacity: .4, interactive: false }).addTo(layer);
      L.polyline([[r[i - 1].lat, r[i - 1].lon], [r[i].lat, r[i].lon]], { color: done ? '#9ca3af' : '#e05bd8', weight: on ? 5 : 3, opacity: done ? .6 : 1, dashArray: r[i].ap ? '8 6' : null, interactive: false }).addTo(layer);
    }
    r.forEach(function (w, i) {
      var lbl = '<b>' + esc(w.ident) + '</b>' + (w.alt ? ' · ' + Math.round(w.alt) + ' ' + T.ft : '');
      L.circleMarker([w.lat, w.lon], { radius: i === act ? 6 : 4, color: '#000', weight: 1, fillColor: i === act ? '#e05bd8' : i < act ? '#9ca3af' : '#ffffff', fillOpacity: 1 })
        .bindTooltip(lbl, { permanent: true, direction: 'right', offset: [6, 0], className: 'hg-fms-lab' }).addTo(layer);
    });
    var pr = profile(p);
    [['tcPt', T.tc, '#38bdf8', '▲'], ['tdPt', T.td, '#f2c46b', '▼']].forEach(function (k) {
      var pt = pr[k[0]]; if (!pt) return;
      var sub = k[0] === 'tdPt' && pr.td ? ' → ' + Math.round(pr.td.alt) + ' ' + T.ft + ' (' + esc(pr.td.to) + ')' : ' → ' + Math.round(pr.cruise) + ' ' + T.ft;
      L.marker([pt.lat, pt.lon], { interactive: false, icon: L.divIcon({ className: 'hg-fms-pin', html: '<span style="color:' + k[2] + '">' + k[3] + '</span>', iconSize: [16, 16], iconAnchor: [8, 8] }) })
        .bindTooltip('<b>' + k[1] + '</b>' + sub, { permanent: true, direction: 'left', offset: [-8, 0], className: 'hg-fms-lab hg-fms-' + (k[0] === 'tdPt' ? 'td' : 'tc') }).addTo(layer);
    });
  }
  function ensureBox() {
    var host = document.getElementById('leafletTrafficMap'); if (!host || box) return;
    box = document.createElement('div'); box.id = 'hgFmsBox';
    host.appendChild(box);
    box.addEventListener('click', function (e) { if (e.target.closest('[data-fold]')) { folded = !folded; try { localStorage.setItem('hg_fms_track_fold', folded ? '1' : '0'); } catch (x) {} info(); } });
    ['mousedown', 'dblclick', 'wheel', 'touchstart'].forEach(function (ev) { box.addEventListener(ev, function (e) { e.stopPropagation(); }); });
  }
  function info() {
    ensureBox(); if (!box) return;
    var st = window.FmsStore && window.FmsStore.state, p = (st && st.plan) || {}, r = p.route || [];
    if (folded) { box.innerHTML = '<div class="hd" data-fold="1">▸ ' + T.unfold + '</div>'; return; }
    var h = '<div class="hd" data-fold="1">▾ ' + T.title + (p.origin && p.origin.icao ? ' · ' + esc(p.origin.icao) + ' → ' + esc(p.dest && p.dest.icao) : '') + '</div>';
    if (r.length < 2) { box.innerHTML = h + '<div class="ln mu">' + T.none + '</div>'; return; }
    var act = Math.max(1, Math.min(r.length - 1, p.activeLeg || 1)), w = r[act], me = ap && ap.live && ap.actual && isFinite(ap.actual.lat) ? { lat: ap.actual.lat, lon: ap.actual.lon } : null;
    var dNext = me ? nm(me, w) : null;
    h += '<div class="ln"><span class="mu">' + T.next + '</span> <b class="mg">' + esc(w.ident) + '</b>' + (dNext != null ? ' · ' + dNext.toFixed(1) + ' ' + T.nm : '') + (w.alt ? ' · ' + Math.round(w.alt) + ' ' + T.ft : '') + '</div>';
    var vn = ap && ap.live && ap.vnav ? ap.vnav : null, pr = profile(p), line = '';
    if (vn && vn.on && vn.phase === 'climb') line = f('climb', { a: vn.alt });
    else if (vn && vn.on && vn.phase === 'path') line = f('path', { a: vn.alt, p: esc(vn.at) });
    else if (vn && vn.on && vn.phase === 'cruise' && vn.tod >= 0 && vn.alt > 0) line = f('tod', { d: vn.tod, a: vn.alt, p: esc(vn.at) });
    else if (pr.td) line = f('todPlan', { d: (pr.td.toS - pr.td.s).toFixed(1), p: esc(pr.td.to), a: Math.round(pr.td.alt) }) + (vn && vn.on ? '' : ' <span class="mu">(' + T.vnavOff + ')</span>');
    else if (pr.cruise) line = f('cruise', { a: Math.round(pr.cruise) });
    if (line) h += '<div class="ln"><span class="mu">' + T.alt + '</span> <span class="am">' + line + '</span></div>';
    var il = ap && ap.live && ap.ils && ap.ils.ident ? ap.ils : null;
    if (il) h += '<div class="ln"><span class="mu">' + T.ils + '</span> <span class="gr">' + esc(il.ident) + ' ' + il.freq.toFixed(2) + ' · ' + String(il.crs).padStart(3, '0') + '°</span></div>';
    box.innerHTML = h;
  }
  var css = document.createElement('style');
  css.textContent = '#hgFmsBox{position:absolute;top:10px;right:10px;z-index:800;min-width:210px;max-width:320px;background:rgba(11,13,16,.92);border:1px solid #3d7aa6;border-radius:10px;padding:8px 10px;color:#cfe6f5;font:12px Consolas,"Cascadia Mono",monospace;line-height:1.5}' +
    '#hgFmsBox .hd{color:#7fd3ff;font-weight:700;cursor:pointer;user-select:none}#hgFmsBox .ln{margin-top:3px}#hgFmsBox .mu{color:#9aa3ad}#hgFmsBox .mg{color:#f2a7ee}#hgFmsBox .am{color:#f2c46b}#hgFmsBox .gr{color:#7fe0a8}' +
    '.hg-fms-lab{background:rgba(11,13,16,.85)!important;border:1px solid #e05bd8!important;color:#f8e6f7!important;font:11px Consolas,monospace!important;padding:1px 5px!important;box-shadow:none!important}' +
    '.hg-fms-lab::before{display:none!important}.hg-fms-td{border-color:#f2c46b!important;color:#f2c46b!important}.hg-fms-tc{border-color:#38bdf8!important;color:#7fd3ff!important}' +
    '.hg-fms-pin{font-size:15px;line-height:16px;text-align:center;text-shadow:0 0 3px #000,0 0 3px #000}';
  document.head.appendChild(css);
  function tick() {
    if (!open() || !map()) return;
    var st = window.FmsStore && window.FmsStore.state;
    if (st && (st.rev !== lastRev || !layer)) { lastRev = st.rev; draw(st); }
    fetch('http://localhost:8765/ap', { cache: 'no-store' }).then(function (x) { return x.json(); }).then(function (j) { ap = j; info(); }, function () { ap = null; info(); });
  }
  if (window.FmsStore) window.FmsStore.onChange(function (st) { if (open() && map()) { lastRev = st.rev; draw(st); info(); } });
  setInterval(tick, 2000);
})();
</script>
"""
for lang in ("fr", "en"):
    p = os.path.join(here, "..", "web", "dispatch_%s.html" % lang)
    s = open(p, encoding="utf-8").read()
    if "hangar-fms-track" in s:
        print("déjà fait", p); continue
    assert s.count("</body>") == 1 and "hangar-fms-vfr-link" in s, p   # après le lien Plan VFR (qui charge fms_store.js)
    s = s.replace("</body>", JS.replace("__TXT__", json.dumps(TXT[lang], ensure_ascii=False)) + "</body>")
    open(p, "w", encoding="utf-8", newline="").write(s)
    print("ok", p)
