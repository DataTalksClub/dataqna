/* Presentation mode. Projected, so it is keyboard-only and never reorders
   the question currently on screen — reordering applies to the queue, and
   takes effect when the host advances. */
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("config").textContent);
  var API = "/api/v1/rooms/" + CONFIG.room_id;

  var state = { queue: [], currentId: null, etag: null };

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

  function render() {
    var item = current();
    if (!item) {
      $("q-text").textContent = state.queue.length ? "" : "No questions yet.";
      $("q-meta").textContent = "";
      $("upcoming").textContent = "";
      $("remaining").textContent = "0";
      return;
    }
    state.currentId = item.question_id;
    $("q-text").textContent = item.text;
    $("q-meta").textContent = (item.author_name || "Anonymous") + " · " + item.score +
      (item.score === 1 ? " vote" : " votes") + (item.pinned ? " · pinned" : "");

    var index = indexOfCurrent();
    var rest = state.queue.slice(index + 1);
    $("remaining").textContent = String(rest.length);
    var list = $("upcoming");
    list.textContent = "";
    rest.slice(0, 8).forEach(function (entry) {
      var li = document.createElement("li");
      li.textContent = entry.text.length > 90 ? entry.text.slice(0, 90) + "…" : entry.text;
      list.appendChild(li);
    });
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
          // Keep the question on screen exactly where it is; let everything
          // after it re-rank freely.
          var pinnedCurrent = state.queue[index];
          var head = state.queue.slice(0, index + 1).map(function (q) { return q.question_id; });
          var tail = incoming.filter(function (q) { return head.indexOf(q.question_id) === -1; });
          var kept = state.queue.slice(0, index + 1).map(function (q) {
            var fresh = incoming.filter(function (i) { return i.question_id === q.question_id; })[0];
            return fresh || q;
          });
          state.queue = kept.concat(tail);
          if (!state.queue.length) state.queue = [pinnedCurrent];
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

  function act(payload, advance) {
    var item = current();
    if (!item) return;
    request(API + "/questions/" + item.question_id, { method: "PATCH", body: JSON.stringify(payload) })
      .then(function () {
        state.etag = null;
        if (advance) {
          var index = indexOfCurrent();
          state.queue.splice(index, 1);
          state.currentId = state.queue[index] ? state.queue[index].question_id : null;
        }
        render();
        return refresh();
      });
  }

  document.addEventListener("keydown", function (event) {
    switch (event.key) {
      case "ArrowRight": case " ": event.preventDefault(); move(1); break;
      case "ArrowLeft": event.preventDefault(); move(-1); break;
      case "Enter": event.preventDefault(); act({ status: "answered" }, true); break;
      case "p": act({ pinned: !(current() || {}).pinned }, false); break;
      case "h": act({ status: "hidden" }, true); break;
      case "q": $("overlay").classList.toggle("show"); break;
      case "f":
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen();
        break;
      case "Escape":
        if ($("overlay").classList.contains("show")) $("overlay").classList.remove("show");
        else location.href = "/admin/rooms/" + CONFIG.room_id;
        break;
    }
  });

  $("join-url").textContent = CONFIG.url.replace(/^https:\/\//, "");
  $("overlay-url").textContent = CONFIG.url.replace(/^https:\/\//, "");
  $("join-code").textContent = CONFIG.code;
  fetch("/r/" + CONFIG.slug + "/qr.svg").then(function (r) { return r.text(); }).then(function (svg) {
    $("qr").innerHTML = svg;
    $("qr-big").innerHTML = svg;
  });

  refresh();
  setInterval(function () { if (!document.hidden) refresh(); }, 4000);
})();
