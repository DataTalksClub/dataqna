/* Shared between the admin console and presentation mode: the optimistic
   PATCH. A host's click must acknowledge on the click, not after two
   round trips — apply the change locally, re-render, then reconcile with
   the server and roll back visibly if it refuses. */
window.QNA = (function () {
  "use strict";

  /* opts:
       item     — the question object to mutate (status / pinned)
       payload  — the PATCH body fields
       busy     — a map of question_id -> action name; drives disabled/busy UI
       action   — name to record in `busy` while in flight
       send     — function returning the PATCH promise
       render   — re-render callback, called after apply and after rollback
       done(body), fail(error) — optional */
  function patch(opts) {
    var item = opts.item;
    var id = item.question_id;
    if (opts.busy[id]) return Promise.resolve();
    opts.busy[id] = opts.action || "busy";

    var before = { status: item.status, pinned: item.pinned };
    if ("status" in opts.payload) item.status = opts.payload.status;
    if ("pinned" in opts.payload) item.pinned = opts.payload.pinned;
    opts.render();

    return opts.send().then(function (body) {
      delete opts.busy[id];
      if (opts.done) opts.done(body);
    }, function (error) {
      delete opts.busy[id];
      item.status = before.status;
      item.pinned = before.pinned;
      opts.render();
      if (opts.fail) opts.fail(error);
    });
  }

  return { patch: patch };
})();
