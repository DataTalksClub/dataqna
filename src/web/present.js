/* Presentation mode. Projected, so it is keyboard-only and never reorders
   the question currently on screen — reordering applies to the queue, and
   takes effect when the host advances. */
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("config").textContent);
  var API = "/api/v1/rooms/" + CONFIG.room_id;
  var MOTION = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;
  var UPCOMING_SHOWN = 5;

  var state = {
    queue: [],
    currentId: null,
    etag: null,
    lastShownId: null,
    lastAction: null,
    overlayPinned: false,
    footTimer: null
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

  function indexOfCurrent() {
    for (var i = 0; i < state.queue.length; i++) {
      if (state.queue[i].question_id === state.currentId) return i;
    }
    return -1;
  }

  function current() {
    var index = indexOfCurrent();
    return index === -1 ? state.queue[0] : state.queue[index];
  }

  /* A host cue, not audience chrome: small, low-contrast, and gone in a moment. */
  function cue(message) {
    var node = $("cue");
    node.textContent = message;
    node.classList.add("show");
    clearTimeout(node._timer);
    node._timer = setTimeout(function () { node.classList.remove("show"); }, 2600);
  }

  function paint() {
    var item = current();
    if (!item) {
      $("q-text").textContent = "No questions yet.";
      $("q-meta").textContent = "";
      $("upcoming").textContent = "";
      $("remaining").textContent = "0";
      return;
    }
    state.currentId = item.question_id;
    $("q-text").textContent = item.text;

    $("q-meta").innerHTML = "";
    var score = document.createElement("span");
    score.className = "q-score";
    score.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M6 14l6-7 6 7"/></svg><span>' + item.score + "</span>";
    var who = document.createElement("span");
    who.textContent = (item.author_name || "Anonymous") + (item.pinned ? " · pinned" : "");
    $("q-meta").appendChild(score);
    $("q-meta").appendChild(who);

    var index = indexOfCurrent();
    var rest = state.queue.slice(index + 1);
    $("remaining").textContent = String(rest.length);
    var list = $("upcoming");
    list.textContent = "";
    rest.slice(0, UPCOMING_SHOWN).forEach(function (entry) {
      var li = document.createElement("li");
      li.textContent = entry.text.length > 80 ? entry.text.slice(0, 80) + "…" : entry.text;
      list.appendChild(li);
    });

    // Nobody is joining a room that has questions in it yet — but at session
    // start, the QR is the only thing on screen worth looking at.
    if (!state.overlayPinned) $("overlay").classList.toggle("show", state.queue.length === 0);
  }

  function render() {
    var item = current();
    var changed = item && item.question_id !== state.lastShownId;
    if (!changed || !MOTION) {
      paint();
      state.lastShownId = item ? item.question_id : null;
      return;
    }
    var main = $("main");
    main.classList.add("swapping");
    setTimeout(function () {
      paint();
      state.lastShownId = item.question_id;
      main.classList.remove("swapping");
    }, 250);
  }

  function refresh() {
    var headers = state.etag ? { "if-none-match": state.etag } : {};
    return request(API + "/questions?sort=popular&status=visible", { headers: headers })
      .then(function (body) {
        if (body.unchanged || !body.items) return;
        state.etag = body.etag;
        var incoming = body.items;
        var index = indexOfCurrent();
        if (index === -1) {
          state.queue = incoming;
        } else {
          var head = state.queue.slice(0, index + 1).map(function (q) { return q.question_id; });
          var tail = incoming.filter(function (q) { return head.indexOf(q.question_id) === -1; });
          var kept = state.queue.slice(0, index + 1).map(function (q) {
            var fresh = incoming.filter(function (i) { return i.question_id === q.question_id; })[0];
            return fresh || q;
          });
          state.queue = kept.concat(tail);
        }
        render();
      });
  }

  function move(delta) {
    var index = indexOfCurrent();
    var next = Math.max(0, Math.min(state.queue.length - 1, index + delta));
    if (state.queue[next]) {
      state.currentId = state.queue[next].question_id;
      render();
    }
  }

  function act(payload, advance, label) {
    var item = current();
    if (!item) return;
    if (advance) state.lastAction = { question_id: item.question_id, text: item.text };
    request(API + "/questions/" + item.question_id, { method: "PATCH", body: JSON.stringify(payload) })
      .then(function () {
        state.etag = null;
        if (advance) {
          var index = indexOfCurrent();
          state.queue.splice(index, 1);
          state.currentId = state.queue[index] ? state.queue[index].question_id : null;
        }
        render();
        if (label) cue(label);
        return refresh();
      });
  }

  /* A mis-keyed `h` silently removes an attendee's question from a projected
     screen. One level of undo costs nothing and prevents a bad moment. */
  function undo() {
    if (!state.lastAction) return cue("Nothing to undo");
    var target = state.lastAction;
    state.lastAction = null;
    request(API + "/questions/" + target.question_id, {
      method: "PATCH", body: JSON.stringify({ status: "visible" })
    }).then(function () {
      state.etag = null;
      cue("Restored");
      return refresh();
    });
  }

  function showFoot() {
    var foot = $("foot");
    foot.classList.remove("faded");
    clearTimeout(state.footTimer);
    state.footTimer = setTimeout(function () { foot.classList.add("faded"); }, 5000);
  }

  document.addEventListener("keydown", function (event) {
    showFoot();
    switch (event.key) {
      case "ArrowRight": case " ": event.preventDefault(); move(1); break;
      case "ArrowLeft": event.preventDefault(); move(-1); break;
      case "Enter": event.preventDefault(); act({ status: "answered" }, true, "Marked answered · u to undo"); break;
      case "p": act({ pinned: !(current() || {}).pinned }, false, "Pin toggled"); break;
      case "h": act({ status: "hidden" }, true, "Hidden · u to undo"); break;
      case "u": undo(); break;
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
          $("overlay").classList.remove("show");
        } else {
          location.href = "/admin/rooms/" + CONFIG.room_id;
        }
        break;
    }
  });

  document.addEventListener("mousemove", showFoot);

  var shortUrl = CONFIG.url.replace(/^https:\/\//, "");
  $("room-title").textContent = CONFIG.title || "";
  $("join-url").textContent = shortUrl;
  $("overlay-url").textContent = shortUrl;
  $("overlay-code").textContent = "or " + CONFIG.url.replace(/\/r\/.*$/, "/r/") + CONFIG.code;
  fetch("/r/" + CONFIG.slug + "/qr.svg").then(function (r) { return r.text(); }).then(function (svg) {
    $("qr").innerHTML = svg;
    $("qr-big").innerHTML = svg;
  });

  refresh();
  showFoot();
  setInterval(function () { if (!document.hidden) refresh(); }, 4000);
})();
