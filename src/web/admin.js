/* Admin console. One page, two views, chosen by the path. */
(function () {
  "use strict";

  var API = "/api/v1";
  var roomId = (location.pathname.match(/^\/admin\/rooms\/([^/]+)/) || [])[1];
  var toastEl = document.getElementById("toast");
  var state = { room: null, filter: "all", items: [], etag: null, armedDelete: null };

  function $(id) { return document.getElementById(id); }

  function toast(message) {
    toastEl.textContent = message;
    toastEl.classList.add("show");
    setTimeout(function () { toastEl.classList.remove("show"); }, 2800);
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
          room.counts.questions + " questions, " + room.counts.answered + " answered" +
          (room.counts.pending ? " · " + room.counts.pending + " to review" : "");
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
      var table = $("keys");
      table.innerHTML = "<tr><th>Name</th><th>Created</th><th>Last used</th><th></th></tr>";
      (body.items || []).forEach(function (key) {
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
      var table = $("cohosts");
      table.innerHTML = "<tr><th>Code</th><th>For</th><th>Valid until</th><th></th></tr>";
      (body.items || []).forEach(function (invite) {
        var row = table.insertRow();
        var codeCell = row.insertCell();
        codeCell.className = "mono";
        codeCell.textContent = invite.code;
        row.insertCell().textContent = invite.label || "—";
        row.insertCell().textContent = (invite.expires_at || "").slice(0, 10) || "no expiry";

        var cell = row.insertCell();
        var copy = document.createElement("button");
        copy.className = "ghost small";
        copy.textContent = "Copy link";
        copy.addEventListener("click", function () {
          navigator.clipboard.writeText(invite.join_url).then(function () { toast("Co-host link copied"); });
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
      body: JSON.stringify({ label: $("cohost-label").value.trim() || null })
    }).then(function (invite) {
      $("cohost-label").value = "";
      toast("Code " + invite.code + " created");
      loadCohosts();
    }).catch(fail);
  }

  function renderRoom(room) {
    state.room = room;
    // A co-host sees the questions and the share panel, and nothing that would
    // let them change the room or widen their own access.
    var isCohost = room.role === "cohost";
    $("settings-card").hidden = isCohost;
    $("cohost-card").hidden = isCohost;
    $("cohost-notice").hidden = !isCohost;
    if (isCohost) {
      var back = document.querySelector('a[href="/admin"]');
      if (back) back.hidden = true;
    }
    $("room-title").textContent = room.title;
    $("room-sub").textContent = room.state + " · " + room.counts.questions + " questions" +
      (room.expires_at ? " · closes " + new Date(room.expires_at).toLocaleString() : "");
    $("public-link").href = room.url;
    $("public-link").textContent = room.url;
    $("join-code").textContent = room.code;
    $("present").href = "/admin/rooms/" + room.room_id + "/present";
    $("qr-png").href = "/r/" + room.slug + "/qr.png?size=1024";
    $("qr-svg").href = "/r/" + room.slug + "/qr.svg";
    ["md", "csv", "json"].forEach(function (format) {
      $("export-" + format).href = API + "/rooms/" + room.room_id + "/export?format=" + format;
    });
    $("state").value = room.state;
    $("questions-open").checked = room.settings.questions_open;
    $("voting-open").checked = room.settings.voting_open;
    $("moderation").checked = room.settings.moderation === "on";
    if (!isCohost) {
      $("admins").textContent = "Owner " + room.owner +
        (room.admins && room.admins.length ? " · admins: " + room.admins.join(", ") : "");
    }

    fetch("/r/" + room.slug + "/qr.svg").then(function (r) { return r.text(); })
      .then(function (svg) { $("qr").innerHTML = svg; });
  }

  function patchRoom(payload) {
    request("/rooms/" + roomId, { method: "PATCH", body: JSON.stringify(payload) })
      .then(renderRoom).catch(fail);
  }

  function renderQuestions() {
    var filtered = state.items.filter(function (item) {
      if (state.filter === "all") return item.status === "visible" || item.status === "answered";
      if (state.filter === "pending") return item.status === "pending";
      if (state.filter === "answered") return item.status === "answered";
      return item.status === "hidden";
    });
    var pending = state.items.filter(function (q) { return q.status === "pending"; }).length;
    $("pending-badge").hidden = pending === 0;
    $("pending-badge").textContent = pending;

    $("qempty").hidden = filtered.length > 0;
    var list = $("qlist");
    list.textContent = "";

    filtered.forEach(function (item) {
      var li = document.createElement("li");
      li.className = "q" + (item.status === "answered" ? " answered" : "") + (item.pinned ? " pinned" : "");

      var score = document.createElement("div");
      // Displays a score; it is not a control, so it must not look like one.
      score.className = "vote static";
      score.setAttribute("aria-hidden", "true");
      score.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M6 14l6-7 6 7"/></svg><span>' + item.score + "</span>";

      var body = document.createElement("div");
      body.className = "grow";
      var text = document.createElement("div");
      text.className = "text";
      text.textContent = item.text;
      var meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = (item.author_name || "Anonymous") + " · " + new Date(item.created_at).toLocaleTimeString() + " · " + item.status;

      var actions = document.createElement("div");
      actions.className = "actions";
      [
        item.status === "pending" ? ["Approve", { status: "visible" }, true] : null,
        item.status === "answered"
          ? ["Unanswer", { status: "visible" }, false]
          : ["Mark answered", { status: "answered" }, item.status !== "pending"],
        [item.pinned ? "Unpin" : "Pin", { pinned: !item.pinned }, false],
        item.status === "hidden" ? ["Restore", { status: "visible" }, false] : ["Hide", { status: "hidden" }, false]
      ].filter(Boolean).forEach(function (entry) {
        var button = document.createElement("button");
        // Answering is the live-session flow; it earns the filled treatment.
        button.className = entry[2] ? "small" : "ghost small";
        button.textContent = entry[0];
        button.addEventListener("click", function () {
          request("/rooms/" + roomId + "/questions/" + item.question_id, {
            method: "PATCH", body: JSON.stringify(entry[1])
          }).then(function () { state.etag = null; refresh(); }).catch(fail);
        });
        actions.appendChild(button);
      });
      actions.appendChild(deleteButton(item));

      body.appendChild(text);
      body.appendChild(meta);
      body.appendChild(actions);
      li.appendChild(score);
      li.appendChild(body);
      list.appendChild(li);
    });
  }

  function refresh() {
    var headers = state.etag ? { "if-none-match": state.etag } : {};
    return request("/rooms/" + roomId + "/questions?status=visible,answered,pending,hidden", { headers: headers })
      .then(function (body) {
        if (body.unchanged) return;
        state.etag = body.etag;
        state.items = body.items || [];
        renderQuestions();
      }).catch(function () {});
  }

  /* Deleting is irreversible, so the first click only arms the button. */
  function deleteButton(item) {
    var button = document.createElement("button");
    var armed = state.armedDelete === item.question_id;
    button.className = armed ? "small arm" : "ghost small";
    button.textContent = armed ? "Really delete?" : "Delete";
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
      request("/rooms/" + roomId + "/questions/" + item.question_id, {
        method: "PATCH", body: JSON.stringify({ status: "deleted" })
      }).then(function () { state.etag = null; refresh(); }).catch(fail);
    });
    return button;
  }

  function selectFilter(name) {
    state.filter = name;
    ["all", "pending", "answered", "hidden"].forEach(function (key) {
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

    $("state").addEventListener("change", function () { patchRoom({ state: this.value }); });
    $("questions-open").addEventListener("change", function () { patchRoom({ settings: { questions_open: this.checked } }); });
    $("voting-open").addEventListener("change", function () { patchRoom({ settings: { voting_open: this.checked } }); });
    $("moderation").addEventListener("change", function () { patchRoom({ settings: { moderation: this.checked ? "on" : "off" } }); });
    $("add-admin").addEventListener("click", function () {
      var email = $("admin-email").value.trim().toLowerCase();
      if (!email) return;
      request("/rooms/" + roomId + "/admins/" + encodeURIComponent(email), { method: "PUT" })
        .then(function () {
          $("admin-email").value = "";
          toast("Added " + email);
          return request("/rooms/" + roomId).then(renderRoom);
        }).catch(fail);
    });
    $("copy-link").addEventListener("click", function () {
      navigator.clipboard.writeText(state.room.url).then(function () { toast("Link copied"); });
    });
    $("create-cohost").addEventListener("click", createCohost);
    ["all", "pending", "answered", "hidden"].forEach(function (key) {
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
