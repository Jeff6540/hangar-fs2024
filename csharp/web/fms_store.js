// FMS — mémoire commune du plan de vol, côté page.
// Toute page de l'appli peut l'utiliser : <script src="/fms_store.js"></script>
//   FmsStore.state          → le vol en cours (null tant que l'appli n'a pas répondu)
//   FmsStore.onChange(fn)   → fn(state) à chaque changement, d'où qu'il vienne (et une fois au départ)
//   FmsStore.set(patch, source)  → modifie seulement ce qui est envoyé, ex. { plan: { activeLeg: 3 } }
//   FmsStore.reset(source)  → « Nouveau vol »
(function () {
  if (window.FmsStore) return;
  var hasHost = !!(window.chrome && window.chrome.webview);
  var listeners = [];
  var KEY = 'hg_fms_state_copy';   // copie de secours si la page est ouverte hors de l'appli

  function post(msg) {
    if (hasHost) { try { window.chrome.webview.postMessage({ fms: msg }); return true; } catch (e) {} }
    return false;
  }
  function emit(st) {
    store.state = st;
    try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {}
    listeners.slice().forEach(function (fn) { try { fn(st); } catch (e) { console.error(e); } });
  }
  function merge(a, b) {
    Object.keys(b || {}).forEach(function (k) {
      var v = b[k];
      if (v && typeof v === 'object' && !Array.isArray(v) && a[k] && typeof a[k] === 'object' && !Array.isArray(a[k])) merge(a[k], v);
      else a[k] = v;
    });
    return a;
  }

  var store = {
    state: null,
    onChange: function (fn) { listeners.push(fn); if (store.state) { try { fn(store.state); } catch (e) {} } },
    set: function (patch, source) {
      if (!post({ op: 'set', patch: patch, source: source || '' })) {
        var st = merge(JSON.parse(JSON.stringify(store.state || {})), patch);
        st.rev = (st.rev || 0) + 1; st.source = source || ''; st.updated = new Date().toISOString();
        emit(st);
      }
    },
    reset: function (source) {
      if (!post({ op: 'reset', source: source || '' })) { try { localStorage.removeItem(KEY); } catch (e) {} location.reload(); }
    },
    refresh: function () { post({ op: 'get' }); }
  };
  window.FmsStore = store;

  if (hasHost) {
    window.chrome.webview.addEventListener('message', function (e) {
      var d = e.data;
      if (d && d.fmsState) emit(d.fmsState);
    });
    post({ op: 'get' });
  } else {
    try { var c = JSON.parse(localStorage.getItem(KEY) || 'null'); if (c) emit(c); } catch (e) {}
  }
})();
