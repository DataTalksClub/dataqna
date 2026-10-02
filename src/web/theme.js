/* The theme pin, for every page that offers a toggle.

   This lived in room.js and admin.js as the same thirty lines twice, which is
   how the front page ended up with no toggle at all: adding one meant a third
   copy. A page opts in by carrying a [data-theme-toggle] button; the pin
   itself is applied before paint by the inline script in each head, because a
   deferred asset is far too late to decide what colour the page is.

   Light is the default for everyone regardless of what their device prefers,
   so dark is the only thing that is ever stored. prefers-color-scheme is not
   consulted anywhere — a deliberate turn from dakit's README boot script,
   which falls back to the OS preference; see docs/design-system.md §3.

   Presentation mode is deliberately not here. It pins light by default —
   a projector renders white as "screen off" — and stores that under its own
   key, so it is a different decision rather than a variation on this one. */
(function () {
  "use strict";

  var root = document.documentElement;

  /* The address bar matches the top of the page, which is the hero band in a
     room and the page background everywhere else. */
  var DARK = root.getAttribute("data-theme-dark") || "#0d1117";
  var LIGHT = root.getAttribute("data-theme-light") || "#ffffff";

  /* The family icon language: 16x16, stroke 1.5, round caps, no fills — the
     same drawing style as the dakit chevron and every nav glyph. */
  var SUN = '<svg class="icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" ' +
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="8" cy="8" r="3.2"/><path d="M8 1.2v1.7M8 13.1v1.7M2.9 2.9l1.2 1.2M11.9 11.9l1.2 ' +
    '1.2M1.2 8h1.7M13.1 8h1.7M2.9 13.1l1.2-1.2M11.9 4.1l1.2-1.2"/></svg>';
  var MOON = '<svg class="icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" ' +
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M13.2 9.6A5.5 5.5 0 116.4 2.8a4.3 4.3 0 006.8 6.8z"/></svg>';

  function effective() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
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
    /* The pin is dakit's data-theme attribute; light is what the attribute's
       absence — or an explicit "light" — means. */
    root.setAttribute("data-theme", next);
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
