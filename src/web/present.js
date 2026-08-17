/* Presentation mode. Projected, staff-only, two states in one frame:

   The resting state is the ranked list — the audience votes because they can
   see what is winning, so the list re-sorts live and movement is animated to
   stay legible. Spotlight blows one question up; the spotlit question never
   moves underneath the host — the ranking only matters again once they
   return to the list.

   Clicking is the interaction model: the card carries the actions that run the
   session (pin, mark answered), everything view-level lives in the toolbar —
   hiding is moderation and stays in the room console. The pinned state shows
   in the button, not as a second glyph beside the author. The only keys are
   the conventional ones —
   arrows move the selection, Esc backs out of spotlight or the overlay. */
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("config").textContent);
  var API = "/api/v1/rooms/" + CONFIG.room_id;
  var MOTION = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;
  var MAX_ROWS = 6;

  function svg(paths, size) {
    return '<svg width="' + (size || 20) + '" height="' + (size || 20) + '" viewBox="0 0 24 24" ' +
      'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round" aria-hidden="true">' + paths + "</svg>";
  }

  var I = {
    chevron: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M6 14l6-7 6 7"/></svg>',
    pin: svg('<path d="M9 4h6"/><path d="M10 4v5l-3 3v2h10v-2l-3-3V4"/><path d="M12 14v7"/>'),
    check: svg('<path d="M20 6 9 17l-5-5"/>'),
    focus: svg('<path d="M4 8V6a2 2 0 0 1 2-2h2"/><path d="M16 4h2a2 2 0 0 1 2 2v2"/>' +
      '<path d="M20 16v2a2 2 0 0 1-2 2h-2"/><path d="M8 20H6a2 2 0 0 1-2-2v-2"/>' +
      '<circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>', 18),
    undo: svg('<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-15-6.7L3 13"/>', 18),
    qr: svg('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" ' +
      'height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>' +
      '<path d="M14 14h3v3h-3z"/><path d="M21 14v3h-1"/><path d="M14 21h3"/>', 18),
    sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 ' +
      '17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>', 18),
    moon: svg('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>', 18),
    expand: svg('<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>' +
      '<path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>', 18),
    shrink: svg('<path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/>' +
      '<path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/>', 18),
    close: svg('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', 18),
    left: svg('<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>'),
    right: svg('<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>'),
    back: svg('<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>', 18)
  };
  var state = {
    items: [],
    etag: null,
    epoch: 0,
    mode: "list",
    selectedId: null,
    spotlightId: null,
    lastAction: null,
    overlayPinned: false,
    overlayDismissed: false,
    loaded: false,
    painted: false,
    scores: {},
    busy: {}
  };

  function $(id) { return document.getElementById(id); }

  function request(path, options) {
    options = options || {};
    options.headers = Object.assign({ "content-type": "application/json" }, options.headers || {});
    return fetch(path, options).then(function (res) {
      if (res.status === 304) return { unchanged: true };
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (!res.ok) throw new Error((body.error && body.error.message) || "Request failed");
        return body;
      });
    });
  }

  /* The server ranks, but the tap cannot wait for it: ranking here too is
     what lets the optimistic pin reorder on the click — playFlip slides the
     pinned card up and the displaced one down instead of the room watching
     both sit still for the next poll. Mirrors the server's popular sort. */
  function visible() {
    return state.items
      .filter(function (item) {
        return !item.status || item.status === "visible";
      })
      .sort(function (a, b) {
        if (!!b.pinned !== !!a.pinned) return b.pinned ? 1 : -1;
        if (b.score !== a.score) return b.score - a.score;
        return a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0;
      });
  }

  function byId(id) {
    for (var i = 0; i < state.items.length; i++) {
      if (state.items[i].question_id === id) return state.items[i];
    }
    return null;
  }

  function shown() { return visible().slice(0, MAX_ROWS); }

  /* A host cue with the undo one tap away — mis-taps get likelier now that
     every action is a button. */
  function cue(message, withUndo) {
    var node = $("cue");
    node.textContent = "";
    var text = document.createElement("span");
    text.textContent = message;
    node.appendChild(text);
    if (withUndo) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = "Undo";
      button.addEventListener("click", undo);
      node.appendChild(button);
    }
    node.classList.add("show");
    clearTimeout(node._timer);
    node._timer = setTimeout(function () { node.classList.remove("show"); }, withUndo ? 6000 : 2600);
  }

  function hideCue() {
    var node = $("cue");
    clearTimeout(node._timer);
    node.classList.remove("show");
  }

  /* ---- actions ----

     Optimistic to the point of hiding the network entirely. A pin lands
     pinned, an answered card leaves, both on the tap: a spinner on a
     projected screen is a stall the room watches the host sit through, and
     the delay it reports is not one they can do anything about. The request
     still goes out — `state.busy` holds the poll off it — and a refusal
     rolls the change back and says so in the cue. The console keeps its
     spinners; that surface is the host's alone, and there a slow network
     should read as busy rather than broken. */

  function performAction(item, name, payload, options) {
    options = options || {};
    state.epoch += 1;
    var run = function () {
      QNA.patch({
        item: item,
        payload: payload,
        busy: state.busy,
        action: name,
        send: function () {
          return request(API + "/questions/" + item.question_id, {
            method: "PATCH", body: JSON.stringify(payload)
          });
        },
        render: render,
        done: function () {
          state.etag = null;
          if (options.done) options.done();
        },
        fail: function (error) {
          if (options.fail) options.fail(error);
          else cue(error.message);
        }
      });
    };
    if (options.leave) dismiss(item, run);
    else run();
  }

  /* Removals acknowledge on the tap: the card leaves (or the spotlight
     closes) immediately, the cue offers undo, and a refusal rolls back. */
  function removal(item, name, status, label) {
    if (state.busy[item.question_id]) return;
    state.lastAction = { question_id: item.question_id };
    // The pin goes with the card: an answered question holds nothing up.
    performAction(item, name, { status: status, pinned: false }, { leave: state.mode === "list" });
    if (state.mode === "spotlight") exitSpotlight();
    cue(label, true);
    paintToolbar();
  }

  function markAnswered(item) { removal(item, "answered", "answered", "Marked answered"); }

  /* One pin per room: pinning this question retires the room's other pin,
     and both happen on the tap. A refusal brings the retired pin back. */
  function togglePin(item) {
    if (state.busy[item.question_id]) return;
    var retired = [];
    if (!item.pinned) {
      state.items.forEach(function (other) {
        if (other !== item && other.pinned) {
          other.pinned = false;
          retired.push(other);
        }
      });
    }
    performAction(item, "pin", { pinned: !item.pinned }, {
      fail: function (error) {
        retired.forEach(function (other) { other.pinned = true; });
        cue(error.message);
      }
    });
  }

  /* One level of undo costs nothing and saves the projected moment. */
  function undo() {
    if (!state.lastAction) return;
    var target = state.lastAction;
    state.lastAction = null;
    hideCue();
    paintToolbar();
    var item = byId(target.question_id);
    state.epoch += 1;
    if (item) {
      QNA.patch({
        item: item,
        payload: { status: "visible" },
        busy: state.busy,
        action: "undo",
        send: function () {
          return request(API + "/questions/" + target.question_id, {
            method: "PATCH", body: JSON.stringify({ status: "visible" })
          });
        },
        render: render,
        done: function () { state.etag = null; cue("Restored"); refresh(); },
        fail: function (error) { cue(error.message); }
      });
    } else {
      request(API + "/questions/" + target.question_id, {
        method: "PATCH", body: JSON.stringify({ status: "visible" })
      }).then(function () {
        state.etag = null;
        cue("Restored");
        refresh();
      }, function (error) { cue(error.message); });
    }
  }

  /* ---- rendering ---- */

  function iconButton(name, markup, handler, pressed) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "icon-btn";
    button.innerHTML = markup;
    button.setAttribute("aria-label", name);
    button.title = name;
    if (pressed !== undefined) button.setAttribute("aria-pressed", pressed ? "true" : "false");
    button.addEventListener("click", handler);
    return button;
  }

  function buildRow(item) {
    var li = document.createElement("li");
    li.dataset.qid = item.question_id;
    if (item.question_id === state.selectedId) li.classList.add("selected");

    var score = document.createElement("div");
    score.className = "p-score";
    score.innerHTML = I.chevron + '<span class="count">' + item.score + "</span>";

    var body = document.createElement("div");
    body.className = "p-body";
    var text = document.createElement("div");
    text.className = "p-text";
    text.textContent = item.text;
    var meta = document.createElement("div");
    meta.className = "p-meta";
    var who = document.createElement("span");
    who.textContent = item.author_name || "Anonymous";
    meta.appendChild(who);
    body.appendChild(text);
    body.appendChild(meta);

    var actions = document.createElement("div");
    actions.className = "p-actions";
    var buttons = {
      pin: iconButton(item.pinned ? "Unpin" : "Pin", I.pin, function () { togglePin(item); }, !!item.pinned),
      answered: iconButton("Mark answered", I.check, function () { markAnswered(item); })
    };
    actions.appendChild(buttons.pin);
    actions.appendChild(buttons.answered);

    li.appendChild(score);
    li.appendChild(body);
    li.appendChild(actions);
    return li;
  }

  function positions(list) {
    var map = {};
    Array.prototype.forEach.call(list.children, function (li) {
      map[li.dataset.qid] = li.offsetTop;
    });
    return map;
  }

  /* A rank change is the emotional core of a live Q&A. Sliding the cards to
     their new places makes it legible; a straight swap reads as a glitch. */
  function playFlip(list, before) {
    if (!MOTION) return;
    Array.prototype.forEach.call(list.children, function (li) {
      var was = before[li.dataset.qid];
      if (was === undefined) {
        if (state.painted) li.classList.add("entering");
        return;
      }
      var delta = was - li.offsetTop;
      if (!delta) return;
      li.style.transform = "translateY(" + delta + "px)";
      requestAnimationFrame(function () {
        li.style.transition = "transform .3s ease";
        li.style.transform = "";
      });
      li.addEventListener("transitionend", function once() {
        li.style.transition = "";
        li.removeEventListener("transitionend", once);
      });
    });
  }

  function renderList() {
    var list = $("plist");
    var rows = shown();
    var before = positions(list);

    list.textContent = "";
    rows.forEach(function (item) { list.appendChild(buildRow(item)); });
    playFlip(list, before);

    if (MOTION && state.painted) {
      rows.forEach(function (item) {
        var old = state.scores[item.question_id];
        if (old === undefined || old === item.score) return;
        var count = list.querySelector('[data-qid="' + item.question_id + '"] .count');
        if (count) {
          count.classList.remove("pop");
          void count.offsetWidth;
          count.classList.add("pop");
        }
      });
    }
    state.scores = {};
    state.items.forEach(function (item) { state.scores[item.question_id] = item.score; });

    var extra = visible().length - rows.length;
    $("more").hidden = extra <= 0;
    if (extra > 0) $("more").textContent = "+ " + extra + " more in the queue";
    state.painted = true;
  }

  function renderStage() {
    var item = byId(state.spotlightId);
    if (!item) return exitSpotlight();
    $("q-text").textContent = item.text;

    var meta = $("q-meta");
    meta.textContent = "";
    var score = document.createElement("span");
    score.className = "q-score";
    score.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true"><path d="M6 14l6-7 6 7"/></svg><span>' + item.score + "</span>";
    meta.appendChild(score);
    var who = document.createElement("span");
    who.textContent = item.author_name || "Anonymous";
    meta.appendChild(who);

    var actions = $("stage-actions");
    actions.textContent = "";
    var list = visible();
    var at = list.indexOf(item);
    var prev = iconButton("Previous question", I.left, function () { step(-1); });
    var next = iconButton("Next question", I.right, function () { step(1); });
    prev.disabled = at <= 0;
    next.disabled = at === -1 || at >= list.length - 1;
    var buttons = {
      pin: iconButton(item.pinned ? "Unpin" : "Pin", I.pin, function () { togglePin(item); }, !!item.pinned),
      answered: iconButton("Mark answered", I.check, function () { markAnswered(item); })
    };

    var back = document.createElement("button");
    back.type = "button";
    back.className = "ghost small";
    back.innerHTML = I.back + "<span>All questions</span>";
    back.addEventListener("click", exitSpotlight);

    actions.appendChild(prev);
    actions.appendChild(next);
    var gap1 = document.createElement("span");
    gap1.className = "spacer";
    actions.appendChild(gap1);
    actions.appendChild(buttons.pin);
    actions.appendChild(buttons.answered);
    var gap2 = document.createElement("span");
    gap2.className = "spacer";
    actions.appendChild(gap2);
    actions.appendChild(back);
  }

  function paintToolbar() {
    $("tb-undo").disabled = !state.lastAction;
    var lit = state.mode === "spotlight";
    var spot = $("tb-spot");
    spot.innerHTML = I.focus + "<span>" + (lit ? "All questions" : "Spotlight") + "</span>";
    spot.setAttribute("aria-label", lit ? "Back to all questions" : "Spotlight the top question");
    spot.setAttribute("aria-pressed", lit ? "true" : "false");
    spot.disabled = !lit && !visible().length;
    var dark = document.documentElement.classList.contains("theme-dark");
    $("tb-theme").innerHTML = (dark ? I.sun : I.moon) + "<span>" + (dark ? "Light" : "Dark") + "</span>";
    $("tb-theme").setAttribute("aria-label", dark ? "Switch to the light theme" : "Switch to the dark theme");
    var full = !!document.fullscreenElement;
    $("tb-full").innerHTML = (full ? I.shrink : I.expand) + "<span>" + (full ? "Exit fullscreen" : "Fullscreen") + "</span>";
  }

  function overlayShouldShow() {
    if (state.overlayPinned) return true;
    return state.loaded && !visible().length && !state.overlayDismissed;
  }

  function render() {
    var count = visible().length;
    var inSpotlight = state.mode === "spotlight" && byId(state.spotlightId);
    if (state.mode === "spotlight" && !inSpotlight) state.mode = "list";

    $("plist").hidden = state.mode !== "list";
    if (state.mode !== "list") $("more").hidden = true;
    $("stage").hidden = state.mode !== "spotlight";

    if (state.mode === "spotlight") {
      renderStage();
      var list = visible();
      var at = list.indexOf(byId(state.spotlightId));
      $("progress").textContent = at === -1 ? "" : (at + 1) + " of " + list.length;
    } else {
      renderList();
      $("progress").textContent = count ? count + (count === 1 ? " question" : " questions") : "No questions yet";
    }
    $("join-count").textContent = count ? count + (count === 1 ? " question" : " questions") : "";

    if (count) state.overlayDismissed = false;
    $("overlay").classList.toggle("show", overlayShouldShow());
    paintToolbar();
  }

  function refresh() {
    // An in-flight optimistic change must not be stomped by the 1s poll.
    if (Object.keys(state.busy).length) return Promise.resolve();
    var epoch = state.epoch;
    var headers = state.etag ? { "if-none-match": state.etag } : {};
    return request(API + "/questions?sort=popular&status=visible", { headers: headers })
      .then(function (body) {
        // A 304 — most polls — re-renders nothing at all.
        if (body.unchanged || !body.items) return;
        if (epoch !== state.epoch || Object.keys(state.busy).length) return;
        // A question asked outranks the join code it came through: the QR
        // overlay's job is to fill an empty screen, not to sit on the first
        // question it produced.
        var known = {};
        state.items.forEach(function (item) { known[item.question_id] = true; });
        if (body.items.some(function (item) { return !known[item.question_id]; })) {
          state.overlayPinned = false;
        }
        state.etag = body.etag;
        state.items = body.items;
        if (state.selectedId && !byId(state.selectedId)) state.selectedId = null;
        state.loaded = true;
        render();
      })
      .catch(function () {});
  }

  /* Arrow keys: in the list they move the selection; in the spotlight they
     walk the current ranking. Conventional, and mirrored by buttons. */
  function step(delta) {
    var list = visible();
    if (state.mode === "spotlight") {
      var index = list.indexOf(byId(state.spotlightId)) + delta;
      var next = list[Math.max(0, Math.min(list.length - 1, index))];
      if (next && next.question_id !== state.spotlightId) swapSpotlight(next.question_id);
      return;
    }
    var rows = shown();
    if (!rows.length) return;
    var at = -1;
    rows.forEach(function (item, i) { if (item.question_id === state.selectedId) at = i; });
    var to = at === -1 ? (delta > 0 ? 0 : rows.length - 1) : Math.max(0, Math.min(rows.length - 1, at + delta));
    state.selectedId = rows[to].question_id;
    render();
  }

  function swapSpotlight(id) {
    state.spotlightId = id;
    if (!MOTION) return render();
    var stage = $("stage");
    stage.classList.add("swapping");
    setTimeout(function () {
      render();
      stage.classList.remove("swapping");
    }, 220);
  }

  function enterSpotlight(item) {
    if (!item) return;
    state.spotlightId = item.question_id;
    state.mode = "spotlight";
    render();
  }

  function exitSpotlight() {
    state.mode = "list";
    state.selectedId = byId(state.spotlightId) ? state.spotlightId : null;
    state.spotlightId = null;
    render();
  }

  /* The toolbar is the only way in, so it opens on the question the room
     voted to the top; prev/next walk from there. */
  function toggleSpotlight() {
    if (state.mode === "spotlight") return exitSpotlight();
    enterSpotlight(visible()[0]);
  }

  /* Marking answered removes the card. Slide it out before the
     list closes ranks, so the queue visibly shrinks instead of glitching. */
  function dismiss(item, done) {
    var li = $("plist").querySelector('[data-qid="' + item.question_id + '"]');
    if (!MOTION || !li) return done();
    li.classList.add("leaving");
    setTimeout(done, 200);
  }

  /* Light by default: a projector renders white as "screen off", and dark
     slides wash out in a lit room. Dark is an explicit choice, kept across
     sessions for the hosts who present from an OLED in a dim studio. */
  function applyTheme(theme) {
    document.documentElement.classList.toggle("theme-dark", theme === "dark");
    document.documentElement.classList.toggle("theme-light", theme !== "dark");
    var color = theme === "dark" ? "#0d1220" : "#ffffff";
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    Array.prototype.forEach.call(metas, function (meta) { meta.setAttribute("content", color); });
  }

  function toggleTheme() {
    var dark = !document.documentElement.classList.contains("theme-dark");
    applyTheme(dark ? "dark" : "light");
    try { localStorage.setItem("dq_present_theme", dark ? "dark" : "light"); } catch (e) {}
    paintToolbar();
  }

  function closeOverlay() {
    state.overlayPinned = false;
    state.overlayDismissed = true;
    render();
  }

  function toggleOverlay() {
    if ($("overlay").classList.contains("show")) return closeOverlay();
    state.overlayPinned = true;
    render();
  }

  /* ---- wiring ---- */

  document.addEventListener("keydown", function (event) {
    switch (event.key) {
      case "ArrowRight": case "ArrowDown": event.preventDefault(); step(1); break;
      case "ArrowLeft": case "ArrowUp": event.preventDefault(); step(-1); break;
      case "Escape":
        if ($("overlay").classList.contains("show")) closeOverlay();
        else if (state.mode === "spotlight") exitSpotlight();
        break;
    }
  });

  $("tb-undo").addEventListener("click", undo);
  $("tb-spot").addEventListener("click", toggleSpotlight);
  $("tb-qr").addEventListener("click", toggleOverlay);
  $("tb-theme").addEventListener("click", toggleTheme);
  $("tb-full").addEventListener("click", function () {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  });
  document.addEventListener("fullscreenchange", paintToolbar);
  $("overlay").addEventListener("click", closeOverlay);
  $("overlay-close").innerHTML = I.close;
  $("tb-undo").innerHTML = I.undo + "<span>Undo</span>";
  $("tb-undo").setAttribute("aria-label", "Undo the last mark answered");
  $("tb-qr").innerHTML = I.qr + "<span>QR code</span>";
  $("tb-qr").setAttribute("aria-label", "Show the join QR code full screen");
  $("tb-full").setAttribute("aria-label", "Toggle browser fullscreen");

  if (new URLSearchParams(location.search).get("theme") === "dark") applyTheme("dark");

  var shortUrl = CONFIG.url.replace(/^https:\/\//, "");
  $("session-title").textContent = CONFIG.title || "";
  $("join-url").textContent = shortUrl;
  $("overlay-url").textContent = shortUrl;
  fetch("/r/" + CONFIG.slug + "/qr.svg").then(function (r) { return r.text(); }).then(function (svg) {
    $("qr").innerHTML = svg;
    $("qr-big").innerHTML = svg;
  });

  paintToolbar();
  refresh();
  /* One client — the host's screen — so a 1s poll is cheap: almost every
     response is a 304 and renders nothing. The room view stays at 4s
     because that poll is multiplied by the whole audience (spec §5.1). */
  setInterval(function () { if (!document.hidden) refresh(); }, 1000);
})();
