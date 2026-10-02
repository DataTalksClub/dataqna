/* Admin console. One page, two views, chosen by the path. */
(function () {
  "use strict";

  var API = "/api/v1";
  var roomId = (location.pathname.match(/^\/admin\/rooms\/([^/]+)/) || [])[1];
  var toastEl = document.getElementById("toast");
  var state = { room: null, filter: "all", items: [], etag: null, armedDelete: null, busy: {} };

  function svg(paths) {
    /* The family icon language: 16x16, stroke 1.5, round caps, no fills. */
    return '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" ' +
      'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      paths + "</svg>";
  }

  /* The moderation glyphs are presentation mode's, verbatim: the host runs
     both surfaces in the same session, so one vocabulary. */
  var I = {
    check: svg('<path d="M13 4.5 6.5 11 3 7.5"/>'),
    pin: svg('<path d="M6 2.5h4"/><path d="M6.5 2.5v3.2L4.3 8.3v1.2h7.4V8.3L9.5 5.7V2.5"/>' +
      '<path d="M8 9.5v4"/>'),
    trash: svg('<path d="M2.5 4h11"/><path d="M5.5 4V3a1.5 1.5 0 011.5-1.5h2A1.5 1.5 0 0110.5 3v1"/>' +
      '<path d="M12.5 4v8.5a1.5 1.5 0 01-1.5 1.5H5a1.5 1.5 0 01-1.5-1.5V4"/>' +
      '<path d="M6.5 7v4M9.5 7v4"/>')
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

  /* ---- room list ---- */

  var GROUPS = [["open", "Open"], ["draft", "Draft"], ["closed", "Closed"], ["archived", "Archived"]];
  /* Session states speak in the family's status badges: open is live
     (success), archived carries its pending deletion (danger); draft and
     closed are ordinary stops, so they stay neutral. */
  var STATE_TAGS = {
    open: ["open", "Open"],
    draft: ["", "Draft"],
    closed: ["", "Closed"],
    archived: ["archived", "Archived"]
  };

  var CHEVRON_RIGHT = '<svg class="row-chev" width="16" height="16" viewBox="0 0 16 16" fill="none" ' +
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M6 3l5 5-5 5"/></svg>';

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

      var panel = document.createElement("section");
      panel.className = "panel";
      var header = document.createElement("div");
      header.className = "panel-header";
      var heading = document.createElement("h2");
      heading.textContent = group[1];
      var count = document.createElement("span");
      count.className = "muted panel-hint";
      count.textContent = inGroup.length;
      header.appendChild(heading);
      header.appendChild(count);
      panel.appendChild(header);

      inGroup.forEach(function (room) {
        var row = document.createElement("div");
        row.className = "panel-row";
        var main = document.createElement("div");
        main.className = "row-main";
        var link = document.createElement("a");
        // Stretched so the whole row is the hit target, not just the words.
        link.className = "row-link stretched";
        link.href = "/admin/rooms/" + room.room_id;
        link.textContent = room.title;
        var meta = document.createElement("span");
        meta.className = "row-meta";
        meta.textContent = "/r/" + room.slug + " · " +
          room.counts.questions + (room.counts.questions === 1 ? " question, " : " questions, ") +
          room.counts.answered + " answered";
        main.appendChild(link);
        main.appendChild(meta);
        row.appendChild(main);
        row.insertAdjacentHTML("beforeend", CHEVRON_RIGHT);
        panel.appendChild(row);
      });
      host.appendChild(panel);
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
    // The description line carries provenance; the numbers below are the
    // strip's job, so they are not repeated here.
    $("room-sub").textContent = "/r/" + room.slug + " — hosted by " + room.owner;
    $("room-owner").textContent = "Owner: " + room.owner;
    var stateTag = STATE_TAGS[room.state] || ["", room.state];
    $("stat-questions").textContent = room.counts.questions;
    $("stat-answered").textContent = room.counts.answered;
    $("stat-state").innerHTML = "";
    var badge = document.createElement("span");
    badge.className = "tag" + (stateTag[0] ? " " + stateTag[0] : "");
    badge.textContent = stateTag[1];
    $("stat-state").appendChild(badge);
    $("stat-closes").textContent = room.expires_at
      ? new Date(room.expires_at).toLocaleString()
      : "Never";
    $("public-link").href = room.url;
    $("public-link").textContent = room.url;
    $("present").href = "/admin/rooms/" + room.room_id + "/present";
    $("qr-png").href = "/r/" + room.slug + "/qr.png?size=1024";
    $("qr-svg").href = "/r/" + room.slug + "/qr.svg";
    // An archived session is read-only: settings have nothing left to say,
    // and the banner carries the one move it still has.
    var archived = room.state === "archived";
    $("archived-notice").hidden = !archived;
    $("archived-tools").hidden = !archived;
    $("settings-card").hidden = archived;
    $("state").value = room.state;
    $("listed").checked = room.settings.listed !== false;

    fetch("/r/" + room.slug + "/qr.svg").then(function (r) { return r.text(); })
      .then(function (svg) { $("qr").innerHTML = svg; });
  }

  function patchRoom(payload) {
    request("/rooms/" + roomId, { method: "PATCH", body: JSON.stringify(payload) })
      .then(renderRoom).catch(fail);
  }

  var TABS = ["all", "unanswered", "answered"];

  /* Empty states are written per tab: each one says what would appear
     here and what causes it, not a generic "nothing". */
  var EMPTY = {
    all: ["No questions yet",
      "Share the link below — questions appear the moment they are asked."],
    unanswered: ["Everything is answered",
      "A new question lands here the moment it is asked."],
    answered: ["Nothing answered yet",
      "Mark a question answered and it moves to this tab."]
  };

  function renderQuestions() {
    var filtered = state.items.filter(function (item) {
      if (state.filter === "answered") return item.status === "answered";
      if (state.filter === "unanswered") return item.status === "visible";
      return item.status === "visible" || item.status === "answered";
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

      var score = document.createElement("div");
      // Displays a score; it is not a control, so it must not look like one.
      score.className = "vote static";
      score.setAttribute("aria-hidden", "true");
      score.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" ' +
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4 9.5 8 5l4 4.5"/></svg><span>' + item.score + "</span>";

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
          : ["Mark answered", I.check, { status: "answered", pinned: false }, false],
        [item.pinned ? "Unpin" : "Pin", I.pin, { pinned: !item.pinned }, !!item.pinned]
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
    // Answered and pinned are toggles; pressed shows which side is on.
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
    return request("/rooms/" + roomId + "/questions?status=visible,answered", { headers: headers })
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
    TABS.forEach(function (key) {
      $("f-" + key).setAttribute("aria-pressed", key === name ? "true" : "false");
    });
    renderQuestions();
  }

  /* ---- boot ---- */


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

    /* Reopening is the undo of an accidental archive, so it is one click
       with no arming — the risk runs the other way now. */
    $("reopen").addEventListener("click", function () {
      var button = this;
      button.disabled = true;
      request("/rooms/" + roomId, { method: "PATCH", body: JSON.stringify({ state: "open" }) })
        .then(function (room) {
          renderRoom(room);
          state.etag = null;
          refresh();
          toast("Session reopened");
        })
        .catch(function (error) {
          fail(error);
          button.disabled = false;
        });
    });

    /* Archiving is the console's one terminal act — no transition leaves it,
       and the API 410s once it lands — so it arms like delete: the first
       click asks, the second acts, and success returns to the list, where
       the session now lives under Archived as its own record. */
    var archiveTimer = null;
    $("archive").addEventListener("click", function () {
      var button = this;
      if (!button.classList.contains("arm")) {
        button.classList.add("arm");
        button.textContent = "Really archive?";
        clearTimeout(archiveTimer);
        archiveTimer = setTimeout(function () {
          button.classList.remove("arm");
          button.textContent = "Archive session";
        }, 3000);
        return;
      }
      clearTimeout(archiveTimer);
      button.disabled = true;
      request("/rooms/" + roomId, { method: "PATCH", body: JSON.stringify({ state: "archived" }) })
        .then(function () { location.href = "/admin"; })
        .catch(function (error) {
          button.disabled = false;
          button.classList.remove("arm");
          button.textContent = "Archive session";
          fail(error);
        });
    });
    $("listed").addEventListener("change", function () { patchRoom({ settings: { listed: this.checked } }); });
    $("copy-link").addEventListener("click", function () {
      navigator.clipboard.writeText(state.room.url).then(function () { toast("Link copied"); });
    });
    $("create-cohost").addEventListener("click", createCohost);
    TABS.forEach(function (key) {
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
