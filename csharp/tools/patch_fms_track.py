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
      if (dest) { if (!(r[i].elev === true || (r[i].alt > 0 && r[i].elev !== false)) || r.some(function (q) { return q.ap && q.alt > 0; })) continue; a += 1500; d = Math.max(0, d - 5); }
      if (a <= 0 || a >= cruise - 300) continue;
      var s = d - (cruise - a) / 318.4; if (!best || s < best.s) best = { s: Math.max(s, cum[peak]), alt: a, to: r[i].ident, toS: d };
    }
    if (best) { out.td = best; out.tdPt = along(r, best.s); }
    var elev = r[0].alt || 0, tcS = (cruise - elev) / 250;
    if (tcS > 0 && (!best || tcS < best.s)) { out.tc = { s: tcS }; out.tcPt = along(r, tcS); }
    return out;
  }
  /* branche en cours : celle du FMS, ou plus loin si ton avion a déjà dépassé des points (FMS pas engagé) */
  var lastAct = -1;
  function actOf(p, r) {
    var act = Math.max(1, Math.min(r.length - 1, p.activeLeg || 1));
    var me = ap && ap.live && ap.actual && isFinite(ap.actual.lat) ? { lat: ap.actual.lat, lon: ap.actual.lon } : null;
    if (!me || r.length < 2) return act;
    var best = act, bx = Infinity;
    for (var i = 1; i < r.length; i++) { if (!isFinite(r[i].lat) || !isFinite(r[i - 1].lat)) continue; var x = nm(me, r[i - 1]) + nm(me, r[i]) - nm(r[i - 1], r[i]); if (x < bx) { bx = x; best = i; } }
    return bx < 15 ? Math.max(act, best) : act;
  }
  function draw(st) {
    var m = map(); if (!m || !window.L) return;
    if (!layer) layer = L.layerGroup().addTo(m);
    /* étiquettes du plan sous les avions (le tien reste toujours visible) */
    if (!m.getPane('hgFmsLbl')) { var pn = m.createPane('hgFmsLbl'); pn.style.zIndex = 590; pn.style.pointerEvents = 'none'; }
    layer.clearLayers();
    var p = (st && st.plan) || {}, r = (p.route || []).filter(function (w) { return isFinite(w.lat) && isFinite(w.lon) && !(w.lat === 0 && w.lon === 0); });
    if (r.length < 2) return;
    var act = actOf(p, r); lastAct = act;
    for (var i = 1; i < r.length; i++) {
      var done = i < act, on = i === act;
      L.polyline([[r[i - 1].lat, r[i - 1].lon], [r[i].lat, r[i].lon]], { color: '#1e1b4b', weight: 7, opacity: .4, interactive: false }).addTo(layer);
      L.polyline([[r[i - 1].lat, r[i - 1].lon], [r[i].lat, r[i].lon]], { color: done ? '#9ca3af' : '#e05bd8', weight: on ? 5 : 3, opacity: done ? .6 : 1, dashArray: r[i].ap ? '8 6' : null, interactive: false }).addTo(layer);
    }
    r.forEach(function (w, i) {
      // altitude : « * » = valeur par défaut du FMS, A = à ou au-dessus, B = à ou au-dessous (données MSFS)
      var sfx = w.altDef ? '*' : w.altDesc === 2 ? 'A' : w.altDesc === 3 ? 'B' : w.altDesc === 4 ? '±' : '';
      var lbl = '<b>' + esc(w.ident) + '</b>' + (w.faf ? ' FAF' : '') + (w.alt ? ' · ' + Math.round(w.alt) + sfx + ' ' + T.ft : '');
      var cm = L.circleMarker([w.lat, w.lon], { radius: i === act ? 6 : 4, color: '#000', weight: 1, fillColor: i === act ? '#e05bd8' : i < act ? '#9ca3af' : '#ffffff', fillOpacity: 1 });
      /* points déjà passés : plus d'étiquette (moins de texte autour de ton avion) */
      if (i >= act || i === r.length - 1) cm.bindTooltip(lbl, { permanent: true, direction: 'right', offset: [6, 0], className: 'hg-fms-lab', pane: 'hgFmsLbl' });
      cm.addTo(layer);
    });
    var pr = profile(p);
    [['tcPt', T.tc, '#38bdf8', '▲'], ['tdPt', T.td, '#f2c46b', '▼']].forEach(function (k) {
      var pt = pr[k[0]]; if (!pt) return;
      var sub = k[0] === 'tdPt' && pr.td ? ' → ' + Math.round(pr.td.alt) + ' ' + T.ft + ' (' + esc(pr.td.to) + ')' : ' → ' + Math.round(pr.cruise) + ' ' + T.ft;
      L.marker([pt.lat, pt.lon], { interactive: false, icon: L.divIcon({ className: 'hg-fms-pin', html: '<span style="color:' + k[2] + '">' + k[3] + '</span>', iconSize: [16, 16], iconAnchor: [8, 8] }) })
        .bindTooltip('<b>' + k[1] + '</b>' + sub, { permanent: true, direction: 'left', offset: [-8, 0], className: 'hg-fms-lab hg-fms-' + (k[0] === 'tdPt' ? 'td' : 'tc'), pane: 'hgFmsLbl' }).addTo(layer);
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
    var act = actOf(p, r), w = r[act], me = ap && ap.live && ap.actual && isFinite(ap.actual.lat) ? { lat: ap.actual.lat, lon: ap.actual.lon } : null;
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
  css.textContent = '#hgFmsBox{position:absolute;top:10px;left:50%;transform:translateX(-50%);z-index:800;min-width:210px;max-width:320px;background:rgba(11,13,16,.92);border:1px solid #3d7aa6;border-radius:10px;padding:8px 10px;color:#cfe6f5;font:12px Consolas,"Cascadia Mono",monospace;line-height:1.5}' +
    '#hgFmsBox .hd{color:#7fd3ff;font-weight:700;cursor:pointer;user-select:none}#hgFmsBox .ln{margin-top:3px}#hgFmsBox .mu{color:#9aa3ad}#hgFmsBox .mg{color:#f2a7ee}#hgFmsBox .am{color:#f2c46b}#hgFmsBox .gr{color:#7fe0a8}' +
    'html body #trafficMapWrapper .leaflet-tooltip.hg-fms-lab,.hg-fms-lab{background:rgba(11,13,16,.68)!important;border:1px solid rgba(224,91,216,.7)!important;color:#f8e6f7!important;font:9.5px/13px Consolas,monospace!important;padding:0 4px!important;border-radius:4px!important;box-shadow:none!important}' +
    '.hg-fms-lab::before{display:none!important}html body #trafficMapWrapper .leaflet-tooltip.hg-fms-td{border-color:#f2c46b!important;color:#f2c46b!important}html body #trafficMapWrapper .leaflet-tooltip.hg-fms-tc{border-color:#38bdf8!important;color:#7fd3ff!important}' +
    '.hg-fms-pin{font-size:12px;line-height:16px;text-align:center;text-shadow:0 0 3px #000,0 0 3px #000}';
  document.head.appendChild(css);
  // ---- plan SimBrief importé dans le Suivi de vol : le FMS le reçoit aussi (approche du FMS gardée si même arrivée)
  function arr(x) { return Array.isArray(x) ? x : x ? [x] : []; }
  function num(x) { var n = parseFloat(x); return isFinite(n) ? n : 0; }
  function sbToFms() {
    var j = window.alPlanFull; if (!j || !window.FmsStore || !j.origin || !j.destination) return;
    var id = [(j.params && (j.params.request_id || j.params.time_generated)) || '', j.origin.icao_code, j.destination.icao_code, j.general && j.general.route].join('|');
    var last = ''; try { last = localStorage.getItem('hg_fms_sb_sent') || ''; } catch (e) {}
    if (id === last) return;                 // même plan déjà envoyé (réouverture de la page) : on ne touche pas au FMS
    try { localStorage.setItem('hg_fms_sb_sent', id); } catch (e) {}
    var fixes = arr(j.navlog && j.navlog.fix); if (!fixes.length) return;
    var route = [{ ident: j.origin.icao_code, lat: num(j.origin.pos_lat), lon: num(j.origin.pos_long), alt: num(j.origin.elevation), elev: true, type: 'apt', via: '' }];
    var sid = '', star = '', enroute = false;
    fixes.forEach(function (fx) {
      if (fx.ident === 'TOC' || fx.ident === 'TOD') return;
      if (fx.ident === j.destination.icao_code && fx.type === 'apt') return;
      if (fx.is_sid_star === '1' && fx.via_airway && fx.via_airway !== 'DCT') { if (!enroute) sid = fx.via_airway; else star = fx.via_airway; } else enroute = true;
      route.push({ ident: fx.ident, lat: num(fx.pos_lat), lon: num(fx.pos_long), alt: num(fx.altitude_feet), type: fx.type || '', via: fx.via_airway && fx.via_airway !== 'DCT' ? fx.via_airway : '' });
    });
    var dest = { ident: j.destination.icao_code, lat: num(j.destination.pos_lat), lon: num(j.destination.pos_long), alt: num(j.destination.elevation), elev: true, type: 'apt', via: '' };
    var old = (window.FmsStore.state && window.FmsStore.state.plan) || {}, keep = {};
    if (old.dest && old.dest.icao === dest.ident && old.approach) {
      // même arrivée : l'approche du FMS est raccordée à la fin de la STAR
      var aps = (old.route || []).filter(function (w) { return w.ap; });
      if (aps.length) {
        var k = -1; route.forEach(function (w, i) { if (i > 0 && w.ident === aps[0].ident) k = i; });
        if (k > 0) route = route.slice(0, k);
        route = route.concat(aps);
        keep = { approach: old.approach, ils: old.ils || null };
        if (old.dest.rwy) keep.rwy = old.dest.rwy;
      }
    }
    route.push(dest);
    var plan = { origin: { icao: j.origin.icao_code || '', rwy: j.origin.plan_rwy || '' }, dest: { icao: dest.ident, rwy: keep.rwy || j.destination.plan_rwy || '' },
      cruiseAlt: num(j.general && j.general.initial_altitude), route: route, departure: sid, arrival: star, approach: keep.approach || '', ils: keep.ils || null, activeLeg: 1 };
    window.FmsStore.set({ plan: plan }, 'simbrief');
  }
  window.addEventListener('al-plan', function () { setTimeout(sbToFms, 50); });
  // ---- un seul tracé : le trait SimBrief est masqué quand le FMS a une route pour le même vol
  function sbVisibility() {
    var m = map(); if (!m) return;
    var st = window.FmsStore && window.FmsStore.state, p = st && st.plan || {}, pd = window.alPlanData;
    var same = !!(pd && pd.origin && pd.destination && p.origin && p.dest && (p.route || []).length > 1 &&
      p.origin.icao === pd.origin.icao_code && p.dest.icao === pd.destination.icao_code);
    [typeof sbLayer !== 'undefined' ? sbLayer : null, typeof sbLabelLayer !== 'undefined' ? sbLabelLayer : null].forEach(function (lg) {
      if (!lg) return;
      if (same && m.hasLayer(lg)) m.removeLayer(lg);
      else if (!same && !m.hasLayer(lg)) lg.addTo(m);
    });
  }
  var aptSig = '';
  function preloadAirports() {
    var st = window.FmsStore && window.FmsStore.state, r = st && st.plan && st.plan.route || [];
    if (r.length < 2) return;
    var a = r[0], b = r[r.length - 1];
    if (!isFinite(a.lat) || !isFinite(b.lat) || (a.lat === 0 && a.lon === 0)) return;
    var cur = window.alFlightAirports;
    if (cur && cur.length && !cur._fms) return;              // un plan SimBrief est chargé : c'est lui qui décide
    var sig = [a.lat, a.lon, b.lat, b.lon].join(',');
    if (sig === aptSig) return;
    aptSig = sig;
    var list = [[a.lat, a.lon], [b.lat, b.lon]]; list._fms = true;
    window.alFlightAirports = list;
    try { window.dispatchEvent(new Event('al-plan')); } catch (e) {}
  }
  function tick() {
    preloadAirports();
    if (!open() || !map()) return;
    sbVisibility();
    var st = window.FmsStore && window.FmsStore.state;
    if (st && (st.rev !== lastRev || !layer)) { lastRev = st.rev; draw(st); }
    else if (st && st.plan && st.plan.route && st.plan.route.length > 1) { var rr = st.plan.route.filter(function (w) { return isFinite(w.lat) && isFinite(w.lon) && !(w.lat === 0 && w.lon === 0); }); if (rr.length > 1 && actOf(st.plan, rr) !== lastAct) draw(st); }
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
