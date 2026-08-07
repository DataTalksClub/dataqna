/* The participant view: ask, vote, and watch the list reorder. */
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("config").textContent);
  var API = "/api/v1/rooms/" + CONFIG.room_id;
  var MOTION = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;
  var RING = 75.4; /* 2πr for the limit ring's r=12 circle */

  var CHEVRON = '<svg class="arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true"><path d="M6 14l6-7 6 7"/></svg>';
  // The host's two ways back. A cog for the console and a screen for the
  // projector: both are read at a glance mid-session, which is more than a
  // word-shaped button gets on a page whose job is the question composer.
  var COG = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 ' +
    '0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09' +
    'A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 ' +
    '1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 ' +
    '1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 ' +
    '1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06' +
    '-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 ' +
    '0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';
  var SCREEN = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="2.5" y="4" width="19" height="13" rx="2"/><path d="M9 21h6M12 17v4"/></svg>';

  var el = {
    ask: document.getElementById("ask"),
    text: document.getElementById("text"),
    name: document.getElementById("name"),
    send: document.getElementById("send"),
    limit: document.getElementById("limit"),
    limitLeft: document.getElementById("limit-left"),
    limitLive: document.getElementById("limit-live"),
    list: document.getElementById("list"),
    empty: document.getElementById("empty"),
    emptyTitle: document.getElementById("empty-title"),
    emptyBody: document.getElementById("empty-body"),
    banner: document.getElementById("banner"),
    liveCount: document.getElementById("live-count"),
    toast: document.getElementById("toast"),
    console: document.getElementById("console"),
    present: document.getElementById("present"),
    tabs: {
      popular: document.getElementById("tab-popular"),
      recent: document.getElementById("tab-recent"),
      answered: document.getElementById("tab-answered")
    }
  };
  el.limitFill = el.limit.querySelector(".fill");

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
    armed: null,
    sending: false,
    over: false,
    said75: false,
    saidOver: false
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

  /* ---- questions ---- */

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

  /* Slido's card anatomy: the question leads, author and time sit under it,
     and the vote pill rides the foot line. */
  function buildCard(item) {
    var li = document.createElement("li");
    li.dataset.qid = item.question_id;
    li.className = "q" + (item.status === "answered" ? " answered" : "") +
      (item.pinned ? " pinned" : "");
    if (state.loaded && !state.seen[item.question_id]) li.classList.add("flash");
    state.seen[item.question_id] = true;

    var text = document.createElement("div");
    text.className = "text";
    text.textContent = item.text;

    var foot = document.createElement("div");
    foot.className = "q-foot";

    var meta = document.createElement("div");
    meta.className = "meta";
    var who = document.createElement("span");
    who.textContent = (item.author_name || "Anonymous") + " · " + relative(item.created_at);
    meta.appendChild(who);
    if (item.own) meta.appendChild(tag("you", "You"));
    if (item.pinned) meta.appendChild(tag("pinned", "Pinned"));
    if (item.status === "answered") meta.appendChild(tag("answered", "Answered"));

    var vote = document.createElement("button");
    vote.type = "button";
    vote.className = "vote";
    vote.setAttribute("aria-pressed", item.voted ? "true" : "false");
    vote.setAttribute("aria-label",
      "Upvote: " + item.score + (item.score === 1 ? " vote" : " votes"));
    vote.innerHTML = CHEVRON + '<span class="count" aria-hidden="true">' + item.score + "</span>";
    vote.disabled = !CONFIG.can_vote || !!state.busy[item.question_id];
    vote.addEventListener("click", function () { toggleVote(item, vote); });

    foot.appendChild(meta);
    foot.appendChild(vote);
    li.appendChild(text);
    li.appendChild(foot);

    if (item.own && item.editable) {
      var actions = document.createElement("div");
      actions.className = "actions";
      actions.appendChild(withdrawButton(item));
      li.appendChild(actions);
    }
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
    if (!text || state.over || state.sending) return;
    state.sending = true;
    el.send.disabled = true;

    request(API + "/questions", {
      method: "POST",
      body: JSON.stringify({ text: text, author_name: el.name.value.trim() || null })
    }).then(function (body) {
      el.text.value = "";
      updateLimit();
      try { localStorage.setItem("dq_name", el.name.value.trim()); } catch (e) {}
      state.etag = null;
      return refresh().then(function () { reveal(body.question_id); });
    }).catch(function (error) {
      toast(error.message);
    }).then(function () {
      state.sending = false;
      el.send.disabled = state.over;
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

  /* The Twitter ring: nothing until 75% of the limit, a filling ring after,
     the remaining count in the last 10%, and a blocked Send when over. */
  function updateLimit() {
    var limit = CONFIG.settings.max_question_length;
    var length = el.text.value.length;
    var left = limit - length;
    var lastStretch = left <= Math.ceil(limit * 0.1);
    var over = left < 0;
    var show = length >= limit * 0.75;

    state.over = over;
    el.limit.classList.toggle("show", show);
    el.limit.classList.toggle("warn", lastStretch && !over);
    el.limit.classList.toggle("over", over);
    el.limitFill.style.strokeDashoffset =
      (RING * (1 - Math.min(1, length / limit))).toFixed(1);
    el.limitLeft.textContent = show && lastStretch ? String(left) : "";
    el.send.disabled = over || state.sending;

    if (show && !state.said75) {
      state.said75 = true;
      el.limitLive.textContent = length + " of " + limit + " characters used.";
    } else if (!show) {
      state.said75 = false;
    }
    if (over && !state.saidOver) {
      state.saidOver = true;
      el.limitLive.textContent =
        "Over the " + limit + " character limit — shorten your question to send it.";
    } else if (!over) {
      state.saidOver = false;
    }
  }

  function schedule() {
    clearInterval(state.timer);
    state.timer = setInterval(refresh, document.hidden ? 30000 : 4000);
  }

  function init() {

    // Sent only to whoever already moderates this room, and the page is
    // no-store, so they never reach the audience.
    if (CONFIG.host_links) {
      el.console.href = CONFIG.host_links.console;
      el.console.innerHTML = COG;
      el.console.hidden = false;
      el.present.href = CONFIG.host_links.present;
      el.present.innerHTML = SCREEN;
      el.present.hidden = false;
    }

    if (CONFIG.can_ask) {
      el.ask.hidden = false;
      if (!CONFIG.settings.allow_names) el.name.hidden = true;
      if (CONFIG.settings.require_names) {
        el.name.placeholder = "Your name";
        el.name.required = true;
      }
      try { el.name.value = localStorage.getItem("dq_name") || ""; } catch (e) {}
      el.text.addEventListener("input", updateLimit);
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
