#!/usr/bin/env python3
"""
freesound_sfx.py  -  fetch real curated CC0 SFX from Freesound on demand.

WHY THIS EXISTS
  Using the same Mixkit whoosh on every video gets stale and predictable.
  Freesound has thousands of CC0 (public-domain) SFX with stable preview URLs.
  This module:
    1) caches a small library of whooshes + dings under assets/sfx/
    2) on each render, copies a random one into the channel's music folder
       (just for that render - the per-channel folder gets fresh SFX every time)

  Fail-soft: if Freesound is unreachable or the key is missing, the engine
  falls back to whatever SFX already live in channels/<id>/music/ (or no SFX).

USAGE  (module - this is how make_video.py calls it)
  from freesound_sfx import refresh_render_sfx
  refresh_render_sfx(work_dir)   # picks a random whoosh + ding for this render

USAGE  (CLI - prefetch the cache)
  python scripts/freesound_sfx.py --prefetch 8     # download 8 of each into cache
"""

import argparse
import json
import os
import random
import shutil
import sys
import urllib.parse
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(PROJECT_ROOT, "assets", "sfx")
WHOOSH_DIR = os.path.join(CACHE_DIR, "whoosh")
DING_DIR = os.path.join(CACHE_DIR, "ding")

API_BASE = "https://freesound.org/apiv2"


# ---------------------------------------------------------------- env loading
def _load_env_value(name):
    """Read NAME from environment or project .env. Match env names case-insensitively."""
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


# ---------------------------------------------------------------- API helpers
def _search(query, max_duration, page_size, key):
    """Query Freesound for short CC0 sounds matching `query`. Returns list of dicts."""
    params = {
        "query": query,
        "filter": f"duration:[0 TO {max_duration}] license:\"Creative Commons 0\"",
        "fields": "id,name,duration,previews,license",
        "page_size": page_size,
        "token": key,
        "sort": "rating_desc",  # higher-rated sounds first - usually cleaner
    }
    url = API_BASE + "/search/text/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "youtube-engine/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        return data.get("results") or []
    except Exception as e:
        print(f"[freesound] search failed for '{query}': {e}")
        return []


def _download(url, dest):
    """Stream a URL to a local file. Returns True on success."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "youtube-engine/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return os.path.getsize(dest) > 0
    except Exception as e:
        print(f"[freesound] download failed: {e}")
        return False


# ---------------------------------------------------------------- cache management
def _cache_dir(kind):
    """kind = 'whoosh' | 'ding'."""
    d = WHOOSH_DIR if kind == "whoosh" else DING_DIR
    os.makedirs(d, exist_ok=True)
    return d


def _list_cache(kind):
    d = _cache_dir(kind)
    return [os.path.join(d, fn) for fn in os.listdir(d)
            if fn.lower().endswith((".mp3", ".wav", ".ogg"))]


def prefetch_cache(per_kind=6, key=None):
    """Download a small varied pool of SFX into the project cache so renders
    don't depend on the network. Run once after install (or whenever you want
    to refresh the pool)."""
    if key is None:
        key = _load_env_value("FREESOUND_API_KEY")
    if not key:
        print("[freesound] FREESOUND_API_KEY missing - prefetch skipped.")
        return False

    queries = {
        "whoosh": [
            ("whoosh transition short", 1.5),
            ("swoosh fast", 1.2),
            ("transition swoosh", 1.5),
            ("cinematic whoosh", 2.0),
        ],
        "ding": [
            ("notification pop short", 1.0),
            ("bell ding short", 1.0),
            ("ui click positive", 0.8),
            ("notification soft", 1.2),
        ],
    }

    for kind, qlist in queries.items():
        d = _cache_dir(kind)
        existing = len(_list_cache(kind))
        if existing >= per_kind:
            print(f"[freesound] {kind}: {existing} cached, skipping download.")
            continue
        need = per_kind - existing
        print(f"[freesound] caching {need} {kind}(s)...")
        downloaded = 0
        for query, max_dur in qlist:
            if downloaded >= need:
                break
            results = _search(query, max_dur, page_size=8, key=key)
            for r in results:
                if downloaded >= need:
                    break
                preview = (r.get("previews") or {}).get("preview-hq-mp3")
                if not preview:
                    continue
                fname = f"fs_{r['id']}.mp3"
                dest = os.path.join(d, fname)
                if os.path.exists(dest):
                    continue
                if _download(preview, dest):
                    downloaded += 1
                    print(f"  + {kind} {r['id']} '{r['name'][:40]}' ({r['duration']:.2f}s)")
    return True


# ---------------------------------------------------------------- public API
def refresh_render_sfx(work_dir):
    """Pick a random whoosh + ding from the cache and copy them into the
    render's working folder as sfx_whoosh.mp3 / sfx_ding.mp3.

    If the cache is empty AND a key exists, prefetch a few first.
    Returns (whoosh_path or None, ding_path or None).

    Note: this writes into the RENDER folder, not the channel folder, so each
    render gets its own random SFX while the channel's curated music folder
    stays untouched."""
    key = _load_env_value("FREESOUND_API_KEY")
    if key and (not _list_cache("whoosh") or not _list_cache("ding")):
        prefetch_cache(per_kind=6, key=key)

    out_w = out_d = None
    pool_w = _list_cache("whoosh")
    pool_d = _list_cache("ding")
    if pool_w:
        src = random.choice(pool_w)
        out_w = os.path.join(work_dir, "sfx_whoosh.mp3")
        shutil.copyfile(src, out_w)
        print(f"[freesound] whoosh -> {os.path.basename(src)}")
    if pool_d:
        src = random.choice(pool_d)
        out_d = os.path.join(work_dir, "sfx_ding.mp3")
        shutil.copyfile(src, out_d)
        print(f"[freesound] ding -> {os.path.basename(src)}")
    return out_w, out_d


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="Freesound SFX cache + per-render picker.")
    ap.add_argument("--prefetch", type=int, default=0,
                    help="Download N whooshes + N dings into the cache.")
    ap.add_argument("--list", action="store_true", help="Show cached SFX.")
    args = ap.parse_args()

    if args.list:
        for kind in ("whoosh", "ding"):
            files = _list_cache(kind)
            print(f"{kind} ({len(files)}):")
            for f in files:
                print(f"  {os.path.basename(f)}")
        return

    if args.prefetch:
        prefetch_cache(per_kind=args.prefetch)
        for kind in ("whoosh", "ding"):
            n = len(_list_cache(kind))
            print(f"  {kind}: {n} files cached")


if __name__ == "__main__":
    main()
