/* The theme pin, for every page that offers a toggle.

   This lived in room.js and admin.js as the same thirty lines twice, which is
   how the front page ended up with no toggle at all: adding one meant a third
   copy. A page opts in with a [data-theme-toggle] icon button (room, present,
   public pages) or a [data-appearance-toggle] track switch (the admin Account
   popover — the only theme control on that surface). The pin itself is applied
   before paint by the inline script in each head, because a deferred asset is
   far too late to decide what colour the page is.

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

  /* The address bar matches the top of the page: the page background, on
     every surface that offers the toggle. */
  var DARK = root.getAttribute("data-theme-dark") || "#0d1117";
  var LIGHT = root.getAttribute("data-theme-light") || "#ffffff";

  /* The family icon language: 24-grid paths rendered at 20px, stroke 1.8,
     round caps, no fills — the dataops geometry the spec codified. */
  var SUN = '<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="4.8"/><path d="M12 1.8v2.55M12 19.65v2.55M4.35 4.35l1.8 1.8M17.85 17.85l1.8 ' +
    '1.8M1.8 12h2.55M19.65 12h2.55M4.35 19.65l1.8-1.8M17.85 6.15l1.8-1.8"/></svg>';
  var MOON = '<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M19.8 14.4A8.25 8.25 0 119.6 4.2a6.45 6.45 0 0010.2 10.2Z"/></svg>';

  function effective() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function paint() {
    var dark = effective() === "dark";
    var label = dark ? "Switch to light theme" : "Switch to dark theme";
    var buttons = document.querySelectorAll("[data-theme-toggle]");
    Array.prototype.forEach.call(buttons, function (button) {
      button.innerHTML = dark ? SUN : MOON;
      button.setAttribute("aria-label", label);
    });
    var switches = document.querySelectorAll("[data-appearance-toggle]");
    Array.prototype.forEach.call(switches, function (button) {
      button.setAttribute("aria-pressed", dark ? "true" : "false");
      button.setAttribute("aria-label", label);
      var text = button.querySelector("[data-appearance-label]");
      if (text) text.textContent = dark ? "Light mode" : "Dark mode";
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
    var button = event.target.closest && event.target.closest("[data-theme-toggle], [data-appearance-toggle]");
    if (button) toggle();
  });

  paint();
  window.dqTheme = { effective: effective, toggle: toggle, paint: paint };
})();
