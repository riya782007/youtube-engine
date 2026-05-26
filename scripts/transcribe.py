#!/usr/bin/env python3
"""
transcribe.py  -  word-level caption timing via faster-whisper.

WHY THIS EXISTS
  The previous engine spread N captions evenly across the voiceover. That looks
  fine but never feels in-sync with what's actually being spoken. faster-whisper
  gives us per-WORD timestamps; we use them two ways:

  1) "snap" mode  - move each scene boundary to the nearest real word boundary
                    in the VO so each scene starts when its idea actually starts.
  2) "words" mode - return the full word list so the template can render a
                    karaoke-style word-by-word reveal that matches the speech.

  Falls back gracefully: if the model can't load (no internet on first run, no
  CPU cycles, etc.) we just return None and the caller uses even-spread timing.

USAGE  (as a module - this is how make_video.py calls it)
  from transcribe import transcribe_words, snap_scene_starts
  words = transcribe_words("voice.wav", language="hi")
  if words:
      starts = snap_scene_starts(words, n_scenes=5, total=18.4)

USAGE  (CLI test)
  python scripts/transcribe.py --in voice.wav --lang hi
"""

import argparse
import json
import os
import sys


# ---------------------------------------------------------------- model load
_MODEL = None


def _load_model(size="small", compute_type="int8"):
    """Lazy-load a faster-whisper model. 'small' is the sweet spot for Hinglish
    on a CPU laptop: ~470MB, ~3-5x realtime, accurate enough for caption timing.
    int8 keeps memory low so it never crashes the render box."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        print(f"[whisper] faster-whisper not available ({e}) - skipping word timing.")
        return None
    try:
        print(f"[whisper] loading model '{size}' ({compute_type}) - first run downloads ~470MB...")
        _MODEL = WhisperModel(size, device="cpu", compute_type=compute_type)
        return _MODEL
    except Exception as e:
        print(f"[whisper] model load failed ({e}) - falling back to even-spread timing.")
        return None


# ---------------------------------------------------------------- transcription
def align_words_to_script(words, script_text):
    """Replace Whisper's transcribed text with the ORIGINAL script words while
    keeping Whisper's timing. This fixes two real problems:
      1) Whisper sometimes detects Hinglish as Urdu and writes Arabic-looking
         text into the captions (your last render had this).
      2) Spelling drift: 'ChatGPT' becomes 'चैट जीपीटी' in Hindi mode.

    Strategy: tokenize the script into words, then walk Whisper's word list
    in order and zip them. If counts differ, we evenly distribute the script
    tokens across the Whisper time range so timing degrades gracefully.

    Returns a NEW word list (same shape as Whisper's), or the original list
    if alignment isn't possible."""
    if not words or not script_text:
        return words
    # tokenize the script: keep words, drop pure punctuation
    import re as _re
    tokens = _re.findall(r"\S+", script_text)
    tokens = [t.strip(" ,.!?;:\"'()[]{}*").strip() for t in tokens]
    tokens = [t for t in tokens if t]
    if not tokens:
        return words
    n_tok = len(tokens)
    n_w = len(words)
    if n_tok == n_w:
        # perfect 1:1 alignment - just swap the text
        return [{"word": tokens[i], "start": words[i]["start"], "end": words[i]["end"]}
                for i in range(n_w)]
    # counts differ -> stretch the script tokens across Whisper's time range
    t0 = words[0]["start"]; t1 = words[-1]["end"]
    span = max(0.1, t1 - t0)
    out = []
    for i, tok in enumerate(tokens):
        a = t0 + span * (i / n_tok)
        b = t0 + span * ((i + 1) / n_tok)
        out.append({"word": tok, "start": round(a, 3), "end": round(b, 3)})
    print(f"[whisper] aligned {n_tok} script tokens across {n_w} whisper words "
          f"(re-distributed timings)")
    return out


def transcribe_words(wav_path, language="hi", model_size="small"):
    """Return a list of {word, start, end} dicts (in seconds), or None on failure.
    `language='hi'` works well for Hinglish since Whisper transcribes the Hindi
    parts in Devanagari and English words in Latin - exactly what we want for
    timing (we don't display Whisper's text, only its timestamps)."""
    model = _load_model(model_size)
    if model is None:
        return None
    if not os.path.exists(wav_path):
        print(f"[whisper] wav not found: {wav_path}")
        return None
    try:
        segments, _info = model.transcribe(
            wav_path,
            language=language,
            word_timestamps=True,
            vad_filter=True,           # trim silences -> tighter word timings
            beam_size=1,                # faster; quality is plenty for timing
        )
        words = []
        for seg in segments:
            for w in (seg.words or []):
                txt = (w.word or "").strip()
                if not txt:
                    continue
                words.append({
                    "word": txt,
                    "start": float(w.start),
                    "end": float(w.end),
                })
        if not words:
            print("[whisper] no words returned - falling back to even-spread.")
            return None
        print(f"[whisper] transcribed {len(words)} word(s) "
              f"({words[0]['start']:.2f}s -> {words[-1]['end']:.2f}s)")
        return words
    except Exception as e:
        print(f"[whisper] transcribe failed ({e}) - falling back to even-spread.")
        return None


# ---------------------------------------------------------------- scene snapping
def snap_scene_starts(words, n_scenes, total, tail_pad=0.6):
    """Pick scene start times that align with real word boundaries.

    Strategy: divide the total duration into N equal chunks (the "ideal"), then
    for each ideal start time, snap to the nearest word boundary within a
    +/- 0.4s window. If no word is close enough, keep the even-spread time.
    Returns a list of N start times (first is always 0)."""
    if not words or n_scenes <= 1:
        seg = total / max(1, n_scenes)
        return [round(i * seg, 2) for i in range(n_scenes)]

    seg = total / n_scenes
    starts = [0.0]
    word_starts = [w["start"] for w in words]
    for i in range(1, n_scenes):
        ideal = i * seg
        # find the closest word start to `ideal`
        best = min(word_starts, key=lambda t: abs(t - ideal))
        if abs(best - ideal) <= 0.4:
            starts.append(round(best, 2))
        else:
            starts.append(round(ideal, 2))
    # ensure monotonic + each scene gets at least 1.5s
    for i in range(1, len(starts)):
        if starts[i] - starts[i - 1] < 1.5:
            starts[i] = round(starts[i - 1] + 1.5, 2)
    return starts


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="Word-level caption timing via faster-whisper.")
    ap.add_argument("--in", dest="infile", required=True, help="path to voice.wav")
    ap.add_argument("--lang", default="hi", help="ISO 639-1 (hi for Hinglish, en for English)")
    ap.add_argument("--size", default="small", help="model size: tiny|base|small|medium|large-v3")
    args = ap.parse_args()
    words = transcribe_words(args.infile, language=args.lang, model_size=args.size)
    if not words:
        sys.exit("FAILED")
    print(json.dumps(words[:30], indent=2, ensure_ascii=False))
    print(f"... ({len(words)} words total)")


if __name__ == "__main__":
    main()
