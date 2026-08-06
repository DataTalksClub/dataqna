/* The participant view: ask, vote, and watch the list reorder. */
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("config").textContent);
  var API = "/api/v1/rooms/" + CONFIG.room_id;

  var el = {
    ask: document.getElementById("ask"),
    text: document.getElementById("text"),
    name: document.getElementById("name"),
    send: document.getElementById("send"),
    count: document.getElementById("count"),
    max: document.getElementById("max"),
    list: document.getElementById("list"),
    empty: document.getElementById("empty"),
    banner: document.getElementById("banner"),
    toast: document.getElementById("toast"),
    tabs: {
      popular: document.getElementById("tab-popular"),
      recent: document.getElementById("tab-recent"),
      answered: document.getElementById("tab-answered")
    }
  };

  var state = {
    sort: CONFIG.settings.default_sort === "recent" ? "recent" : "popular",
    tab: CONFIG.settings.default_sort === "recent" ? "recent" : "popular",
    etag: null,
    items: [],
    timer: null,
    busy: {}
  };

  var separateAnswered = CONFIG.settings.answered_placement === "separate";

  function toast(message) {
    el.toast.textContent = message;
    el.toast.classList.add("show");
    setTimeout(function () { el.toast.classList.remove("show"); }, 2600);
  }

  function request(path, options) {
    options = options || {};
    options.headers = Object.assign({ "content-type": "application/json" }, options.headers || {});
    return fetch(path, options).then(function (res) {
      if (res.status === 304) return { unchanged: true };
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (!res.ok) throw new Error((body.error && body.error.message) || "Something went wrong.");
        return body;
      });
    });
  }

  function relative(iso) {
    if (!iso) return "";
    var seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h ago";
    return Math.floor(seconds / 86400) + "d ago";
  }

  function render() {
    var items = state.items.filter(function (item) {
      if (state.tab === "answered") return item.status === "answered";
      if (separateAnswered && item.status === "answered") return false;
      return true;
    });

    if (state.tab !== "answered") {
      items = items.slice().sort(function (a, b) {
        if (!!b.pinned !== !!a.pinned) return b.pinned ? 1 : -1;
        if (CONFIG.settings.answered_placement === "bottom") {
          var aa = a.status === "answered", ba = b.status === "answered";
          if (aa !== ba) return aa ? 1 : -1;
        }
        if (state.tab === "recent") return new Date(b.created_at) - new Date(a.created_at);
        if (b.score !== a.score) return b.score - a.score;
        return new Date(a.created_at) - new Date(b.created_at);
      });
    }

    el.empty.hidden = items.length > 0;
    el.list.textContent = "";

    items.forEach(function (item) {
      var li = document.createElement("li");
      li.className = "q" + (item.status === "answered" ? " answered" : "") + (item.pinned ? " pinned" : "");

      var vote = document.createElement("button");
      vote.className = "vote";
      vote.type = "button";
      vote.setAttribute("aria-pressed", item.voted ? "true" : "false");
      vote.setAttribute("aria-label", "Upvote");
      vote.innerHTML = '<span class="arrow">▲</span><span>' + item.score + "</span>";
      vote.disabled = !CONFIG.can_vote || !!state.busy[item.question_id];
      vote.addEventListener("click", function () { toggleVote(item); });

      var body = document.createElement("div");
      body.className = "grow";

      var text = document.createElement("div");
      text.className = "text";
      text.textContent = item.text;

      var meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = (item.author_name || "Anonymous") + " · " + relative(item.created_at);
      if (item.own) meta.appendChild(tag("you", "You"));
      if (item.status === "answered") meta.appendChild(tag("", "Answered"));
      if (item.status === "pending") meta.appendChild(tag("", "Awaiting review"));

      body.appendChild(text);
      body.appendChild(meta);

      if (item.own && item.editable) {
        var actions = document.createElement("div");
        actions.className = "actions";
        var withdraw = document.createElement("button");
        withdraw.className = "ghost small";
        withdraw.type = "button";
        withdraw.textContent = "Withdraw";
        withdraw.addEventListener("click", function () { withdrawQuestion(item); });
        actions.appendChild(withdraw);
        body.appendChild(actions);
      }

      li.appendChild(vote);
      li.appendChild(body);
      el.list.appendChild(li);
    });
  }

  function tag(kind, label) {
    var span = document.createElement("span");
    span.className = "tag" + (kind ? " " + kind : "");
    span.textContent = label;
    return span;
  }

  function refresh() {
    var headers = state.etag ? { "if-none-match": state.etag } : {};
    return request(API + "/questions?sort=" + state.sort, { headers: headers })
      .then(function (body) {
        if (body.unchanged) return;
        state.etag = body.etag;
        state.items = body.items || [];
        if (separateAnswered) {
          el.tabs.answered.hidden = !(body.counts && body.counts.answered > 0);
        }
        render();
      })
      .catch(function () { /* a dropped poll is not worth interrupting anyone for */ });
  }

  function toggleVote(item) {
    if (state.busy[item.question_id]) return;
    state.busy[item.question_id] = true;
    var wasVoted = item.voted;
    item.voted = !wasVoted;
    item.score += wasVoted ? -1 : 1;
    render();

    request(API + "/questions/" + item.question_id + "/vote", { method: wasVoted ? "DELETE" : "POST" })
      .then(function (body) {
        item.score = body.score;
        item.voted = body.voted;
      })
      .catch(function (error) {
        item.voted = wasVoted;
        item.score += wasVoted ? 1 : -1;
        toast(error.message);
      })
      .then(function () {
        delete state.busy[item.question_id];
        state.etag = null;
        render();
      });
  }

  function withdrawQuestion(item) {
    request(API + "/questions/" + item.question_id, {
      method: "PATCH",
      body: JSON.stringify({ status: "deleted" })
    }).then(function () {
      state.etag = null;
      return refresh();
    }).catch(function (error) { toast(error.message); });
  }

  function submit(event) {
    event.preventDefault();
    var text = el.text.value.trim();
    if (!text) return;
    el.send.disabled = true;

    request(API + "/questions", {
      method: "POST",
      body: JSON.stringify({ text: text, author_name: el.name.value.trim() || null })
    }).then(function (body) {
      el.text.value = "";
      el.count.textContent = "0";
      try { localStorage.setItem("dq_name", el.name.value.trim()); } catch (e) {}
      toast(body.status === "pending" ? "Sent for review" : "Question posted");
      state.etag = null;
      return refresh();
    }).catch(function (error) {
      toast(error.message);
    }).then(function () {
      el.send.disabled = false;
    });
  }

  function selectTab(name) {
    state.tab = name;
    if (name !== "answered") state.sort = name;
    Object.keys(el.tabs).forEach(function (key) {
      el.tabs[key].setAttribute("aria-selected", key === name ? "true" : "false");
    });
    state.etag = null;
    refresh();
  }

  function schedule() {
    clearInterval(state.timer);
    state.timer = setInterval(refresh, document.hidden ? 30000 : 4000);
  }

  function init() {
    if (CONFIG.can_ask) {
      el.ask.hidden = false;
      el.max.textContent = CONFIG.settings.max_question_length;
      el.text.maxLength = CONFIG.settings.max_question_length;
      if (!CONFIG.settings.allow_names) el.name.hidden = true;
      if (CONFIG.settings.require_names) el.name.placeholder = "Your name";
      try { el.name.value = localStorage.getItem("dq_name") || ""; } catch (e) {}
      el.text.addEventListener("input", function () {
        el.count.textContent = String(el.text.value.length);
      });
      el.ask.addEventListener("submit", submit);
      el.text.addEventListener("keydown", function (event) {
        if ((event.metaKey || event.ctrlKey) && event.key === "Enter") submit(event);
      });
      if (window.matchMedia("(min-width: 720px)").matches) el.text.focus();
    }

    if (CONFIG.banner) {
      el.banner.hidden = false;
      el.banner.textContent = CONFIG.banner;
      if (CONFIG.state !== "open") el.banner.classList.add("warn");
    }

    el.tabs.popular.addEventListener("click", function () { selectTab("popular"); });
    el.tabs.recent.addEventListener("click", function () { selectTab("recent"); });
    el.tabs.answered.addEventListener("click", function () { selectTab("answered"); });
    if (state.tab === "recent") selectTab("recent");

    document.addEventListener("visibilitychange", function () {
      schedule();
      if (!document.hidden) refresh();
    });

    refresh();
    schedule();
  }

  init();
})();
