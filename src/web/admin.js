/* Admin console. One page, two views, chosen by the path. */
(function () {
  "use strict";

  var API = "/api/v1";
  var roomId = (location.pathname.match(/^\/admin\/rooms\/([^/]+)/) || [])[1];
  var toastEl = document.getElementById("toast");
  var state = { room: null, filter: "all", items: [], etag: null, armedDelete: null, busy: {} };

  function svg(paths) {
    return '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      paths + "</svg>";
  }

  /* The moderation glyphs are presentation mode's, verbatim: the host runs
     both surfaces in the same session, so one vocabulary. */
  var I = {
    sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 ' +
      '17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>'),
    moon: svg('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'),
    check: svg('<path d="M20 6 9 17l-5-5"/>'),
    pin: svg('<path d="M9 4h6"/><path d="M10 4v5l-3 3v2h10v-2l-3-3V4"/><path d="M12 14v7"/>'),
    eyeOff: svg('<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 ' +
      '5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 ' +
      '3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="m1 1 22 22"/>'),
    trash: svg('<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>' +
      '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M10 11v6"/><path d="M14 11v6"/>')
  };

  function $(id) { return document.getElementById(id); }

  /* A toast, optionally carrying an undo — hiding removes the card from
     view, so its reversal must ride along rather than live on another tab. */
  function toast(message, undoFn) {
    toastEl.textContent = "";
    toastEl.appendChild(document.createTextNode(message));
    if (undoFn) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = "Undo";
      button.addEventListener("click", function () {
        toastEl.classList.remove("show");
        undoFn();
      });
      toastEl.appendChild(button);
    }
    toastEl.classList.add("show");
    clearTimeout(toastEl._timer);
    toastEl._timer = setTimeout(function () { toastEl.classList.remove("show"); }, undoFn ? 6000 : 2800);
  }

  function request(path, options) {
    options = options || {};
    options.headers = Object.assign({ "content-type": "application/json" }, options.headers || {});
    return fetch(API + path, options).then(function (res) {
      if (res.status === 401) { location.href = "/auth/login?next=" + encodeURIComponent(location.pathname); throw new Error("redirecting"); }
      if (res.status === 304) return { unchanged: true };
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (!res.ok) throw new Error((body.error && body.error.message) || "Request failed");
        return body;
      });
    });
  }

  function fail(error) { if (error && error.message !== "redirecting") toast(error.message); }

  function relative(iso) {
    if (!iso) return "";
    var seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h ago";
    return Math.floor(seconds / 86400) + "d ago";
  }

  function tag(kind, label) {
    var span = document.createElement("span");
    span.className = "tag" + (kind ? " " + kind : "");
    span.textContent = label;
    return span;
  }

  /* ---- theme: system by default, pinned once the user picks ---- */

  function effectiveTheme() {
    var root = document.documentElement.classList;
    if (root.contains("theme-dark")) return "dark";
    if (root.contains("theme-light")) return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function paintThemeToggle() {
    var dark = effectiveTheme() === "dark";
    $("theme-toggle").innerHTML = dark ? I.sun : I.moon;
    $("theme-toggle").setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  }

  function toggleTheme() {
    var next = effectiveTheme() === "dark" ? "light" : "dark";
    document.documentElement.classList.remove("theme-dark", "theme-light");
    document.documentElement.classList.add("theme-" + next);
    try { localStorage.setItem("dq_theme", next); } catch (e) {}
    var color = next === "dark" ? "#0d1220" : "#f6f8fb";
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    Array.prototype.forEach.call(metas, function (meta) { meta.setAttribute("content", color); });
    paintThemeToggle();
  }

  /* ---- room list ---- */

  var GROUPS = [["open", "Open"], ["draft", "Draft"], ["closed", "Closed"], ["archived", "Archived"]];

  function renderRooms(items) {
    var host = $("rooms");
    host.textContent = "";
    if (!items.length) {
      host.innerHTML = '<div class="empty"><h2>No rooms yet</h2><p>Create one above.</p></div>';
      return;
    }
    GROUPS.forEach(function (group) {
      var inGroup = items.filter(function (room) { return room.state === group[0]; });
      if (!inGroup.length) return;
      var heading = document.createElement("div");
      heading.className = "group-heading";
      heading.textContent = group[1] + " · " + inGroup.length;
      host.appendChild(heading);

      inGroup.forEach(function (room) {
        var card = document.createElement("div");
        card.className = "card room-card row wrapping";
        var link = document.createElement("a");
        // Stretched so the whole card is the hit target, not just the words.
        link.className = "stretched";
        link.href = "/admin/rooms/" + room.room_id;
        link.textContent = room.title;
        link.style.fontWeight = "600";
        var meta = document.createElement("div");
        meta.className = "muted";
        meta.style.width = "100%";
        meta.textContent = "/r/" + room.slug + " · " +
          room.counts.questions + (room.counts.questions === 1 ? " question, " : " questions, ") +
          room.counts.answered + " answered";
        card.appendChild(link);
        card.appendChild(meta);
        host.appendChild(card);
      });
    });
  }

  function loadRooms() {
    request("/rooms").then(function (body) { renderRooms(body.items || []); }).catch(fail);
  }

  function createRoom() {
    var title = $("new-title").value.trim();
    if (!title) return toast("A title is required.");
    var payload = { title: title, state: $("new-state").value };
    var slug = $("new-slug").value.trim();
    if (slug) payload.slug = slug;
    var hours = $("new-expiry").value;
    if (hours) payload.expires_at = new Date(Date.now() + parseInt(hours, 10) * 3600000).toISOString();

    $("create").disabled = true;
    request("/rooms", { method: "POST", body: JSON.stringify(payload) })
      .then(function (room) { location.href = "/admin/rooms/" + room.room_id; })
      .catch(fail)
      .then(function () { $("create").disabled = false; });
  }

  function loadKeys() {
    request("/api-keys").then(function (body) {
      var items = body.items || [];
      // No rows means no chrome: headers labelling nothing are noise.
      $("keys").hidden = !items.length;
      $("keys-empty").hidden = !!items.length;
      if (!items.length) return;
      var table = $("keys");
      table.innerHTML = "<tr><th>Name</th><th>Created</th><th>Last used</th><th></th></tr>";
      items.forEach(function (key) {
        var row = table.insertRow();
        row.insertCell().textContent = key.name;
        row.insertCell().textContent = (key.created_at || "").slice(0, 10);
        row.insertCell().textContent = key.last_used_at ? key.last_used_at.slice(0, 10) : "never";
        var cell = row.insertCell();
        var button = document.createElement("button");
        button.className = "ghost small";
        button.textContent = "Revoke";
        button.addEventListener("click", function () {
          request("/api-keys/" + key.key_id, { method: "DELETE" }).then(loadKeys).catch(fail);
        });
        cell.appendChild(button);
      });
    }).catch(fail);
  }

  function createKey() {
    request("/api-keys", { method: "POST", body: JSON.stringify({ name: $("key-name").value.trim() || "unnamed" }) })
      .then(function (key) {
        var box = $("key-reveal");
        box.hidden = false;
        box.className = "banner warn mono";
        box.textContent = key.key + "  — copy it now, it is not shown again";
        $("key-name").value = "";
        loadKeys();
      }).catch(fail);
  }

  /* ---- room detail ---- */

  function loadCohosts() {
    request("/rooms/" + roomId + "/cohosts").then(function (body) {
      var items = body.items || [];
      $("cohosts").hidden = !items.length;
      $("cohosts-empty").hidden = !!items.length;
      if (!items.length) return;
      var table = $("cohosts");
      table.innerHTML = "<tr><th>Name</th><th>Passcode</th><th></th></tr>";
      items.forEach(function (invite) {
        var row = table.insertRow();
        var nameCell = row.insertCell();
        nameCell.className = "mono";
        nameCell.textContent = invite.name;
        var passCell = row.insertCell();
        passCell.className = "mono";
        passCell.textContent = invite.passcode;

        var cell = row.insertCell();
        var copy = document.createElement("button");
        copy.className = "ghost small";
        copy.textContent = "Copy both";
        copy.addEventListener("click", function () {
          // The link is useless without the passcode, so copy them together.
          navigator.clipboard
            .writeText(invite.join_url + "\nPasscode: " + invite.passcode)
            .then(function () { toast("Link and passcode copied"); });
        });
        var revoke = document.createElement("button");
        revoke.className = "ghost small";
        revoke.textContent = "Revoke";
        revoke.addEventListener("click", function () {
          request("/rooms/" + roomId + "/cohosts/" + invite.invite_id, { method: "DELETE" })
            .then(loadCohosts).catch(fail);
        });
        cell.appendChild(copy);
        cell.appendChild(revoke);
      });
    }).catch(fail);
  }

  function createCohost() {
    request("/rooms/" + roomId + "/cohosts", {
      method: "POST",
      body: JSON.stringify({
        name: $("cohost-name").value.trim() || null,
        passcode: $("cohost-passcode").value.trim() || null
      })
    }).then(function (invite) {
      ["cohost-name", "cohost-passcode"].forEach(function (id) { $(id).value = ""; });
      toast("Invite created — passcode " + invite.passcode);
      loadCohosts();
    }).catch(fail);
  }

  function renderRoom(room) {
    state.room = room;
    // A co-host sees the questions and the share panel, and nothing that would
    // let them change the room or widen their own access.
    // A session code is admin of this session: settings and lifecycle
    // included. What it cannot do is hand that access on to anyone else.
    var isCohost = room.role === "cohost";
    $("cohost-card").hidden = isCohost;
    $("cohost-notice").hidden = !isCohost;
    if (isCohost) {
      // The console list is owner territory; a co-host has exactly one room.
      Array.prototype.forEach.call(
        document.querySelectorAll('a[href="/admin"]'),
        function (link) { link.hidden = true; }
      );
    }
    $("room-title").textContent = room.title;
    $("room-sub").textContent = room.state + " · " + room.counts.questions +
      (room.counts.questions === 1 ? " question" : " questions") +
      (room.expires_at ? " · closes " + new Date(room.expires_at).toLocaleString() : "");
    $("room-owner").textContent = "Owner: " + room.owner;
    $("public-link").href = room.url;
    $("public-link").textContent = room.url;
    $("present").href = "/admin/rooms/" + room.room_id + "/present";
    $("qr-png").href = "/r/" + room.slug + "/qr.png?size=1024";
    $("qr-svg").href = "/r/" + room.slug + "/qr.svg";
    $("state").value = room.state;
    $("listed").checked = room.settings.listed !== false;

    fetch("/r/" + room.slug + "/qr.svg").then(function (r) { return r.text(); })
      .then(function (svg) { $("qr").innerHTML = svg; });
  }

  function patchRoom(payload) {
    request("/rooms/" + roomId, { method: "PATCH", body: JSON.stringify(payload) })
      .then(renderRoom).catch(fail);
  }

  /* Empty states are written per tab: each one says what would appear
     here and what causes it, not a generic "nothing". */
  var EMPTY = {
    all: ["No questions yet",
      "Share the link below — questions appear the moment they are asked."],
    answered: ["Nothing answered yet",
      "Mark a question answered and it moves to this tab."],
    hidden: ["Nothing hidden",
      "Hide a question to park it here without deleting it."]
  };

  function renderQuestions() {
    var filtered = state.items.filter(function (item) {
      if (state.filter === "all") return item.status === "visible" || item.status === "answered";
      if (state.filter === "answered") return item.status === "answered";
      return item.status === "hidden";
    });
    if (state.filter === "all") {
      // The console's job is what to answer next: done items sink below the
      // open queue instead of interleaving with it by score. Stable sort, so
      // the server's ranking holds within each half.
      filtered.sort(function (a, b) {
        return (a.status === "answered") - (b.status === "answered");
      });
    }

    $("qempty").hidden = filtered.length > 0;
    if (!filtered.length) {
      $("qempty-title").textContent = EMPTY[state.filter][0];
      $("qempty-body").textContent = EMPTY[state.filter][1];
    }
    var list = $("qlist");
    list.textContent = "";

    filtered.forEach(function (item) {
      var li = document.createElement("li");
      li.className = "q" + (item.status === "answered" ? " answered" : "") + (item.pinned ? " pinned" : "");

      var text = document.createElement("div");
      text.className = "text";
      text.textContent = item.text;

      var meta = document.createElement("div");
      meta.className = "meta";
      var who = document.createElement("span");
      who.textContent = (item.author_name || "Anonymous") + " · " + relative(item.created_at);
      meta.appendChild(who);
      // States are tags, matching the room view: text and shape, never
      // position or hue alone.
      if (item.pinned) meta.appendChild(tag("pinned", "Pinned"));
      if (item.status === "answered") meta.appendChild(tag("answered", "Answered"));
      if (item.status === "hidden") meta.appendChild(tag("hidden", "Hidden"));

      var score = document.createElement("div");
      // Displays a score; it is not a control, so it must not look like one.
      score.className = "vote static";
      score.setAttribute("aria-hidden", "true");
      score.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M6 14l6-7 6 7"/></svg><span>' + item.score + "</span>";

      /* Moderation is routine — twelve times a session — so it whispers:
         the quiet icon squares from presentation mode, sharing the foot
         line with the score. The question text keeps the card. */
      var foot = document.createElement("div");
      foot.className = "q-foot";
      var actions = document.createElement("div");
      actions.className = "actions";
      [
        item.status === "answered"
          ? ["Unanswer", I.check, { status: "visible" }, true]
          : ["Mark answered", I.check, { status: "answered" }, false],
        [item.pinned ? "Unpin" : "Pin", I.pin, { pinned: !item.pinned }, !!item.pinned],
        item.status === "hidden"
          ? ["Restore", I.eyeOff, { status: "visible" }, true]
          // Hiding removes the card from the current tab, so the undo rides
          // the confirmation toast — one tap to reverse.
          : ["Hide", I.eyeOff, { status: "hidden" }, false, "Question hidden"]
      ].forEach(function (entry) {
        actions.appendChild(actionButton(item, entry[0], entry[1], entry[2], entry[3], entry[4]));
      });
      actions.appendChild(deleteButton(item));
      foot.appendChild(actions);
      foot.appendChild(score);

      li.appendChild(text);
      li.appendChild(meta);
      li.appendChild(foot);
      list.appendChild(li);
    });
  }

  /* The click is acknowledged on the click: apply locally, reconcile after.
     While the PATCH is in flight the row's buttons disable and the acting
     one shows a ring, so a slow network reads as busy, not broken. */
  function performAction(item, name, payload, after) {
    QNA.patch({
      item: item,
      payload: payload,
      busy: state.busy,
      action: name,
      send: function () {
        return request("/rooms/" + roomId + "/questions/" + item.question_id, {
          method: "PATCH", body: JSON.stringify(payload)
        });
      },
      render: renderQuestions,
      done: function () { state.etag = null; refresh(); if (after) after(); },
      fail: fail
    });
  }

  /* Icon-only, named for the screen reader and the tooltip. The armed
     delete below is the one action that speaks in words instead — a
     destructive confirm should be read, not recognised. */
  function actionButton(item, name, icon, payload, pressed, undoLabel) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "icon-btn";
    button.innerHTML = icon;
    button.setAttribute("aria-label", name);
    button.title = name;
    // Answered, pinned, hidden are toggles; pressed shows which side is on.
    button.setAttribute("aria-pressed", pressed ? "true" : "false");
    if (state.busy[item.question_id]) {
      button.disabled = true;
      if (state.busy[item.question_id] === name) button.classList.add("busy");
    }
    button.addEventListener("click", function () {
      var after = undoLabel ? function () {
        toast(undoLabel, function () {
          performAction(item, "Undo", { status: "visible" });
        });
      } : null;
      performAction(item, name, payload, after);
    });
    return button;
  }

  function refresh() {
    // An in-flight optimistic change must not be stomped by the poll.
    if (Object.keys(state.busy).length) return Promise.resolve();
    var headers = state.etag ? { "if-none-match": state.etag } : {};
    return request("/rooms/" + roomId + "/questions?status=visible,answered,hidden", { headers: headers })
      .then(function (body) {
        if (body.unchanged) return;
        if (Object.keys(state.busy).length) return;
        state.etag = body.etag;
        state.items = body.items || [];
        renderQuestions();
      }).catch(function () {});
  }

  /* Deleting is irreversible, so the first click only arms the button. */
  function deleteButton(item) {
    var button = document.createElement("button");
    button.type = "button";
    var armed = state.armedDelete === item.question_id;
    if (armed) {
      button.className = "small arm";
      button.textContent = "Really delete?";
    } else {
      button.className = "icon-btn";
      button.innerHTML = I.trash;
      button.setAttribute("aria-label", "Delete");
      button.title = "Delete";
    }
    if (state.busy[item.question_id]) {
      button.disabled = true;
      if (state.busy[item.question_id] === "Delete") button.classList.add("busy");
    }
    button.addEventListener("click", function () {
      if (state.armedDelete !== item.question_id) {
        state.armedDelete = item.question_id;
        renderQuestions();
        setTimeout(function () {
          if (state.armedDelete === item.question_id) { state.armedDelete = null; renderQuestions(); }
        }, 3000);
        return;
      }
      state.armedDelete = null;
      performAction(item, "Delete", { status: "deleted" });
    });
    return button;
  }

  function selectFilter(name) {
    state.filter = name;
    ["all", "answered", "hidden"].forEach(function (key) {
      $("f-" + key).setAttribute("aria-pressed", key === name ? "true" : "false");
    });
    renderQuestions();
  }

  /* ---- boot ---- */

  paintThemeToggle();
  $("theme-toggle").addEventListener("click", toggleTheme);

  if (roomId) {
    $("view-room").hidden = false;
    request("/rooms/" + roomId).then(function (room) {
      renderRoom(room);
      if (room.role !== "cohost") loadCohosts();
    }).catch(fail);
    refresh();
    setInterval(function () { if (!document.hidden) refresh(); }, 5000);
    // Relative timestamps go stale behind 304s, which is most of the time.
    setInterval(function () { if (state.items.length) renderQuestions(); }, 60000);

    $("state").addEventListener("change", function () { patchRoom({ state: this.value }); });
    $("listed").addEventListener("change", function () { patchRoom({ settings: { listed: this.checked } }); });
    $("copy-link").addEventListener("click", function () {
      navigator.clipboard.writeText(state.room.url).then(function () { toast("Link copied"); });
    });
    $("create-cohost").addEventListener("click", createCohost);
    ["all", "answered", "hidden"].forEach(function (key) {
      $("f-" + key).addEventListener("click", function () { selectFilter(key); });
    });
  } else {
    $("view-list").hidden = false;
    loadRooms();
    loadKeys();
    $("create").addEventListener("click", createRoom);
    $("create-key").addEventListener("click", createKey);
  }
})();
