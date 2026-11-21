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
