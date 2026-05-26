#!/usr/bin/env python3
"""
beats.py  -  beat detection for music-synced scene cuts.

WHY THIS EXISTS
  The most "produced" feeling in a Short comes from cuts landing ON THE BEAT of
  the music. librosa's beat tracker is good enough to pull this off
  automatically. We take librosa's beat times, then snap each scene boundary
  (already roughly placed by Whisper or even-spread) to the closest beat - but
  ONLY if the beat is within a small window (so we never push a scene cut far
  away from where the words actually demand it).

  Falls back to a no-op if librosa can't load the audio (rare).

USAGE  (module)
  from beats import detect_beats, snap_to_beats
  beats = detect_beats("music.mp3")
  starts = snap_to_beats(starts, beats, max_drift=0.25)

USAGE  (CLI)
  python scripts/beats.py --in music.mp3
"""

import argparse
import sys


def detect_beats(audio_path):
    """Return a sorted list of beat times in seconds, or [] on failure."""
    try:
        import librosa
    except Exception as e:
        print(f"[beats] librosa not available ({e}) - skipping beat sync.")
        return []
    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        # tightness=100 keeps the beat grid stable on EDM/lo-fi/cinematic alike
        tempo, frames = librosa.beat.beat_track(y=y, sr=sr, tightness=100)
        beat_times = librosa.frames_to_time(frames, sr=sr)
        # tempo can be a numpy scalar OR a 0-d array OR a 1-element array
        try:
            tempo_val = float(tempo)
        except Exception:
            tempo_val = float(getattr(tempo, "item", lambda: 0.0)())
        beats_list = [round(float(t), 3) for t in beat_times]
        print(f"[beats] tempo ~{tempo_val:.1f} BPM, {len(beats_list)} beats found")
        return beats_list
    except Exception as e:
        print(f"[beats] detection failed ({e}) - skipping beat sync.")
        return []


def snap_to_beats(starts, beats, max_drift=0.25):
    """For each scene start, snap to the nearest beat if it's within max_drift.
    Otherwise leave the start where it is."""
    if not beats or not starts:
        return starts
    out = [starts[0]]  # always pin first scene to 0
    for t in starts[1:]:
        nearest = min(beats, key=lambda b: abs(b - t))
        if abs(nearest - t) <= max_drift:
            out.append(round(nearest, 2))
        else:
            out.append(round(t, 2))
    # enforce minimum scene length
    for i in range(1, len(out)):
        if out[i] - out[i - 1] < 1.2:
            out[i] = round(out[i - 1] + 1.2, 2)
    return out


def main():
    ap = argparse.ArgumentParser(description="Beat detection for music-synced cuts.")
    ap.add_argument("--in", dest="infile", required=True, help="path to music file")
    args = ap.parse_args()
    b = detect_beats(args.infile)
    if not b:
        sys.exit("no beats")
    print(b[:30], f"... ({len(b)} total)")


if __name__ == "__main__":
    main()
