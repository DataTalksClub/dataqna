#!/usr/bin/env python3
"""Post-deployment verification against the live site.

Exercises the paths that a broken deploy would silently break: the public room
page, anonymous submission and voting, conditional polling, moderation
authorization, QR rendering, and the permanent /live link. Read-only against
existing data — it creates its own throwaway room and purges it at the end.

    DATAQNA_KEY=dq_... uv run --with requests python scripts/verify_deployment.py
"""

import argparse
import os
import sys
import time

import requests

FAILURES = []


def check(name, condition, detail=""):
    status = "ok  " if condition else "FAIL"
    print(f"[{status}] {name}{(' — ' + detail) if detail and not condition else ''}")
    if not condition:
        FAILURES.append(name)
    return condition


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("DATAQNA_URL", "https://qna.dtcdev.click"))
    parser.add_argument("--key", default=os.environ.get("DATAQNA_KEY", ""))
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    api = f"{base}/api/v1"
    admin_headers = {"authorization": f"Bearer {args.key}"} if args.key else None

    check("health responds", requests.get(f"{base}/health", timeout=15).json().get("status") == "ok")
    check("admin console requires sign-in",
          requests.get(f"{base}/admin", timeout=15, allow_redirects=False).status_code == 302)

    if not admin_headers:
        print("\nNo DATAQNA_KEY set — skipping the authenticated round trip.")
        return 1 if FAILURES else 0

    slug = f"verify-{int(time.time())}"
    created = requests.post(
        f"{api}/rooms", headers=admin_headers, timeout=20,
        json={"title": "Deployment verification", "slug": slug, "state": "open"},
    )
    if not check("room creation", created.status_code == 201, created.text[:200]):
        return 1
    room = created.json()
    room_id = room["room_id"]

    try:
        check("room url is canonical", room["url"] == f"{base}/r/{slug}")

        participant = requests.Session()
        page = participant.get(f"{base}/r/{slug}", timeout=20)
        check("room page renders", page.status_code == 200 and "Deployment verification" in page.text)
        check("participant cookie is issued", "dq_p" in participant.cookies)

        code_hop = requests.get(f"{base}/r/{room['code']}", timeout=20, allow_redirects=False)
        check("join code redirects to the slug",
              code_hop.status_code == 302 and code_hop.headers.get("location", "").endswith(f"/r/{slug}"))

        posted = participant.post(f"{api}/rooms/{room_id}/questions", timeout=20,
                                  json={"text": "Is the deployment healthy?", "author_name": "verifier"})
        check("anonymous submission", posted.status_code == 201, posted.text[:200])
        question_id = posted.json()["question_id"]
        check("author's own vote counts once", posted.json()["score"] == 1)

        voter = requests.Session()
        voter.get(f"{base}/r/{slug}", timeout=20)
        first = voter.post(f"{api}/rooms/{room_id}/questions/{question_id}/vote", timeout=20)
        second = voter.post(f"{api}/rooms/{room_id}/questions/{question_id}/vote", timeout=20)
        check("second participant's vote counts", first.json().get("score") == 2)
        check("repeat vote is idempotent", second.json().get("score") == 2)

        listing = requests.get(f"{api}/rooms/{room_id}/questions", timeout=20)
        etag = listing.headers.get("etag")
        check("listing returns an etag", bool(etag))
        revalidated = requests.get(f"{api}/rooms/{room_id}/questions",
                                   headers={"if-none-match": etag or ""}, timeout=20)
        check("unchanged listing revalidates to 304", revalidated.status_code == 304)

        forbidden = requests.patch(f"{api}/rooms/{room_id}/questions/{question_id}",
                                   json={"status": "answered"}, timeout=20)
        check("participants cannot moderate", forbidden.status_code == 403)

        answered = requests.patch(f"{api}/rooms/{room_id}/questions/{question_id}",
                                  headers=admin_headers, json={"status": "answered"}, timeout=20)
        check("admins can mark answered", answered.status_code == 200)

        svg = requests.get(f"{base}/r/{slug}/qr.svg", timeout=20)
        check("QR svg renders", svg.status_code == 200 and svg.text.startswith("<svg"))
        check("QR svg follows the page theme", "currentColor" in svg.text)
        png = requests.get(f"{base}/r/{slug}/qr.png?size=512", timeout=20)
        check("QR png renders", png.status_code == 200 and png.content[:4] == b"\x89PNG")

        live = requests.get(f"{base}/live", timeout=20, allow_redirects=False)
        check("live link resolves", live.status_code in (200, 302))

        export = requests.get(f"{api}/rooms/{room_id}/export?format=md", headers=admin_headers, timeout=20)
        check("markdown export", export.status_code == 200 and "Is the deployment healthy?" in export.text)

        anonymous_export = requests.get(f"{api}/rooms/{room_id}/export?format=md", timeout=20)
        check("export requires an admin", anonymous_export.status_code == 401)

        # Co-host invites: a link that names one, and a passcode that opens it.
        invite = requests.post(f"{api}/rooms/{room_id}/cohosts", headers=admin_headers,
                               json={"label": "verifier"}, timeout=20)
        check("co-host invite creation", invite.status_code == 201, invite.text[:200])
        name, passcode = invite.json()["name"], invite.json()["passcode"]
        check("the join link does not carry the passcode",
              passcode not in invite.json()["join_url"])

        leaked = requests.Session()
        link_only = leaked.get(f"{base}/cohost/{name}", timeout=20, allow_redirects=False)
        check("the link alone only asks for the passcode",
              link_only.status_code == 200 and "dq_cohost" not in leaked.cookies)
        wrong = leaked.post(f"{base}/cohost", timeout=20, allow_redirects=False,
                            data={"name": name, "passcode": "WRONG-WRONG-WRNG"})
        check("a wrong passcode is refused",
              wrong.status_code == 403 and "dq_cohost" not in leaked.cookies)

        cohost = requests.Session()
        redeemed = cohost.post(f"{base}/cohost", timeout=20, allow_redirects=False,
                               data={"name": name, "passcode": passcode})
        check("link and passcode together redeem to the session",
              redeemed.status_code == 302 and room_id in redeemed.headers.get("location", ""))
        check("co-host cookie is issued", "dq_cohost" in cohost.cookies)

        moderated = cohost.patch(f"{api}/rooms/{room_id}/questions/{question_id}",
                                 json={"pinned": True}, timeout=20)
        check("co-host can moderate", moderated.status_code == 200, moderated.text[:200])

        runs = cohost.patch(f"{api}/rooms/{room_id}",
                            json={"settings": {"default_sort": "recent"}}, timeout=20)
        check("co-host runs the session's settings", runs.status_code == 200)

        blocked = cohost.patch(f"{api}/rooms/{room_id}", json={"slug": "hijacked"}, timeout=20)
        check("co-host cannot move the published link", blocked.status_code == 403)

        no_keys = cohost.get(f"{api}/rooms/{room_id}/cohosts", timeout=20)
        check("co-host cannot read co-host invites", no_keys.status_code == 403)

        no_rooms = cohost.get(f"{api}/rooms", timeout=20)
        check("co-host cannot list rooms", no_rooms.status_code == 401)

        unknown = requests.post(f"{base}/cohost", timeout=20, allow_redirects=False,
                                data={"name": "no-such-invite", "passcode": passcode})
        check("an unknown link name is refused", unknown.status_code == 403)

        requests.delete(f"{api}/rooms/{room_id}/cohosts/{invite.json()['invite_id']}",
                        headers=admin_headers, timeout=20)
        after_revoke = cohost.patch(f"{api}/rooms/{room_id}/questions/{question_id}",
                                    json={"pinned": False}, timeout=20)
        check("revoking an invite takes effect immediately", after_revoke.status_code == 403)

        no_admins = requests.put(f"{api}/rooms/{room_id}/admins/someone@example.com",
                                 headers=admin_headers, timeout=20)
        check("per-room email admins are gone", no_admins.status_code == 404)

    finally:
        requests.delete(f"{api}/rooms/{room_id}?purge=true", headers=admin_headers, timeout=20)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
