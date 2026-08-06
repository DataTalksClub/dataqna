/* Presentation mode. Projected, keyboard-only, two states in one frame:

   The resting state is the ranked list — the audience votes because they can
   see what is winning, so the list re-sorts live and movement is animated to
   stay legible. Spotlight blows one question up; it is entered deliberately
   (Enter) and the spotlit question never moves underneath the host — the
   ranking only matters again once they return to the list. */
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("config").textContent);
  var API = "/api/v1/rooms/" + CONFIG.room_id;
  var MOTION = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;
  var MAX_ROWS = 8;
  var DENSE_AT = 6;

  var HINTS = {
    list: "↑↓ select · Enter spotlight · a answered · p pin · h hide · u undo · q QR · d theme · f fullscreen · Esc exit",
    spotlight: "→ next · ← previous · Enter answered · p pin · h hide · u undo · Esc back to list"
  };

  var state = {
    items: [],
    etag: null,
    mode: "list",
    selectedId: null,
    spotlightId: null,
    lastAction: null,
    overlayPinned: false,
    footTimer: null,
    loaded: false,
    painted: false,
    scores: {}
  };

  function $(id) { return document.getElementById(id); }

  function request(path, options) {
    options = options || {};
    options.headers = Object.assign({ "content-type": "application/json" }, options.headers || {});
    return fetch(path, options).then(function (res) {
      if (res.status === 304) return { unchanged: true };
      return res.json().catch(function () { return {}; });
    });
  }

  function byId(id) {
    for (var i = 0; i < state.items.length; i++) {
      if (state.items[i].question_id === id) return state.items[i];
    }
    return null;
  }

  function indexOf(id) {
    for (var i = 0; i < state.items.length; i++) {
      if (state.items[i].question_id === id) return i;
    }
    return -1;
  }

  function shown() { return state.items.slice(0, MAX_ROWS); }

  /* The question the next keystroke applies to: the selection if there is
     one, else the leader — the host works the list top-down. */
  function target() {
    if (state.mode === "spotlight") return byId(state.spotlightId);
    return byId(state.selectedId) || state.items[0] || null;
  }

  /* A host cue, not audience chrome: small, low-contrast, and gone in a moment. */
  function cue(message) {
    var node = $("cue");
    node.textContent = message;
    node.classList.add("show");
    clearTimeout(node._timer);
    node._timer = setTimeout(function () { node.classList.remove("show"); }, 2600);
  }

  var CHEVRON = '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true"><path d="M6 14l6-7 6 7"/></svg>';

  function buildRow(item) {
    var li = document.createElement("li");
    li.dataset.qid = item.question_id;
    if (item.pinned) li.classList.add("pinned");
    if (item.question_id === state.selectedId) li.classList.add("selected");

    var score = document.createElement("div");
    score.className = "p-score";
    score.innerHTML = CHEVRON + '<span class="count">' + item.score + "</span>";

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
    if (item.pinned) {
      var pin = document.createElement("span");
      pin.className = "p-pin";
      pin.textContent = "Pinned";
      meta.appendChild(pin);
    }
    body.appendChild(text);
    body.appendChild(meta);
    li.appendChild(score);
    li.appendChild(body);
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

    list.classList.toggle("dense", rows.length >= DENSE_AT);
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

    var extra = state.items.length - rows.length;
    $("more").hidden = extra <= 0;
    if (extra > 0) $("more").textContent = "+ " + extra + " more in the queue";

    $("progress").textContent = state.items.length
      ? state.items.length + (state.items.length === 1 ? " question" : " questions")
      : "";
    state.painted = true;
  }

  function renderStage() {
    var item = byId(state.spotlightId);
    if (!item) return exitSpotlight();
    $("q-text").textContent = item.text;
    $("q-meta").innerHTML = "";
    var score = document.createElement("span");
    score.className = "q-score";
    score.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M6 14l6-7 6 7"/></svg><span>' + item.score + "</span>";
    var who = document.createElement("span");
    who.textContent = (item.author_name || "Anonymous") + (item.pinned ? " · pinned" : "");
    $("q-meta").appendChild(score);
    $("q-meta").appendChild(who);
    $("progress").textContent = (indexOf(item.question_id) + 1) + " of " + state.items.length;
  }

  function render() {
    var inSpotlight = state.mode === "spotlight" && byId(state.spotlightId);
    if (state.mode === "spotlight" && !inSpotlight) state.mode = "list";

    $("plist").hidden = state.mode !== "list";
    if (state.mode !== "list") $("more").hidden = true;
    $("stage").hidden = state.mode !== "spotlight";
    $("hints").textContent = HINTS[state.mode];

    if (state.mode === "spotlight") renderStage();
    else renderList();

    // Nobody is joining a room that already has questions — but at the start,
    // the QR is the only thing on screen worth looking at.
    if (!state.overlayPinned) {
      $("overlay").classList.toggle("show", state.items.length === 0 && state.loaded);
    }
  }

  function refresh() {
    var headers = state.etag ? { "if-none-match": state.etag } : {};
    return request(API + "/questions?sort=popular&status=visible", { headers: headers })
      .then(function (body) {
        if (body.unchanged || !body.items) return;
        state.etag = body.etag;
        state.items = body.items;
        if (state.selectedId && !byId(state.selectedId)) state.selectedId = null;
        state.loaded = true;
        render();
      });
  }

  /* Arrow keys: in the list they move the selection; in the spotlight they
     walk the current ranking. */
  function move(delta) {
    if (state.mode === "spotlight") {
      var index = indexOf(state.spotlightId) + delta;
      var next = state.items[Math.max(0, Math.min(state.items.length - 1, index))];
      if (next && next.question_id !== state.spotlightId) {
        swapSpotlight(next.question_id);
      }
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

  function enterSpotlight() {
    var item = target();
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

  /* Marking answered or hiding removes the card. Slide it out before the
     list closes ranks, so the queue visibly shrinks instead of glitching. */
  function dismiss(item, done) {
    var li = $("plist").querySelector('[data-qid="' + item.question_id + '"]');
    var index = indexOf(item.question_id);
    var finish = function () {
      if (index !== -1) state.items.splice(index, 1);
      if (state.selectedId === item.question_id) state.selectedId = null;
      done();
    };
    if (!MOTION || state.mode !== "list" || !li) return finish();
    li.classList.add("leaving");
    setTimeout(finish, 200);
  }

  function act(payload, removes, label) {
    var item = target();
    if (!item) return;
    if (removes) state.lastAction = { question_id: item.question_id };
    var send = function () {
      request(API + "/questions/" + item.question_id, { method: "PATCH", body: JSON.stringify(payload) })
        .then(function () {
          state.etag = null;
          if (state.mode === "spotlight" && removes) exitSpotlight();
          else render();
          if (label) cue(label);
          return refresh();
        });
    };
    if (removes) dismiss(item, send);
    else send();
  }

  /* A mis-keyed `h` silently removes an attendee's question from a projected
     screen. One level of undo costs nothing and prevents a bad moment. */
  function undo() {
    if (!state.lastAction) return cue("Nothing to undo");
    var undoTarget = state.lastAction;
    state.lastAction = null;
    request(API + "/questions/" + undoTarget.question_id, {
      method: "PATCH", body: JSON.stringify({ status: "visible" })
    }).then(function () {
      state.etag = null;
      cue("Restored");
      return refresh();
    });
  }

  /* Light by default: a projector renders white as "screen off", and dark
     slides wash out in a lit room. Dark is an explicit choice (`d`), kept
     across sessions for the hosts who present from an OLED in a dim studio. */
  function applyTheme(theme) {
    document.documentElement.classList.toggle("theme-dark", theme === "dark");
    document.documentElement.classList.toggle("theme-light", theme !== "dark");
  }

  function toggleTheme() {
    var dark = !document.documentElement.classList.contains("theme-dark");
    applyTheme(dark ? "dark" : "light");
    try { localStorage.setItem("dq_present_theme", dark ? "dark" : "light"); } catch (e) {}
    cue(dark ? "Dark theme" : "Light theme");
  }

  function showFoot() {
    var hints = $("hints");
    hints.classList.remove("faded");
    clearTimeout(state.footTimer);
    state.footTimer = setTimeout(function () { hints.classList.add("faded"); }, 5000);
  }

  document.addEventListener("keydown", function (event) {
    showFoot();
    switch (event.key) {
      case "ArrowRight": case "ArrowDown": case " ": event.preventDefault(); move(1); break;
      case "ArrowLeft": case "ArrowUp": event.preventDefault(); move(-1); break;
      case "Enter":
        event.preventDefault();
        if (state.mode === "spotlight") act({ status: "answered" }, true, "Marked answered · u to undo");
        else enterSpotlight();
        break;
      case "a": act({ status: "answered" }, true, "Marked answered · u to undo"); break;
      case "p": act({ pinned: !(target() || {}).pinned }, false, "Pin toggled"); break;
      case "h": act({ status: "hidden" }, true, "Hidden · u to undo"); break;
      case "u": undo(); break;
      case "d": toggleTheme(); break;
      case "q":
        state.overlayPinned = !$("overlay").classList.contains("show");
        $("overlay").classList.toggle("show");
        break;
      case "f":
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen();
        break;
      case "Escape":
        if ($("overlay").classList.contains("show") && state.overlayPinned) {
          state.overlayPinned = false;
          render();
        } else if (state.mode === "spotlight") {
          exitSpotlight();
        } else {
          location.href = "/admin/rooms/" + CONFIG.room_id;
        }
        break;
    }
  });

  document.addEventListener("mousemove", showFoot);

  try {
    if (localStorage.getItem("dq_present_theme") === "dark") applyTheme("dark");
  } catch (e) {}
  if (new URLSearchParams(location.search).get("theme") === "dark") applyTheme("dark");

  var shortUrl = CONFIG.url.replace(/^https:\/\//, "");
  $("session-title").textContent = CONFIG.title || "";
  $("join-url").textContent = shortUrl;
  $("join-code").textContent = CONFIG.code;
  $("overlay-url").textContent = shortUrl;
  $("overlay-code").textContent = "Join code " + CONFIG.code;
  fetch("/r/" + CONFIG.slug + "/qr.svg").then(function (r) { return r.text(); }).then(function (svg) {
    $("qr").innerHTML = svg;
    $("qr-big").innerHTML = svg;
  });

  $("hints").textContent = HINTS.list;
  refresh();
  showFoot();
  setInterval(function () { if (!document.hidden) refresh(); }, 4000);
})();
