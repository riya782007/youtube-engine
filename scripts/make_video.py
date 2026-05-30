#!/usr/bin/env python3
"""
make_video.py  -  one command turns a JOB FILE into a finished Short.

PIPELINE
  job.json  ->  voice.py (Sarvam VO)  ->  caption timing + token fill
            ->  index.html in a render folder  ->  npx hyperframes render
            ->  output.mp4  +  upload.json (title/description/tags for upload.py)

USAGE
  python scripts/make_video.py --job channels/ai-tadka/jobs/example.json
  python scripts/make_video.py --job <path> --keep      # keep the work folder
  python scripts/make_video.py --job <path> --no-render  # build index.html only

WHAT YOU EDIT  ->  the JOB FILE (see channels/<name>/jobs/example.json)
  {
    "channel":     "ai-tadka",                  # folder under channels/
    "title":       "ChatGPT se resume in 2 min",
    "description": "Optional extra blurb (channel footer is appended automatically).",
    "hashtags":    ["#ai", "#chatgpt"],         # merged with channel defaults
    "music":       "music/bgm.mp3",             # optional, relative to the channel folder
    "voice":       "Pura Hinglish VO script yahan...",
    "captions": [                                # 1 to 5 on-screen captions
      { "kicker": "AI HACK", "line": "ChatGPT se *resume* sirf 2 min me" },
      { "kicker": "",        "line": "Bas *yeh prompt* paste karo" }
    ]
  }

CAPTION MARKUP (so you never touch HTML)
  *text*    -> highlighted in the channel's ACCENT colour
  **text**  -> highlighted in the channel's SECONDARY accent colour
  a newline inside a "line" becomes a line break
  emojis: paste the real emoji character (not &#...; codes)

REQUIREMENTS
  - Python 3, `pip install requests`
  - Node >= 22 and FFmpeg on PATH (hyperframes renders via headless Chrome + FFmpeg)
  - SARVAM_API_KEY in the project .env
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import wave

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
VOICE_PY = os.path.join(SCRIPT_DIR, "voice.py")

# pexels.py / transcribe.py / beats.py live next to this file. All three are
# fail-soft imports: if a module is missing, the corresponding feature degrades
# (gradient instead of B-roll, even-spread captions instead of Whisper-timed,
# no beat sync) but the render still succeeds.
sys.path.insert(0, SCRIPT_DIR)
try:
    import pexels  # noqa: E402
except Exception:
    pexels = None
try:
    import transcribe as _whisper  # noqa: E402
except Exception:
    _whisper = None
try:
    import beats as _beats  # noqa: E402
except Exception:
    _beats = None
try:
    import freesound_sfx as _fs_sfx  # noqa: E402
except Exception:
    _fs_sfx = None

MAX_CAPTIONS = 12
TAIL_PAD_S = 0.6      # silence tail so the last word/caption isn't clipped
MIN_DURATION_S = 6.0  # never make a Short shorter than this
MUSIC_VOLUME = 0.12   # background music sits well under the voice
CAPTION_GAP_S = 0.0   # v2 scenes are GSAP-driven (not clips), so they stay contiguous
SFX_WHOOSH_VOLUME = 0.45  # transition whoosh between scenes
SFX_DING_VOLUME = 0.6     # payoff ding on the final scene
# default per-scene icons if a caption doesn't specify one (kept generic/safe)
DEFAULT_ICONS = ["", "", "", "", "", "", "", "", "", "", "", ""]


# ----------------------------------------------------------- small helpers
def die(msg):
    sys.exit(f"ERROR: {msg}")


def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return (s or "short")[:50]


def markup_to_html(text):
    """Convert the friendly caption markup into safe HTML.
    Escape first (so user text can't inject tags), then re-introduce our own spans."""
    s = html.escape(text, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r'<span class="accent2">\1</span>', s)
    s = re.sub(r"\*(.+?)\*", r'<span class="accent">\1</span>', s)
    s = s.replace("\n", "<br/>")
    return s


def wav_duration_seconds(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


# ----------------------------------------------------------- core steps
def load_channel(channel_id):
    cdir = os.path.join(PROJECT_ROOT, "channels", channel_id)
    cfg_path = os.path.join(cdir, "channel.json")
    if not os.path.exists(cfg_path):
        die(f"channel '{channel_id}' not found (looked for {cfg_path})")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    tmpl = os.path.join(cdir, "compositions", "template.html")
    if not os.path.exists(tmpl):
        die(f"template not found for channel '{channel_id}' ({tmpl})")
    return cdir, cfg, tmpl


def generate_voice(job, cfg, out_wav, speaker_override=None, pace_override=None,
                   temperature_override=None):
    """Run voice.py as a subprocess to synthesize the VO wav.

    Override precedence (highest first):
      1) CLI flags                          (--speaker / --pace / --temperature)
      2) job file's voice_overrides block   ({"voice_overrides": {"speaker": ...}})
      3) channel.json voice block           ({"voice": {"speaker": "arjun", ...}})
      4) Sarvam channel preset              (built into voice.py)
    """
    voice_cfg = cfg.get("voice", {}) or {}
    job_overrides = job.get("voice_overrides", {}) or {}
    speaker = speaker_override or job_overrides.get("speaker") or voice_cfg.get("speaker")
    pace = pace_override or job_overrides.get("pace") or voice_cfg.get("pace")
    temperature = (temperature_override or job_overrides.get("temperature")
                   or voice_cfg.get("temperature"))
    preset = voice_cfg.get("channel_preset")

    cmd = [sys.executable, VOICE_PY, "--text", job["voice"], "--out", out_wav]
    # Always pass --channel so ElevenLabs can pick the channel preset voice,
    # even when --speaker (Sarvam-only) is also set. voice.py knows to skip the
    # channel preset for Sarvam when an explicit speaker is given.
    if preset:
        cmd += ["--channel", preset]
    if speaker:
        cmd += ["--speaker", speaker]
    if pace:
        cmd += ["--pace", str(pace)]
    if temperature:
        cmd += ["--temperature", str(temperature)]
    desc = f"speaker={speaker or preset or 'default'}"
    if pace: desc += f" pace={pace}"
    if temperature: desc += f" temp={temperature}"
    print(f"[voice] synthesizing VO via Sarvam ({desc})...")
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0 or not os.path.exists(out_wav):
        die("voice generation failed (see message above).")


def compute_caption_timings(n_captions, total, custom_starts=None):
    """Build (start, duration) for each of MAX_CAPTIONS slots.

    If `custom_starts` is provided (length n_captions), those are used as the
    real scene starts (e.g. snapped to word boundaries + beats). Otherwise we
    fall back to even-spread.

    Slots beyond n_captions get (total, 0) so they never appear."""
    n = max(1, min(n_captions, MAX_CAPTIONS))
    if custom_starts and len(custom_starts) >= n:
        starts = [round(float(custom_starts[i]), 2) for i in range(n)]
        # guarantee monotonic + non-zero first start
        starts[0] = 0.0
        for i in range(1, n):
            if starts[i] <= starts[i - 1] + 0.5:
                starts[i] = round(starts[i - 1] + 1.5, 2)
    else:
        seg = total / n
        starts = [round(i * seg, 2) for i in range(n)]
    timings = []
    for i in range(MAX_CAPTIONS):
        if i < n:
            start = starts[i]
            end = starts[i + 1] if i + 1 < n else total
            dur = round(max(0.5, end - start - CAPTION_GAP_S), 2)
        else:
            start, dur = total, 0
        timings.append((start, dur))
    return timings


def fill_template(template_path, tokens):
    with open(template_path, "r", encoding="utf-8") as f:
        htmltext = f.read()
    # strip the template's documentation comments so they don't ride along into
    # the rendered index.html (they contain literal {{TOKEN}} examples)
    htmltext = re.sub(r"<!--.*?-->", "", htmltext, flags=re.DOTALL)
    for k, v in tokens.items():
        htmltext = htmltext.replace("{{" + k + "}}", str(v))
    return htmltext


def build_description(job, cfg):
    parts = []
    if job.get("description"):
        parts.append(job["description"].strip())
    footer = cfg.get("seo", {}).get("description_footer")
    if footer:
        parts.append(footer.strip())
    # hashtags: job + channel defaults, de-duplicated, order preserved
    tags = list(job.get("hashtags", [])) + cfg.get("seo", {}).get("default_hashtags", [])
    seen, merged = set(), []
    for t in tags:
        t = t if t.startswith("#") else f"#{t}"
        if t.lower() not in seen:
            seen.add(t.lower())
            merged.append(t)
    if merged:
        parts.append(" ".join(merged))
    return "\n\n".join(parts)


def build_theme_tokens(cfg):
    """Pull this channel's colours/motif into the template's CSS variables."""
    th = cfg.get("theme", {})
    handle = cfg.get("handle", "")
    return {
        "BG_FROM": th.get("bg_from", "#10213d"),
        "BG_TO": th.get("bg_to", "#070d18"),
        "ACCENT": th.get("accent", "#ff7a18"),
        "ACCENT2": th.get("accent2", "#ffb347"),
        "KICKER_COLOR": th.get("kicker", "#ffc88a"),
        "TEXT_COLOR": th.get("text", "#ffffff"),
        "MOTIF": th.get("motif_emoji", ""),
        "HANDLE": handle,
    }


def build_sfx_tracks(cdir, work, scene_starts):
    """Emit <audio> tags for whoosh-per-cut + final ding.

    SFX source order:
      1) Freesound (random pick from cached CC0 pool) - fresh per render
      2) channels/<id>/music/sfx_whoosh.mp3 + sfx_ding.mp3 (curated fallback)
      3) Skip silently (render proceeds without SFX)

    Freesound option keeps every video sounding different rather than the same
    whoosh on repeat. The cache lives under assets/sfx/ and survives between
    renders, so this only hits the network on first-ever run."""
    tags = []
    whoosh_dst = os.path.join(work, "sfx_whoosh.mp3")
    ding_dst = os.path.join(work, "sfx_ding.mp3")

    # 1) Try Freesound first (fresh random SFX per render).
    if _fs_sfx is not None:
        try:
            _fs_sfx.refresh_render_sfx(work)
        except Exception as e:
            print(f"[sfx] freesound error ({e}) - falling back to channel SFX.")

    # 2) Fall back to whatever is in the channel's music folder.
    music_dir = os.path.join(cdir, "music")
    if not os.path.exists(whoosh_dst):
        src = os.path.join(music_dir, "sfx_whoosh.mp3")
        if os.path.exists(src):
            shutil.copyfile(src, whoosh_dst)
    if not os.path.exists(ding_dst):
        src = os.path.join(music_dir, "sfx_ding.mp3")
        if os.path.exists(src):
            shutil.copyfile(src, ding_dst)

    # 3) Emit tags only if files are actually present.
    if os.path.exists(whoosh_dst):
        for i, st in enumerate(scene_starts):
            tags.append(
                f'<audio id="sfx_whoosh_{i}" src="sfx_whoosh.mp3" '
                f'data-start="{round(max(0.0, st - 0.05), 2)}" data-volume="{SFX_WHOOSH_VOLUME}"></audio>'
            )
    if os.path.exists(ding_dst) and scene_starts:
        tags.append(
            f'<audio id="sfx_ding" src="sfx_ding.mp3" '
            f'data-start="{round(scene_starts[-1], 2)}" data-volume="{SFX_DING_VOLUME}"></audio>'
        )
    if tags:
        print(f"[sfx] added {len(tags)} sound-effect track(s)")
    return "\n      ".join(tags)


def build_broll_tracks(files, timings, total):
    """Turn the downloaded clip list into <video> tags for the template.
    Each clip gets its OWN track-index so windows may overlap for a crossfade.
      data-start/data-duration/data-track-index -> hyperframes seeks the clip
      data-at/data-len                          -> GSAP drives opacity + Ken Burns
    Scenes with no clip are simply omitted (gradient background shows through)."""
    tags = []
    for i, fname in enumerate(files):
        if not fname:
            continue
        start, length = timings[i]
        if start + length < total - 0.05:
            dur = round(min(total - start, length + 0.6), 2)  # small overlap for the crossfade
        else:
            dur = round(total - start, 2)                      # last clip runs to the end
        tags.append(
            f'<video id="broll_{i}" class="broll" src="{fname}" muted playsinline preload="auto" '
            f'data-start="{start}" data-duration="{dur}" data-track-index="{i}" '
            f'data-at="{start}" data-len="{length}"></video>'
        )
    if tags:
        print(f"[broll] added {len(tags)} stock-footage layer(s)")
    return "\n        ".join(tags)


def copy_assets(work):
    """Copy bundled .ttf fonts and GSAP into the render folder."""
    # 1) Fonts
    src_dir = os.path.join(PROJECT_ROOT, "assets", "fonts")
    if os.path.isdir(src_dir):
        fonts_dir = os.path.join(work, "fonts")
        os.makedirs(fonts_dir, exist_ok=True)
        for fn in os.listdir(src_dir):
            if fn.lower().endswith((".ttf", ".woff2", ".woff", ".otf")):
                shutil.copyfile(os.path.join(src_dir, fn), os.path.join(fonts_dir, fn))
    
    # 2) GSAP
    gsap_src = os.path.join(PROJECT_ROOT, "assets", "gsap.min.js")
    if os.path.exists(gsap_src):
        shutil.copyfile(gsap_src, os.path.join(work, "gsap.min.js"))


def normalize_audio(work):
    """Borrowed from the youtube-shorts-editor playbook: bring loudness to YouTube's
    -14 LUFS target so the voice sits consistent and 'produced'. Video is copied,
    only audio is re-encoded. Fails soft - the un-normalized render is kept on error."""
    src = os.path.join(work, "output.mp4")
    tmp = os.path.join(work, "output_norm.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-c:v", "copy",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", tmp,
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, src)
            print("[audio] normalized to -14 LUFS")
        else:
            if os.path.exists(tmp):
                os.remove(tmp)
            print("[audio] loudnorm skipped (ffmpeg returned non-zero) - keeping original.")
    except FileNotFoundError:
        print("[audio] ffmpeg not found - keeping original audio.")
    except Exception as e:
        print(f"[audio] loudnorm error ({e}) - keeping original.")


# ----------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Build a Short from a job file.")
    ap.add_argument("--job", required=True, help="path to a job .json file")
    ap.add_argument("--no-render", action="store_true",
                    help="build index.html + assets but skip the hyperframes render")
    ap.add_argument("--keep", action="store_true",
                    help="(default) keep the render work folder; here for clarity")
    ap.add_argument("--no-broll", action="store_true",
                    help="skip Pexels stock footage (gradient background only)")
    ap.add_argument("--no-loudnorm", action="store_true",
                    help="skip the -14 LUFS audio normalization post-step")
    ap.add_argument("--no-whisper", action="store_true",
                    help="skip Whisper word-timing (use even-spread caption starts)")
    ap.add_argument("--no-beats", action="store_true",
                    help="skip beat detection (don't snap scene cuts to music)")
    ap.add_argument("--speaker", default=None,
                    help="override Sarvam speaker (e.g. arjun, manan, shreya, kavya, rohan)")
    ap.add_argument("--pace", type=float, default=None, help="override speech pace 0.5-2.0")
    ap.add_argument("--temperature", type=float, default=None, help="override Sarvam temperature 0.01-2.0")
    args = ap.parse_args()

    job_path = os.path.abspath(args.job)
    if not os.path.exists(job_path):
        die(f"job file not found: {job_path}")
    with open(job_path, "r", encoding="utf-8") as f:
        job = json.load(f)

    for field in ("channel", "title", "voice", "captions"):
        if not job.get(field):
            die(f"job file is missing required field: '{field}'")
    captions = job["captions"][:MAX_CAPTIONS]
    if not captions:
        die("job file needs at least one caption.")

    cdir, cfg, template_path = load_channel(job["channel"])

    # render work folder: channels/<id>/renders/<slug>-<timestamp>/
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    work = os.path.join(cdir, "renders", f"{slugify(job['title'])}-{stamp}")
    os.makedirs(work, exist_ok=True)
    print(f"[setup] work folder: {work}")

    # 1) voice
    voice_wav = os.path.join(work, "voice.wav")
    generate_voice(job, cfg, voice_wav,
                   speaker_override=args.speaker,
                   pace_override=args.pace,
                   temperature_override=args.temperature)
    vo = wav_duration_seconds(voice_wav)
    total = round(max(MIN_DURATION_S, vo + TAIL_PAD_S), 2)
    print(f"[voice] VO duration {vo:.2f}s -> composition {total:.2f}s")

    # 2) optional music
    music_track = ""
    if job.get("music"):
        src = os.path.join(cdir, job["music"])
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(work, "music.mp3"))
            music_track = (
                f'<audio id="music" src="music.mp3" data-start="0" data-volume="{MUSIC_VOLUME}"></audio>'
            )
            print(f"[music] using {job['music']}")
        else:
            print(f"[music] WARNING: '{src}' not found - rendering without music.")

    # 3) scene timing -> Whisper word-snap, then beat-snap to the BGM if present.
    # Both steps are best-effort: if either fails, we silently fall back to
    # even-spread, so the render is never blocked.
    custom_starts = None
    words = None
    if not args.no_whisper and _whisper is not None:
        words = _whisper.transcribe_words(voice_wav, language="hi", model_size="base")
        if words:
            # CRITICAL: replace Whisper's text with the original script. Whisper's
            # Hindi mode sometimes outputs Urdu/Arabic script for Hinglish audio,
            # and even when it's correct it spells English brand names in Devanagari.
            # We only ever wanted the TIMINGS from Whisper, not the text.
            words = _whisper.align_words_to_script(words, job["voice"])
            custom_starts = _whisper.snap_scene_starts(words, len(captions), total)
            print(f"[whisper] scene starts (word-snapped): {custom_starts}")
    if not args.no_beats and _beats is not None and job.get("music"):
        bgm_path = os.path.join(work, "music.mp3")
        if os.path.exists(bgm_path):
            beat_times = _beats.detect_beats(bgm_path)
            if beat_times and custom_starts:
                custom_starts = _beats.snap_to_beats(custom_starts, beat_times, max_drift=0.25)
                print(f"[beats] scene starts (beat-snapped): {custom_starts}")
            elif beat_times:
                # no whisper -> snap even-spread starts to beats anyway
                seg = total / len(captions)
                tmp = [round(i * seg, 2) for i in range(len(captions))]
                custom_starts = _beats.snap_to_beats(tmp, beat_times, max_drift=0.3)
                print(f"[beats] scene starts (beat-snapped, no-whisper): {custom_starts}")

    timings = compute_caption_timings(len(captions), total, custom_starts=custom_starts)
    scene_starts = [timings[i][0] for i in range(len(captions))]
    sfx_tracks = build_sfx_tracks(cdir, work, scene_starts)

    # 3a) stock B-roll: one Pexels clip per scene "broll" search term
    broll_tracks = ""
    if not args.no_broll and pexels is not None:
        terms = []
        for i, cap in enumerate(captions):
            t = cap.get("broll") or ""
            if not t and isinstance(job.get("broll"), list) and i < len(job["broll"]):
                t = job["broll"][i]
            terms.append(t)
        if any(t.strip() for t in terms):
            durs = [timings[i][1] for i in range(len(captions))]
            try:
                files = pexels.fetch_broll(terms, durs, work)
            except Exception as e:
                print(f"[broll] fetch error ({e}) - continuing without stock footage.")
                files = [None] * len(captions)
            broll_tracks = build_broll_tracks(files, timings, total)
        else:
            print("[broll] no 'broll' search terms in job - gradient background only.")
    elif args.no_broll:
        print("[broll] --no-broll set - skipping stock footage.")

    tokens = {
        "TITLE": html.escape(job["title"], quote=True),
        "WATERMARK": cfg.get("watermark", cfg.get("name", "")),
        "DURATION": total,
        "BROLL_TRACKS": broll_tracks,
        "MUSIC_TRACK": music_track,
        "SFX_TRACKS": sfx_tracks,
        "WORD_DATA": json.dumps(words or [], ensure_ascii=False),
    }
    tokens.update(build_theme_tokens(cfg))
    for i in range(MAX_CAPTIONS):
        start, dur = timings[i]
        cap = captions[i] if i < len(captions) else {"kicker": "", "line": "", "icon": ""}
        icon = cap.get("icon", DEFAULT_ICONS[i] if i < len(DEFAULT_ICONS) else "")
        tokens[f"CAP{i+1}_AT"] = start
        tokens[f"CAP{i+1}_LEN"] = dur
        tokens[f"CAP{i+1}_ICON"] = (icon or "").strip()
        tokens[f"CAP{i+1}_KICKER"] = markup_to_html(cap.get("kicker", ""))
        tokens[f"CAP{i+1}_LINE"] = markup_to_html(cap.get("line", ""))

    index_html = fill_template(template_path, tokens)
    with open(os.path.join(work, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print("[build] index.html written")

    # 3b) bundle assets locally (fonts, gsap)
    copy_assets(work)

    # 4) upload metadata sidecar (consumed by upload.py)
    upload_meta = {
        "channel": job["channel"],
        "channel_name": cfg.get("name"),
        "title": (job["title"] + cfg.get("seo", {}).get("title_suffix", "")).strip(),
        "description": build_description(job, cfg),
        "tags": cfg.get("seo", {}).get("tags", []),
        "categoryId": str(job.get("categoryId", "27")),  # 27 = Education
        "video": "output.mp4",
        "made_at": stamp,
    }
    with open(os.path.join(work, "upload.json"), "w", encoding="utf-8") as f:
        json.dump(upload_meta, f, ensure_ascii=False, indent=2)
    print("[build] upload.json written")

    # 5) render
    if args.no_render:
        print(f"\nDONE (no render). Preview with:\n  cd \"{work}\" && npx hyperframes preview")
        return
    print("[render] running hyperframes (headless Chrome + FFmpeg)...")
    # --yes auto-confirms the one-time "install hyperframes?" prompt on first run
    cmd = ["npx", "--yes", "hyperframes", "render", "--output", "output.mp4"]
    res = subprocess.run(cmd, cwd=work, shell=(os.name == "nt"))
    out_mp4 = os.path.join(work, "output.mp4")
    if res.returncode != 0 or not os.path.exists(out_mp4):
        die("hyperframes render failed (is Node >= 22 + FFmpeg installed?).")

    # 6) audio polish: normalize loudness to the YouTube -14 LUFS target
    if not args.no_loudnorm:
        normalize_audio(work)

    size = os.path.getsize(out_mp4)
    print(f"\nDONE -> {out_mp4} ({size:,} bytes)")
    print(f"Review it, then upload with:\n  python scripts/upload.py --dir \"{work}\"")


if __name__ == "__main__":
    main()
