# -*- coding: utf-8 -*-
"""Publish a reel to the SECOND Instagram account (account-2 pipeline).

Deliberately independent of the account-1 pipeline: its own host repo
(astrology-reels-2), its own credentials file (instagram-credentials-2.json).

Flow
  1. Push <type>.mp4 + <type>.txt to the public host repo, date-stamped filename.
  2. Wait until the GitHub Pages URL actually serves the file (Pages deploy lag).
  3. Create a REELS container on graph.facebook.com with video_url
     (Meta fetches the video itself - no resumable upload needed).
  4. Poll container status, then media_publish.
  5. Print the permalink.

Usage (inside run_program):
    exec(open('/scratch/saved/reel_publish2.py').read())

Env
    REEL_DRYRUN=1   host the video but stop before publishing to Instagram
"""
import asyncio
import base64
import datetime
import json
import os
import time

import requests

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
OWNER = "sahilyadavy251-tech"
HOST_REPO = "astrology-reels-2"
GRAPH = "https://graph.facebook.com/v21.0"
KEEP = ("README.md", "index.html", ".nojekyll", "reel_publish2.py")
CREDS_CANDIDATES = (
    "/scratch/work/instagram-credentials-2.json",
    "/scratch/saved/instagram-credentials-2.json",
)
DRYRUN = os.environ.get("REEL_DRYRUN") == "1"


def load_creds():
    for path in CREDS_CANDIDATES:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    raise SystemExit("PUBLISH_FAIL: instagram-credentials-2.json kahin nahi mila")


def check_account(creds):
    """Cheap sanity check: is the token alive and does it point at the right account?"""
    tok = creds.get("page_token") or creds.get("user_token_60d")
    ig = creds.get("ig_user_id")
    r = requests.get(
        "%s/%s" % (GRAPH, ig),
        params={"fields": "username,name,followers_count", "access_token": tok},
        timeout=30,
    )
    j = r.json()
    if "error" in j:
        raise SystemExit("PUBLISH_FAIL: token/account check - %s" % json.dumps(j)[:300])
    print("account: @%s (%s), followers=%s"
          % (j.get("username"), j.get("name"), j.get("followers_count")))
    return j


async def host_video(vtype, mp4, cap):
    """Push video to the public repo and return its GitHub Pages URL."""
    from sarvam_tools import GITHUB_COMMIT_MULTIPLE_FILES, GITHUB_GET_REPOSITORY_CONTENT

    day = datetime.datetime.now(IST).strftime("%Y%m%d")
    fname = "%s-%s.mp4" % (vtype, day)
    cname = "%s-%s.txt" % (vtype, day)

    raw = open(mp4, "rb").read()
    b64 = base64.b64encode(raw).decode()
    print("%s: %.2f MB (base64 %.2f MB) -> %s"
          % (vtype, len(raw) / 1e6, len(b64) / 1e6, fname))
    if len(b64) > 4_000_000:
        raise SystemExit("PUBLISH_FAIL: video bahut badi (base64 limit)")

    ups = [{"path": fname, "content": b64, "encoding": "base64"}]
    if cap and os.path.exists(cap):
        ups.append({"path": cname,
                    "content": base64.b64encode(open(cap, "rb").read()).decode(),
                    "encoding": "base64"})

    deletes = []
    try:
        listing = await GITHUB_GET_REPOSITORY_CONTENT(owner=OWNER, repo=HOST_REPO, path="/")
        for it in (listing.get("content") or []):
            nm = it.get("name") or ""
            if nm in KEEP or nm in (fname, cname):
                continue
            if nm.endswith(".mp4") or nm.endswith(".txt"):
                deletes.append(nm)
    except Exception as e:
        print("cleanup list skip: %s" % str(e)[:120])

    await GITHUB_COMMIT_MULTIPLE_FILES(
        owner=OWNER, repo=HOST_REPO, branch="main",
        message="Reel %s %s" % (vtype, day), upserts=ups, deletes=deletes,
    )
    print("HOST_OK %s%s" % (fname, (" (cleaned %d)" % len(deletes)) if deletes else ""))
    return "https://%s.github.io/%s/%s" % (OWNER, HOST_REPO, fname)


def wait_for_url(url, timeout=240):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.head(url, timeout=20, allow_redirects=True)
            if r.status_code == 200 and int(r.headers.get("content-length") or 0) > 0:
                print("URL live: %s" % url)
                return True
        except Exception:
            pass
        time.sleep(8)
    return False


def create_container(creds, caption, video_url):
    tok = creds.get("page_token") or creds.get("user_token_60d")
    ig = creds.get("ig_user_id")
    r = requests.post(
        "%s/%s/media" % (GRAPH, ig),
        data={"media_type": "REELS", "video_url": video_url, "caption": caption,
              "share_to_feed": "true", "access_token": tok},
        timeout=60,
    )
    j = r.json()
    if "id" not in j:
        raise SystemExit("PUBLISH_FAIL: container create - %s" % json.dumps(j)[:400])
    print("container: %s" % j["id"])
    return j["id"]


def wait_ready(creds, container_id, timeout=300, interval=6):
    tok = creds.get("page_token") or creds.get("user_token_60d")
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = requests.get("%s/%s" % (GRAPH, container_id),
                         params={"fields": "status_code,status", "access_token": tok},
                         timeout=30)
        j = r.json()
        code = j.get("status_code")
        if code != last:
            print("  status: %s %s" % (code, j.get("status", "")))
            last = code
        if code == "FINISHED":
            return True
        if code == "ERROR":
            raise SystemExit("PUBLISH_FAIL: container ERROR - %s" % json.dumps(j)[:300])
        time.sleep(interval)
    return False


def publish(creds, container_id):
    tok = creds.get("page_token") or creds.get("user_token_60d")
    ig = creds.get("ig_user_id")
    r = requests.post("%s/%s/media_publish" % (GRAPH, ig),
                      data={"creation_id": container_id, "access_token": tok},
                      timeout=120)
    j = r.json()
    if "id" not in j:
        raise SystemExit("PUBLISH_FAIL: media_publish - %s" % json.dumps(j)[:400])
    media_id = j["id"]
    perma = None
    try:
        r2 = requests.get("%s/%s" % (GRAPH, media_id),
                          params={"fields": "permalink", "access_token": tok}, timeout=30)
        perma = (r2.json() or {}).get("permalink")
    except Exception:
        pass
    print("PUBLISHED media_id=%s %s" % (media_id, perma or ""))
    return media_id, perma


async def main():
    try:
        vtype = open("/scratch/work/current_type.txt").read().strip() or "rashifal"
    except Exception:
        vtype = "rashifal"
    mp4 = "/scratch/work/%s.mp4" % vtype
    cap = "/scratch/work/%s.txt" % vtype
    if not os.path.exists(mp4):
        print("PUBLISH_FAIL: %s nahi mila" % mp4)
        return

    creds = load_creds()
    check_account(creds)

    caption = open(cap, encoding="utf-8").read().strip() if os.path.exists(cap) else ""
    url = await host_video(vtype, mp4, cap)

    if DRYRUN:
        print("DRYRUN: host done, Instagram publish skipped")
        return

    if not wait_for_url(url):
        print("PUBLISH_FAIL: Pages URL live nahi hua - %s" % url)
        return

    cid = create_container(creds, caption, url)
    if not wait_ready(creds, cid):
        print("PUBLISH_FAIL: container time out")
        return
    publish(creds, cid)


asyncio.run(main())
