# -*- coding: utf-8 -*-
"""FMS étape 3 : la page Plan VFR envoie sa route (SID, STAR, approche et ILS compris) au FMS dès qu'elle change."""
import os
here = os.path.dirname(os.path.abspath(__file__))
SAVE = "  function save() { try { localStorage.setItem(KEY, JSON.stringify({ v: 2, pts: pts, wpN: wpN, show: show, bg: bgIdx, pr: pr })); } catch (e) {} }"
SAVE2 = SAVE + "\n  /* FMS : la route complète (avec SID, STAR, approche) est lue par le lien Plan VFR → FMS */\n  window.hgVfrFull = function () { return { F: full(), pr: pr, PD: PD, ends: ends2(), label: apLabel }; };"
SAVE_HOOK_OLD = "localStorage.setItem(KEY, JSON.stringify({ v: 2, pts: pts, wpN: wpN, show: show, bg: bgIdx, pr: pr })); } catch (e) {} }"
SAVE_HOOK_NEW = "localStorage.setItem(KEY, JSON.stringify({ v: 2, pts: pts, wpN: wpN, show: show, bg: bgIdx, pr: pr })); } catch (e) {} try { if (window.hgVfrChanged) window.hgVfrChanged(); } catch (e) {} }"
JS = r"""<script src="/fms_store.js"></script><script id="hangar-fms-vfr-link">
/* FMS : la route de la page Plan VFR part dans la mémoire du FMS à chaque changement (pas à la simple ouverture de la page) */
(function () {
  var KEY = 'hg_vfr_fms_sent', timer = null;
  function kindOf(k) { return k === 'apt' ? 'apt' : k === 'vor' ? 'vor' : k === 'ndb' ? 'ndb' : 'wpt'; }
  function ilsFor(a, dest) {
    return new Promise(function (res) {
      if (!a || !/^(ILS|LOC|LDA|SDF)/.test(a.t) || !dest) { res(null); return; }
      var q = '&s=' + (dest.lat - .25) + '&w=' + (dest.lon - .35) + '&n=' + (dest.lat + .25) + '&e=' + (dest.lon + .35);
      fetch('/nav?k=ils' + q).then(function (r) { return r.json(); }).catch(function () { return []; }).then(function (arr) {
        var rh = (parseInt(a.r, 10) || 0) * 10, best = null;
        (arr || []).forEach(function (r) {
          var loc = +r[7] || 0, mv = +r[4] || 0;
          var cs = [loc - mv, loc, loc + mv].filter(function (c) { return Math.abs(((c - rh) % 360 + 540) % 360 - 180) < 30; });
          if (!rh || !cs.length) return;
          var d = Math.abs(((loc - rh) % 360 + 540) % 360 - 180);
          if (!best || d < best.d) best = { d: d, ident: r[0], freq: +r[5], crs: Math.round(((cs[0] % 360) + 360) % 360) || 360 };
        });
        res(best ? { ident: best.ident, freq: best.freq, crs: best.crs, gs: a.t === 'ILS', type: a.t } : null);
      });
    });
  }
  function send() {
    if (!window.hgVfrFull || !window.FmsStore) return;
    var v = window.hgVfrFull(), F = v.F || [], pr = v.pr || {}, e = v.ends || ['', ''];
    if (F.length < 2 || F[0].kind !== 'apt' || F[F.length - 1].kind !== 'apt') return;   // départ et arrivée sur des aéroports
    var dd = v.PD[e[0]], da = v.PD[e[1]];
    var sid = dd && dd.ok && pr.dep && dd.d[pr.dep.sid] ? dd.d[pr.dep.sid].n || '' : '';
    var star = da && da.ok && pr.arr && da.a[pr.arr.star] ? da.a[pr.arr.star].n || '' : '';
    var ap = da && da.ok && pr.arr && da.ap[pr.arr.ap] ? da.ap[pr.arr.ap] : null, apName = ap ? v.label(ap) : '';
    var route = F.map(function (p) {
      var via = p.kind === 'sid' ? sid : p.kind === 'star' ? star : p.kind === 'ap' ? apName : '';
      var w = { ident: p.name, lat: +p.lat, lon: +p.lon, alt: 0, type: kindOf(p.kind), via: via };
      if (p.kind === 'ap') w.ap = true;
      return w;
    });
    var sig = JSON.stringify([route.map(function (w) { return w.ident + ',' + w.lat.toFixed(4) + ',' + w.lon.toFixed(4); }), sid, star, apName]);
    var last = ''; try { last = localStorage.getItem(KEY) || ''; } catch (x) {}
    if (sig === last) return;                  // rien n'a changé depuis le dernier envoi (ex. simple ouverture de la page)
    try { localStorage.setItem(KEY, sig); } catch (x) {}
    var dest = route[route.length - 1];
    [route[0], dest].forEach(function (w) {   // altitude des aéroports (base OurAirports de la page) : le VNAV vise terrain + 1500 ft
      try { var A = typeof airportsDB !== 'undefined' ? airportsDB[w.ident] : null; if (A && isFinite(A.elevation_ft) && A.elevation_ft) {   /* 0 = souvent « inconnue » dans la base : on laisse le pilote la taper */ w.alt = Math.round(A.elevation_ft); w.elev = true; } } catch (x) {}
    });
    // approche : altitudes des données MSFS (contrainte, FAF) quand l'import les a
    if (ap) {
      var legAlt = {};
      (ap.f || []).concat.apply(ap.f || [], (ap.tr || []).map(function (t2) { return t2.l || []; })).forEach(function (l) {
        if (!l || l.length < 9) return;
        var d = +l[4] || 0, a1 = +l[5] || 0, a2 = +l[6] || 0, cur = legAlt[l[0]] || {};
        if (d > 0 && a1 > 0) { cur.alt = Math.round(d === 4 ? Math.max(a1, a2) : a1); cur.d = d; }
        if (+l[8] & 4) cur.faf = true;
        legAlt[l[0]] = cur;
      });
      route.forEach(function (w) {
        var L2 = w.ap && legAlt[w.ident]; if (!L2) return;
        if (L2.alt && !w.alt) { w.alt = L2.alt; w.altDesc = L2.d; w.altSrc = 'msfs'; }
        if (L2.faf) w.faf = true;
      });
    }
    // sinon : pas d'altitude sur le seuil de piste ; FAF à 3000 ft par défaut (terrain + 1500 ft si plus haut), points d'avant au même niveau
    (function () {
      if (route.some(function (w) { return w.altSrc === 'msfs'; })) { route.forEach(function (w) { if (/^RW\d/.test(w.ident)) w.alt = 0; }); return; }
      var last = route.length - 1, rwI = -1, faf = -1, i, aps = [];
      for (i = 1; i <= last; i++) if (/^RW\d/.test(route[i].ident)) { route[i].alt = 0; if (rwI < 0) rwI = i; }
      for (i = 1; i < last; i++) if (route[i].ap && !/^RW\d/.test(route[i].ident)) aps.push(i);
      var end = rwI > 0 ? rwI : last;
      aps.forEach(function (k) { if (k < end && (route[k].faf || /^(FF|FI|FA|FAF)/.test(route[k].ident))) faf = k; });
      if (faf < 0) aps.forEach(function (k) { if (k < end) faf = k; });
      if (faf < 0) return;
      var el = dest.elev ? dest.alt || 0 : 0, def = Math.max(3000, Math.ceil((el + 1500) / 100) * 100);
      if (!route[faf].alt) { route[faf].alt = def; route[faf].altDef = true; }
      aps.forEach(function (k) { if (k < faf && !route[k].alt) { route[k].alt = route[faf].alt; route[k].altDef = true; } });
    })();
    ilsFor(ap, dest).then(function (ils) {
      var ap0 = route[0], st = window.FmsStore.state || {}, old = (st.plan || {});
      // même départ et même arrivée : on garde l'altitude de croisière déjà connue du FMS
      var keepAlt = old.origin && old.dest && old.origin.icao === ap0.ident && old.dest.icao === dest.ident ? old.cruiseAlt || 0 : 0;
      var oldAlt = {}; (old.route || []).forEach(function (w) { if (w.alt) oldAlt[w.ident] = w.alt; });   // altitudes réglées dans le FMS : gardées
      route.forEach(function (w, i) { if (i > 0 && i < route.length - 1 && oldAlt[w.ident]) w.alt = oldAlt[w.ident]; });
      window.FmsStore.set({ plan: {
        origin: { icao: ap0.ident, rwy: '' }, dest: { icao: dest.ident, rwy: ap ? ap.r || '' : '' },
        cruiseAlt: keepAlt, route: route, departure: sid, arrival: star, approach: apName, ils: ils, activeLeg: 1
      } }, 'vfr');
    });
  }
  // plusieurs changements d'affilée (glisser un point…) : un seul envoi, une seconde après le dernier
  window.hgVfrChanged = function () { clearTimeout(timer); timer = setTimeout(send, 1000); };
})();
</script>
"""
for lang in ("fr", "en"):
    p = os.path.join(here, "..", "web", "dispatch_%s.html" % lang)
    s = open(p, encoding="utf-8").read()
    if "hangar-fms-vfr-link" in s:
        print("déjà fait", p); continue
    assert s.count(SAVE) == 1, p
    s = s.replace(SAVE, SAVE2.replace(SAVE_HOOK_OLD, SAVE_HOOK_NEW, 1))
    assert s.count("</body>") == 1
    s = s.replace("</body>", JS + "</body>")
    open(p, "w", encoding="utf-8", newline="").write(s)
    print("ok", p)
