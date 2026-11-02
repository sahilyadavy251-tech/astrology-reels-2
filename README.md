# astrology-reels-2

Temporary public host for daily Instagram reels — **account 2**.

Meta's Instagram API needs a public `https://` URL to fetch a reel from. This repo is
that host: `reel_publish2.py` commits one date-stamped `.mp4` here, waits for GitHub
Pages to serve it, and then asks Instagram to pull it.

Nothing secret lives here — the access token is kept outside this repo.

## Files

| File | Purpose |
| --- | --- |
| `reel_publish2.py` | Hosts a reel here, then publishes it to account 2 |
| `index.html` | Placeholder page so the Pages site is never empty |
| `.nojekyll` | Tells Pages to serve files as-is (no Jekyll processing) |

## Publish URL pattern

```
https://sahilyadavy251-tech.github.io/astrology-reels-2/<type>-<YYYYMMDD>.mp4
```

A new filename every day is deliberate: Pages deploys take 30–90 s, and Instagram
caches a URL it has already fetched — a fixed name makes it re-read yesterday's video.

## Credentials

`reel_publish2.py` reads `instagram-credentials-2.json` from `/scratch/work` or
`/scratch/saved`. Expected fields:

```json
{
  "page_id": "...",
  "page_name": "...",
  "ig_user_id": "...",
  "page_token": "...",
  "app_id": "...",
  "token_expires": "YYYY-MM-DD"
}
```

## Notes

- Only `graph.facebook.com` is reachable from the build sandbox. Direct byte upload to
  `rupload.facebook.com` is not available, which is why the public-URL route is used.
- The account-1 pipeline (`astrology-reels` / `astrology-reels-config`) is untouched and
  completely separate from this repo.
