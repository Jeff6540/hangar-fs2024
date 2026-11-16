<script>
/* Couleurs adaptées aux daltoniens : palette Okabe-Ito pour le trafic IA (réglage de Hangar FS 2024) */
(function () {
  window.alColorblind = true;
  var MAP = {'#3B82F6': '#0072B2', '#F43F5E': '#D55E00', '#A78BFA': '#CC79A7', '#4DE1FF': '#56B4E9'};
  function apply() {
    try {
      if (typeof AC_CATS !== 'undefined') {
        AC_CATS.narrow.color = '#0072B2'; AC_CATS.wide.color = '#D55E00'; AC_CATS.jet.color = '#CC79A7';
        AC_CATS.other.color = '#56B4E9';
      }
    } catch (e) {}
    document.querySelectorAll('span[style*="color:#"]').forEach(function (sp) {
      var m = /color:\s*(#[0-9A-Fa-f]{6})/.exec(sp.getAttribute('style') || '');
      if (m && MAP[m[1].toUpperCase()]) sp.style.color = MAP[m[1].toUpperCase()];
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', apply); else apply();
})();
</script>