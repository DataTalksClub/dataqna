/* The participant view: ask, vote, and watch the list reorder. */
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("config").textContent);
  var API = "/api/v1/rooms/" + CONFIG.room_id;
  var MOTION = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;

  var CHEVRON = '<svg class="arrow" width="18" height="18" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true"><path d="M6 14l6-7 6 7"/></svg>';

  var el = {
    ask: document.getElementById("ask"),
    text: document.getElementById("text"),
    name: document.getElementById("name"),
    send: document.getElementById("send"),
    counter: document.getElementById("counter"),
    count: document.getElementById("count"),
    max: document.getElementById("max"),
    list: document.getElementById("list"),
    empty: document.getElementById("empty"),
    emptyTitle: document.getElementById("empty-title"),
    emptyBody: document.getElementById("empty-body"),
    banner: document.getElementById("banner"),
    liveCount: document.getElementById("live-count"),
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
    counts: null,
    seen: {},
    timer: null,
    busy: {},
    failures: 0,
    loaded: false,
    armed: null
  };

  var separateAnswered = CONFIG.settings.answered_placement === "separate";

  function toast(message) {
    el.toast.textContent = message;
    el.toast.classList.add("show");
    setTimeout(function () { el.toast.classList.remove("show"); }, 2800);
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

  function tag(kind, label) {
    var span = document.createElement("span");
    span.className = "tag" + (kind ? " " + kind : "");
    span.textContent = label;
    return span;
  }

  function visibleItems() {
    var items = state.items.filter(function (item) {
      if (state.tab === "answered") return item.status === "answered";
      if (separateAnswered && item.status === "answered") return false;
      return true;
    });

    if (state.tab === "answered") return items;

    return items.slice().sort(function (a, b) {
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

  function positions() {
    var map = {};
    Array.prototype.forEach.call(el.list.children, function (li) {
      map[li.dataset.qid] = li.offsetTop;
    });
    return map;
  }

  /* A rank change is the emotional core of a live Q&A. Sliding the cards to
     their new places makes it legible; a straight swap reads as a glitch. */
  function playFlip(before) {
    if (!MOTION) return;
    Array.prototype.forEach.call(el.list.children, function (li) {
      var was = before[li.dataset.qid];
      if (was === undefined) return;
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

  function buildCard(item) {
    var li = document.createElement("li");
    li.dataset.qid = item.question_id;
    li.className = "q" + (item.status === "answered" ? " answered" : "") +
      (item.pinned ? " pinned" : "");
    if (state.loaded && !state.seen[item.question_id]) li.classList.add("flash");
    state.seen[item.question_id] = true;

    var vote = document.createElement("button");
    vote.type = "button";
    vote.className = "vote";
    vote.setAttribute("aria-pressed", item.voted ? "true" : "false");
    vote.setAttribute("aria-label",
      "Upvote: " + item.score + (item.score === 1 ? " vote" : " votes"));
    vote.innerHTML = CHEVRON + '<span class="count" aria-hidden="true">' + item.score + "</span>";
    vote.disabled = !CONFIG.can_vote || !!state.busy[item.question_id];
    vote.addEventListener("click", function () { toggleVote(item, vote); });

    var body = document.createElement("div");
    body.className = "grow";

    var text = document.createElement("div");
    text.className = "text";
    text.textContent = item.text;

    var meta = document.createElement("div");
    meta.className = "meta";
    var who = document.createElement("span");
    who.textContent = (item.author_name || "Anonymous") + " · " + relative(item.created_at);
    meta.appendChild(who);
    if (item.own) meta.appendChild(tag("you", "You"));
    if (item.pinned) meta.appendChild(tag("pinned", "Pinned"));
    if (item.status === "answered") meta.appendChild(tag("answered", "Answered"));
    if (item.status === "pending") meta.appendChild(tag("pending", "Awaiting review"));

    body.appendChild(text);
    body.appendChild(meta);

    if (item.own && item.editable) {
      var actions = document.createElement("div");
      actions.className = "actions";
      actions.appendChild(withdrawButton(item));
      body.appendChild(actions);
    }

    li.appendChild(vote);
    li.appendChild(body);
    return li;
  }

  /* Withdrawing cannot be undone, so the first tap only arms the button. */
  function withdrawButton(item) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small";
    var armed = state.armed === item.question_id;
    button.textContent = armed ? "Really withdraw?" : "Withdraw";
    if (armed) button.classList.add("arm");
    button.addEventListener("click", function () {
      if (state.armed !== item.question_id) {
        state.armed = item.question_id;
        render();
        setTimeout(function () {
          if (state.armed === item.question_id) { state.armed = null; render(); }
        }, 3000);
        return;
      }
      state.armed = null;
      withdrawQuestion(item);
    });
    return button;
  }

  function render() {
    var items = visibleItems();
    var before = positions();

    el.empty.hidden = items.length > 0;
    if (!items.length) {
      var answeredTab = state.tab === "answered";
      el.emptyTitle.textContent = answeredTab ? "Nothing answered yet" : "No questions yet";
      el.emptyBody.textContent = answeredTab
        ? "Questions move here once the host answers them."
        : "Ask the first one — it only takes a moment.";
    }

    el.list.textContent = "";
    items.forEach(function (item) { el.list.appendChild(buildCard(item)); });
    playFlip(before);

    if (state.counts) {
      var total = (state.counts.visible || 0) + (state.counts.answered || 0);
      el.liveCount.hidden = total === 0;
      el.liveCount.textContent = total + (total === 1 ? " question" : " questions");
    }
  }

  function toggleVote(item, button) {
    if (state.busy[item.question_id]) return;
    state.busy[item.question_id] = true;

    /* Update in place rather than re-rendering: re-sorting on tap would move
       the card out from under the thumb that just hit it. The next poll
       re-ranks, with the slide animation to explain what happened. */
    var wasVoted = item.voted;
    item.voted = !wasVoted;
    item.score += wasVoted ? -1 : 1;
    paint(item, button);

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
        paint(item, button);
      });
  }

  function paint(item, button) {
    var count = button.querySelector(".count");
    button.setAttribute("aria-pressed", item.voted ? "true" : "false");
    button.setAttribute("aria-label",
      "Upvote: " + item.score + (item.score === 1 ? " vote" : " votes"));
    count.textContent = item.score;
    if (MOTION) {
      count.classList.remove("pop");
      void count.offsetWidth;
      count.classList.add("pop");
    }
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

  function applyRoomState(next) {
    if (!next || next === CONFIG.state) return;
    CONFIG.state = next;
    var open = next === "open";
    el.ask.hidden = !open || !CONFIG.can_ask;
    if (!open) {
      el.banner.hidden = false;
      el.banner.className = "banner warn";
      el.banner.textContent = "This room is closed. You can still read the questions.";
    }
  }

  function connectionBanner(lost) {
    if (lost) {
      el.banner.hidden = false;
      el.banner.className = "banner warn";
      el.banner.textContent = "Connection lost — retrying…";
    } else if (CONFIG.state === "open") {
      el.banner.hidden = !CONFIG.banner;
      el.banner.className = "banner";
      el.banner.textContent = CONFIG.banner || "";
    }
  }

  function refresh() {
    var headers = state.etag ? { "if-none-match": state.etag } : {};
    return request(API + "/questions?sort=" + state.sort, { headers: headers })
      .then(function (body) {
        if (state.failures >= 2) connectionBanner(false);
        state.failures = 0;
        if (body.unchanged) return;
        applyRoomState(body.state);
        state.etag = body.etag;
        state.items = body.items || [];
        state.counts = body.counts || null;
        if (separateAnswered) {
          el.tabs.answered.hidden = !(body.counts && body.counts.answered > 0);
        }
        render();
        state.loaded = true;
      })
      .catch(function () {
        /* One dropped poll is not worth interrupting anyone for. A dead
           connection at a live event is — venue wifi fails constantly. */
        state.failures += 1;
        if (state.failures >= 2) connectionBanner(true);
        if (!state.loaded) { el.empty.hidden = false; state.loaded = true; }
      });
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
      updateCounter();
      try { localStorage.setItem("dq_name", el.name.value.trim()); } catch (e) {}
      if (body.status === "pending") {
        toast("Sent for review — only you can see it until it's approved");
      }
      state.etag = null;
      return refresh().then(function () { reveal(body.question_id); });
    }).catch(function (error) {
      toast(error.message);
    }).then(function () {
      el.send.disabled = false;
    });
  }

  /* A new question lands at the bottom of Popular, possibly off-screen. Take
     the asker to it, or they cannot tell that anything happened. */
  function reveal(questionId) {
    var card = el.list.querySelector('[data-qid="' + questionId + '"]');
    if (!card) return;
    card.scrollIntoView({ behavior: MOTION ? "smooth" : "auto", block: "center" });
    if (!MOTION) return;
    card.classList.remove("flash");
    void card.offsetWidth;
    card.classList.add("flash");
  }

  function selectTab(name) {
    state.tab = name;
    if (name !== "answered") state.sort = name;
    Object.keys(el.tabs).forEach(function (key) {
      el.tabs[key].setAttribute("aria-pressed", key === name ? "true" : "false");
    });
    render();
    state.etag = null;
    refresh();
  }

  function updateCounter() {
    var limit = CONFIG.settings.max_question_length;
    var length = el.text.value.length;
    el.count.textContent = String(length);
    el.counter.hidden = length < limit * 0.8;
    el.counter.classList.toggle("limit", length >= limit);
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
      if (CONFIG.settings.require_names) {
        el.name.placeholder = "Your name";
        el.name.required = true;
      }
      try { el.name.value = localStorage.getItem("dq_name") || ""; } catch (e) {}
      el.text.addEventListener("input", updateCounter);
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
    // Relative timestamps go stale behind 304s, which is most of the time.
    setInterval(function () { if (state.items.length) render(); }, 60000);
  }

  init();
})();
