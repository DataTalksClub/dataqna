/* The theme pin, for every page that offers a toggle.

   This lived in room.js and admin.js as the same thirty lines twice, which is
   how the front page ended up with no toggle at all: adding one meant a third
   copy. A page opts in by carrying a [data-theme-toggle] button; the pin
   itself is applied before paint by the inline script in each head, because a
   deferred asset is far too late to decide what colour the page is.

   Light is the default for everyone regardless of what their device prefers,
   so dark is the only thing that is ever stored. prefers-color-scheme is not
   consulted anywhere.

   Presentation mode is deliberately not here. It pins light by default —
   a projector renders white as "screen off" — and stores that under its own
   key, so it is a different decision rather than a variation on this one. */
(function () {
  "use strict";

  var root = document.documentElement;

  /* The address bar matches the top of the page, which is the hero band in a
     room and the page background everywhere else. */
  var DARK = root.getAttribute("data-theme-dark") || "#0d1220";
  var LIGHT = root.getAttribute("data-theme-light") || "#f6f8fb";

  var SUN = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 ' +
    '1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
  var MOON = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

  function effective() {
    return root.classList.contains("theme-dark") ? "dark" : "light";
  }

  function paint() {
    var dark = effective() === "dark";
    var buttons = document.querySelectorAll("[data-theme-toggle]");
    Array.prototype.forEach.call(buttons, function (button) {
      button.innerHTML = dark ? SUN : MOON;
      button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    });
  }

  /* Light is the default, so it is the absence of a pin rather than a pin of
     its own — switching back to it clears the key instead of writing "light". */
  function toggle() {
    var next = effective() === "dark" ? "light" : "dark";
    root.classList.toggle("theme-dark", next === "dark");
    root.style.colorScheme = next;
    try {
      if (next === "dark") localStorage.setItem("dq_theme", "dark");
      else localStorage.removeItem("dq_theme");
    } catch (e) {}

    var color = next === "dark" ? DARK : LIGHT;
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    Array.prototype.forEach.call(metas, function (meta) { meta.setAttribute("content", color); });
    paint();
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("[data-theme-toggle]");
    if (button) toggle();
  });

  paint();
  window.dqTheme = { effective: effective, toggle: toggle, paint: paint };
})();
