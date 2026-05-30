#!/usr/bin/env python3
"""
music_library.py  -  fetch royalty-free background music via the Jamendo API.

WHY THIS EXISTS
  YouTube's own Audio Library is the safest music source, but it has NO public
  API - you can only download tracks by hand in YouTube Studio (see AUDIO_GUIDE.md).
  To make the daily pipeline truly hands-off we use the **Jamendo API** instead:
  a real, free, key-based music API that returns downloadable MP3s with their
  license info. Fresh, mood-matched, percussive music per render also means the
  beat-sync (beats.py) finally has real beats to snap scene cuts to.

  Designed to FAIL SOFTLY: missing key, no search hit, or a download error simply
  means this render uses whatever bgm.mp3 already sits in the channel's music/
  folder (or no music at all). A video is never blocked by Jamendo.

  LICENSING NOTE (read AUDIO_GUIDE.md): Jamendo tracks are Creative Commons and
  MANY require attribution. This module writes a `music_credits.txt` into each
  render folder and prefers tracks whose download is allowed. For 100%
  no-attribution, monetization-safe music, use the manual YouTube Audio Library /
  Pixabay path documented in AUDIO_GUIDE.md and drop bgm.mp3 in the channel folder.

SETUP (one time)
  1) Create a free app at  https://devportal.jamendo.com  -> copy your Client ID.
  2) Put it in the project's .env:
         JAMENDO_CLIENT_ID=your_client_id_here
     (A public test client id `709fa152` exists for trying the read API, but get
      your own for reliable use.)

USAGE
  # as a module (how make_video.py calls it)
  from music_library import fetch_render_bgm
  path = fetch_render_bgm(work_dir, "electronic upbeat energetic")  # -> work/music.mp3 or None

  # prefetch a cache pool for a mood (offline-friendly)
  python scripts/music_library.py --tags "cinematic motivational" --prefetch 6
  python scripts/music_library.py --list
"""

import argparse
import json
import os
import random
import re
import shutil
import urllib.parse
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(PROJECT_ROOT, "assets", "music")
API_TRACKS = "https://api.jamendo.com/v3.0/tracks/"
TEST_CLIENT_ID = "709fa152"          # Jamendo's public read-only test id (fallback)
DOWNLOAD_TIMEOUT = 90


# ---------------------------------------------------------------- env
def _load_env_value(name):
    nl = name.lower()
    val = os.environ.get(name) or os.environ.get(nl)
    if val:
        return val.strip()
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip().lower() == nl:
                v = v.strip().strip('"').strip("'")
                if v:
                    return v
    return None


def _client_id():
    return _load_env_value("JAMENDO_CLIENT_ID") or TEST_CLIENT_ID


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "music").lower()).strip("-")[:40] or "music"


# ---------------------------------------------------------------- API
def _search_tracks(tags, client_id, limit=12):
    """Return a list of Jamendo track dicts for a mood/tag string. [] on error.

    We ask for instrumental tracks (no vocals fighting the voiceover), order by
    popularity (cleaner / better mixed), and only ones whose download is allowed."""
    params = {
        "client_id": client_id,
        "format": "json",
        "limit": str(limit),
        "fuzzytags": tags.replace(",", " ").strip(),
        "vocalinstrumental": "instrumental",
        "audioformat": "mp32",                 # 192 kbps mp3
        "include": "musicinfo licenses",
        "order": "popularity_total",
        "audiodlallowed": "true",
        "groupby": "artist_id",                # variety: avoid 12 tracks from one artist
    }
    url = API_TRACKS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "youtube-engine/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print(f"[music] Jamendo search failed for '{tags}': {e}")
        return []
    status = (data.get("headers") or {}).get("status")
    if status and status != "success":
        print(f"[music] Jamendo API status: {status} - {(data.get('headers') or {}).get('error_message','')}")
    return data.get("results") or []


def _download(url, dest):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "youtube-engine/1.0"})
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return os.path.getsize(dest) > 1024
    except Exception as e:
        print(f"[music] download failed: {e}")
        return False


# ---------------------------------------------------------------- cache
def _cache_dir(tags):
    d = os.path.join(CACHE_DIR, _slug(tags))
    os.makedirs(d, exist_ok=True)
    return d


def _list_cache(tags):
    d = _cache_dir(tags)
    return [os.path.join(d, fn) for fn in os.listdir(d) if fn.lower().endswith(".mp3")]


def prefetch_cache(tags, per_mood=6, client_id=None):
    """Download a small varied pool of tracks for a mood into assets/music/<mood>/
    plus a credits sidecar. Run once per mood; renders then reuse the cache offline."""
    client_id = client_id or _client_id()
    d = _cache_dir(tags)
    existing = len(_list_cache(tags))
    if existing >= per_mood:
        print(f"[music] '{tags}': {existing} cached, skipping download.")
        return True
    need = per_mood - existing
    tracks = _search_tracks(tags, client_id, limit=per_mood * 3)
    if not tracks:
        return False
    credits = _load_credits(d)
    got = 0
    for t in tracks:
        if got >= need:
            break
        dl = t.get("audiodownload") or t.get("audio")
        if not dl or not (t.get("audiodownload_allowed", True)):
            continue
        tid = t.get("id")
        dest = os.path.join(d, f"jamendo_{tid}.mp3")
        if os.path.exists(dest):
            continue
        if _download(dl, dest):
            got += 1
            credits[f"jamendo_{tid}.mp3"] = {
                "name": t.get("name"),
                "artist": t.get("artist_name"),
                "license": (t.get("license_ccurl") or ""),
                "url": t.get("shareurl") or t.get("shorturl") or "",
            }
            print(f"  + {t.get('name','?')[:42]} by {t.get('artist_name','?')[:24]}")
    _save_credits(d, credits)
    return got > 0


def _load_credits(d):
    p = os.path.join(d, "credits.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_credits(d, credits):
    try:
        with open(os.path.join(d, "credits.json"), "w", encoding="utf-8") as f:
            json.dump(credits, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- public API
def fetch_render_bgm(work_dir, tags, client_id=None):
    """Pick a fresh mood-matched track for THIS render and copy it to
    work_dir/music.mp3. Writes work_dir/music_credits.txt with attribution.

    Returns the path to music.mp3 on success, or None (caller then falls back to
    the channel's own bgm.mp3 or renders music-free)."""
    tags = (tags or "").strip()
    if not tags:
        return None
    client_id = client_id or _client_id()

    # Fill the cache on first use for this mood (best-effort).
    if not _list_cache(tags) and _load_env_value("JAMENDO_CLIENT_ID"):
        prefetch_cache(tags, per_mood=6, client_id=client_id)
    # Even without a personal key, try a one-off search with the test id.
    if not _list_cache(tags):
        prefetch_cache(tags, per_mood=4, client_id=client_id)

    pool = _list_cache(tags)
    if not pool:
        print(f"[music] no Jamendo track available for '{tags}' - falling back.")
        return None

    src = random.choice(pool)
    dst = os.path.join(work_dir, "music.mp3")
    try:
        shutil.copyfile(src, dst)
    except Exception as e:
        print(f"[music] copy failed ({e}).")
        return None

    # write attribution sidecar
    credits = _load_credits(_cache_dir(tags)).get(os.path.basename(src), {})
    if credits:
        with open(os.path.join(work_dir, "music_credits.txt"), "w", encoding="utf-8") as f:
            f.write(
                "Background music via Jamendo (Creative Commons).\n"
                f"Track : {credits.get('name','')}\n"
                f"Artist: {credits.get('artist','')}\n"
                f"License: {credits.get('license','')}\n"
                f"Source : {credits.get('url','')}\n\n"
                "If this license requires attribution, paste the line below into your "
                "YouTube description:\n"
                f"Music: \"{credits.get('name','')}\" by {credits.get('artist','')} (Jamendo, CC).\n"
            )
        print(f"[music] BGM -> {credits.get('name','?')} by {credits.get('artist','?')} (credits written)")
    else:
        print(f"[music] BGM -> {os.path.basename(src)}")
    return dst


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="Jamendo royalty-free BGM fetcher + cache.")
    ap.add_argument("--tags", help="mood/genre tags, e.g. 'electronic upbeat'")
    ap.add_argument("--prefetch", type=int, default=0, help="download N tracks into the cache for --tags")
    ap.add_argument("--list", action="store_true", help="list cached moods + track counts")
    args = ap.parse_args()

    if args.list:
        if not os.path.isdir(CACHE_DIR):
            print("(no music cache yet)")
            return
        for mood in sorted(os.listdir(CACHE_DIR)):
            md = os.path.join(CACHE_DIR, mood)
            if os.path.isdir(md):
                n = len([f for f in os.listdir(md) if f.endswith(".mp3")])
                print(f"  {mood}: {n} track(s)")
        return

    if not args.tags:
        ap.error("--tags is required (unless --list)")
    if args.prefetch:
        prefetch_cache(args.tags, per_mood=args.prefetch)
    else:
        prefetch_cache(args.tags, per_mood=4)
    for f in _list_cache(args.tags):
        print(" ", os.path.basename(f))


if __name__ == "__main__":
    main()
