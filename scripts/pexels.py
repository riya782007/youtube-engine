#!/usr/bin/env python3
"""
pexels.py  -  fetch portrait stock B-roll for each scene of a Short.

WHY THIS EXISTS
  v3 of the engine layers real, moving stock footage BEHIND the motion-graphics
  text. That single change is what makes a faceless Short feel "produced" instead
  of like a slideshow. This module finds one good vertical clip per scene on
  Pexels, downloads it, and standardises it to exactly 1080x1920 H.264 trimmed to
  the scene's length (so hyperframes decodes a small, predictable file).

  Designed to FAIL SOFTLY: if the key is missing, a search returns nothing, or a
  download/transcode errors, the scene simply gets no B-roll and the engine falls
  back to the animated gradient background. A video is never blocked by Pexels.

SETUP (one time)
  1) pip install requests
  2) Put your key in the project's .env:
         PEXELS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  3) ffmpeg must be on PATH (it already is - hyperframes uses it).

USAGE
  # as a module (how make_video.py calls it)
  from pexels import fetch_broll
  files = fetch_broll(terms, durations, work_dir)   # -> ["broll_0.mp4", None, ...]

  # standalone test
  python scripts/pexels.py --terms "robot,money,city street" --out ./test_broll
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

try:
    import requests  # pip install requests
except ImportError:
    requests = None

API_SEARCH = "https://api.pexels.com/videos/search"
TARGET_W = 1080
TARGET_H = 1920
PAD_S = 0.5            # a little extra footage past the scene so cuts feel clean
PER_PAGE = 8          # candidates to consider per term
DOWNLOAD_TIMEOUT = 60


# ---------------------------------------------------------------- key loading
def load_api_key():
    """env var -> scripts/.env -> project-root/.env  (same order as voice.py)."""
    key = os.environ.get("PEXELS_API_KEY")
    if key:
        return key.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for env_path in (os.path.join(here, ".env"), os.path.join(os.path.dirname(here), ".env")):
        if not os.path.exists(env_path):
            continue
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "PEXELS_API_KEY":
                    val = v.strip().strip('"').strip("'")
                    if val:
                        return val
    return None


# ---------------------------------------------------------------- search + pick
def _search_videos(key, query):
    """Return Pexels 'videos' list for a portrait query, or [] on any error."""
    headers = {"Authorization": key}
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "medium",
        "per_page": PER_PAGE,
    }
    try:
        r = requests.get(API_SEARCH, headers=headers, params=params, timeout=30)
    except requests.RequestException as e:
        print(f"  [pexels] network error for '{query}': {e}")
        return []
    if r.status_code != 200:
        print(f"  [pexels] '{query}' -> HTTP {r.status_code}: {r.text[:120]}")
        return []
    return r.json().get("videos", []) or []


def _best_file(video):
    """Pick the most suitable mp4 rendition: portrait, smallest that is still
    >= 1080 wide if possible, else the largest available. Returns a link or None."""
    files = [f for f in video.get("video_files", []) if (f.get("file_type") == "video/mp4" and f.get("link"))]
    if not files:
        return None
    portrait = [f for f in files if (f.get("height") or 0) >= (f.get("width") or 0)] or files
    # prefer renditions at least as wide as our target, smallest of those (less to download)
    big_enough = sorted([f for f in portrait if (f.get("width") or 0) >= TARGET_W],
                        key=lambda f: f.get("width") or 0)
    if big_enough:
        return big_enough[0]["link"]
    # otherwise the largest we can get
    return sorted(portrait, key=lambda f: f.get("width") or 0, reverse=True)[0]["link"]


def _download(url, dest):
    try:
        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
        return os.path.getsize(dest) > 0
    except Exception as e:
        print(f"  [pexels] download failed: {e}")
        return False


def _standardise(src, dst, seconds):
    """Crop/scale to exactly 1080x1920, trim to `seconds`, re-encode H.264 yuv420p.
    Keeping every clip identical makes the hyperframes render fast and predictable."""
    dur = max(1.0, round(seconds + PAD_S, 2))
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},fps=30,setsar=1"
    )
    cmd = [
        "ffmpeg", "-y", "-i", src, "-t", str(dur),
        "-vf", vf, "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
        "-movflags", "+faststart", dst,
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0
    except FileNotFoundError:
        print("  [pexels] ffmpeg not found on PATH - cannot standardise clips.")
        return False


# ---------------------------------------------------------------- public API
def fetch_broll(terms, durations, work_dir, api_key=None):
    """Download + standardise one clip per scene.

    terms      list[str]   search query per scene (use "" to skip a scene)
    durations  list[float] scene length in seconds (same length as terms)
    work_dir   str         render folder; files saved as broll_<i>.mp4
    returns    list        filename ("broll_0.mp4") or None for each scene
    """
    out = [None] * len(terms)
    if requests is None:
        print("[pexels] 'requests' not installed - skipping B-roll (pip install requests).")
        return out
    key = api_key or load_api_key()
    if not key:
        print("[pexels] no PEXELS_API_KEY found - skipping B-roll (gradient background only).")
        return out

    os.makedirs(work_dir, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="broll_dl_")
    seen_ids = set()
    for i, term in enumerate(terms):
        term = (term or "").strip()
        if not term:
            continue
        dur = durations[i] if i < len(durations) else 3.0
        print(f"[pexels] scene {i+1}: searching '{term}'...")
        videos = _search_videos(key, term)
        link = None
        for v in videos:
            if v.get("id") in seen_ids:   # avoid the same clip twice in one video
                continue
            link = _best_file(v)
            if link:
                seen_ids.add(v.get("id"))
                break
        if not link:
            print(f"  [pexels] no usable clip for '{term}' - scene falls back to gradient.")
            continue
        raw = os.path.join(tmpdir, f"raw_{i}.mp4")
        final_name = f"broll_{i}.mp4"
        final_path = os.path.join(work_dir, final_name)
        if _download(link, raw) and _standardise(raw, final_path, dur):
            out[i] = final_name
            print(f"  [pexels] scene {i+1} -> {final_name} ({os.path.getsize(final_path):,} bytes)")
        else:
            print(f"  [pexels] scene {i+1} failed - falls back to gradient.")
    got = sum(1 for x in out if x)
    print(f"[pexels] B-roll ready for {got}/{len(terms)} scene(s).")
    return out


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="Fetch portrait Pexels B-roll per scene.")
    ap.add_argument("--terms", required=True, help="comma-separated search terms (one per scene)")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--secs", default="", help="comma-separated scene seconds (optional)")
    args = ap.parse_args()
    terms = [t.strip() for t in args.terms.split(",")]
    if args.secs:
        durs = [float(x) for x in args.secs.split(",")]
    else:
        durs = [3.0] * len(terms)
    files = fetch_broll(terms, durs, os.path.abspath(args.out))
    print("RESULT:", files)


if __name__ == "__main__":
    main()
