#!/usr/bin/env python3
"""
voice.py  -  Hinglish voiceover generator using Sarvam AI (Bulbul v3).

Turns a script (Devanagari / Hinglish / code-mixed) into a single WAV voiceover,
ready to drop into a Hyperframes composition as an <audio> track.

WHY THIS EXISTS
  Hyperframes renders great motion-graphics but its built-in TTS (Kokoro) is
  English-leaning. Sarvam's Bulbul v3 is purpose-built for Hindi/Hinglish, so we
  generate the voice here, then let Hyperframes' `transcribe` (Whisper) time the
  captions to this WAV.

SETUP (one time)
  1) pip install requests
  2) Put your key in a file named  .env  next to this script:
         SARVAM_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxx
     (Never hard-code the key. Never commit .env to git.)

USAGE
  # from a script file
  python voice.py --in script.txt --out voice.wav --speaker shreya

  # or inline text
  python voice.py --text "Crush saamne aaya aur dimaag blank ho gaya." --out voice.wav

  # per-channel voice presets (overrides --speaker)
  python voice.py --in script.txt --out voice.wav --channel finance

CHANNEL VOICE PRESETS  (edit freely; any Bulbul v3 speaker name works)
  ai        -> rohan   (energetic modern male)   -> "AI Tools & How-To"
  finance   -> shreya  (warm, trustworthy female)-> "Personal Finance & Money Skills"
  business  -> manan   (authoritative male)      -> "Business & Startup Stories"

VALID BULBUL v3 SPEAKERS (lowercase, case-sensitive):
  shubh, aditya, ritu, priya, neha, rahul, pooja, rohan, simran, kavya, amit,
  dev, ishita, shreya, ratan, varun, manan, sumit, roopa, kabir, aayan,
  ashutosh, advait, anand, tanya, tarun, sunny, mani, gokul, vijay, shruti,
  suhani, mohit, kavitha, rehan, soham, rupali
"""

import argparse
import base64
import io
import os
import re
import sys
import time
import wave

import requests  # pip install requests

API_URL = "https://api.sarvam.ai/text-to-speech"
MODEL = "bulbul:v3"
LANG_DEFAULT = "hi-IN"
SAMPLE_RATE = 24000
MAX_CHARS = 1400          # safe chunk size (v3 allows 2500; we stay conservative)
GAP_MS = 140             # small silence inserted between chunks for natural pacing
MAX_RETRIES = 4

# Bulbul v3 infers prosody (pauses, emphasis, tone) from context + punctuation, and
# `temperature` trades "monotone/consistent" vs "human/expressive". These presets lean
# slightly expressive so the delivery doesn't sound robotic, while staying stable.
CHANNEL_PRESETS = {
    "ai":       {"speaker": "rohan",  "pace": 1.04, "temperature": 0.72},
    "finance":  {"speaker": "shreya", "pace": 0.98, "temperature": 0.68},
    "business": {"speaker": "manan",  "pace": 1.0,  "temperature": 0.70},
}

# ---------------------------------------------------------------- ElevenLabs (optional)
# ElevenLabs' multilingual model gives the most natural Hindi/Hinglish delivery and is
# the real fix when Sarvam still sounds slightly "unreal". It is OFF by default; the
# engine switches to it automatically the moment ELEVENLABS_API_KEY exists in .env.
#   - model: eleven_multilingual_v2 (handles Hindi + code-mixed English well)
#   - we request raw 24kHz PCM and wrap it in a WAV header so the rest of the pipeline
#     (chunk stitching, hyperframes caption timing) is unchanged.
# Voice IDs below are ElevenLabs' long-standing default-library voices (stable across
# accounts). Override any of them in .env with ELEVENLABS_VOICE_<CHANNEL> or
# ELEVENLABS_VOICE_ID, or per-run with --voice-id.
ELEVEN_API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_OUTPUT = "pcm_24000"     # raw 16-bit mono PCM @ 24kHz -> we wrap to WAV
ELEVEN_PRESETS = {
    # AI Tadka -> Liam: explicitly built for social-media shorts (energetic, modern).
    # For Hindi/Hinglish, eleven_multilingual_v2 handles the language; the voice
    # affects English-word delivery and overall energy. Higher style = more
    # expression but more pronunciation drift; we keep it moderate.
    "ai":       {"voice_id": "TX3LPaxmHKxFdv7VOQHJ", "stability": 0.42, "similarity_boost": 0.82, "style": 0.38},  # Liam
    # Paisa Pathshala -> Sarah: mature, reassuring, "tv host" delivery for finance trust.
    "finance":  {"voice_id": "EXAVITQu4vr4xnSDxMaL", "stability": 0.55, "similarity_boost": 0.85, "style": 0.22},  # Sarah
    # Dhandha Dimaag -> George: warm, captivating storyteller for business narratives.
    "business": {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "stability": 0.50, "similarity_boost": 0.85, "style": 0.30},  # George
}
ELEVEN_DEFAULT = {"voice_id": "pNInz6obpgDQGcFmaJgB", "stability": 0.45, "similarity_boost": 0.82, "style": 0.30}


def pcm16_to_wav_bytes(pcm, rate=SAMPLE_RATE):
    """Wrap raw little-endian 16-bit mono PCM in a WAV container (in memory)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def synth_chunk_eleven(key, text, voice_id, settings):
    """Call ElevenLabs TTS for one chunk; return WAV bytes."""
    url = f"{ELEVEN_API_BASE}/{voice_id}?output_format={ELEVEN_OUTPUT}"
    headers = {"xi-api-key": key, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": ELEVEN_MODEL,
        "voice_settings": {
            "stability": settings["stability"],
            "similarity_boost": settings["similarity_boost"],
            "style": settings["style"],
            "use_speaker_boost": True,
        },
    }
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
        except requests.RequestException as e:
            last_err = f"network error: {e}"
            time.sleep(2 * attempt)
            continue
        if r.status_code == 200:
            return pcm16_to_wav_bytes(r.content)
        if r.status_code in (429, 500, 502, 503):
            last_err = f"{r.status_code}: {r.text[:200]}"
            time.sleep(2 * attempt)
            continue
        sys.exit(f"ERROR {r.status_code} from ElevenLabs: {r.text[:400]}")
    sys.exit(f"ERROR: ElevenLabs failed after {MAX_RETRIES} retries. Last: {last_err}")


def resolve_eleven_voice(channel, voice_id_arg):
    """Pick voice id + settings: --voice-id > ELEVENLABS_VOICE_<CH> > ELEVENLABS_VOICE_ID
    > channel preset > global default."""
    preset = ELEVEN_PRESETS.get(channel, ELEVEN_DEFAULT)
    voice_id = (
        voice_id_arg
        or (load_env_value(f"ELEVENLABS_VOICE_{channel.upper()}") if channel else None)
        or load_env_value("ELEVENLABS_VOICE_ID")
        or preset["voice_id"]
    )
    return voice_id, preset


# ---------------------------------------------------------------- key loading
def load_env_value(name):
    """Read NAME from the environment, or from the first .env we find.

    Search order: env var -> scripts/.env (next to this file) -> project-root .env
    (one level up). Returns None if not found. Used for SARVAM_API_KEY,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, etc.
    """
    val = os.environ.get(name)
    if val:
        return val.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, ".env"),                       # scripts/.env
        os.path.join(os.path.dirname(here), ".env"),      # project-root/.env
    ]
    for env_path in candidates:
        if not os.path.exists(env_path):
            continue
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == name:
                    out = v.strip().strip('"').strip("'")
                    if out:
                        return out
    return None


def load_api_key():
    """Sarvam key (kept for backward compatibility); exits if missing."""
    key = load_env_value("SARVAM_API_KEY")
    if not key:
        sys.exit(
            "ERROR: No Sarvam API key found.\n"
            "  Put your key in the project's .env file:\n"
            "      SARVAM_API_KEY=sk_your_key_here\n"
            "  or set the SARVAM_API_KEY environment variable."
        )
    return key


# ---------------------------------------------------------------- prosody normalize
def normalize_for_speech(text):
    """Light touch-ups that help Bulbul v3 read Hinglish naturally.

    Bulbul v3 derives pauses/emphasis from punctuation, so we make punctuation clean
    and consistent (this is the single biggest lever on 'does it sound robotic').
      - normalize whitespace
      - guarantee a space AFTER sentence punctuation (so words don't run together)
      - collapse 4+ dots to a 3-dot ellipsis (a natural dramatic pause)
      - ensure the script ends on a terminal mark so the last line gets full intonation

    SCRIPT-WRITING TIPS (do these in the job's "voice" text for best results):
      - Write the way you'd SAY it: short sentences, commas where you'd breathe.
      - Use ? for questions and ... for a beat before a reveal.
      - Keep common English words in Latin (AI, ChatGPT, resume) - v3 handles code-mix.
      - If a specific English word is mispronounced, spell it phonetically in Devanagari.
      - Write big numbers in words for a guaranteed reading (e.g. "ninety-nine" / "nintyaanve").
    """
    if not text:
        return text
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"[ \t]+", " ", text)            # collapse runs of spaces/tabs
    text = re.sub(r"\.{4,}", "...", text)           # 4+ dots -> ellipsis
    text = re.sub(r"\s+([,.!?।])", r"\1", text)     # no space before punctuation
    # ensure a space AFTER a punctuation mark only when a letter follows - this keeps
    # ellipses ("...") and 3.14 and "?!" intact while fixing "word,word" run-ons
    text = re.sub(r"([,.!?।])(?=[^\s\d.,!?।])", r"\1 ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)    # tidy newlines
    if text and text[-1] not in ".!?।":
        text += "."
    return text


# ---------------------------------------------------------------- text chunking
def chunk_text(text, max_chars=MAX_CHARS):
    """Split on sentence boundaries (Devanagari danda, ., !, ?, newlines), then pack
    sentences into chunks under max_chars without breaking words."""
    text = text.strip()
    # split but keep it simple & robust for mixed Hindi/English
    parts = re.split(r"(?<=[।.!?\n])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    chunks, cur = [], ""
    for p in parts:
        # if a single sentence is itself too long, hard-split it
        while len(p) > max_chars:
            chunks.append(p[:max_chars])
            p = p[max_chars:]
        if len(cur) + len(p) + 1 <= max_chars:
            cur = (cur + " " + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks or [text[:max_chars]]


# ---------------------------------------------------------------- Sarvam call
def synth_chunk(key, text, speaker, lang, pace, temperature):
    """Call Sarvam TTS for one chunk; return raw WAV bytes."""
    headers = {"api-subscription-key": key, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "target_language_code": lang,
        "model": MODEL,
        "speaker": speaker,
        "pace": pace,
        "temperature": temperature,
        "speech_sample_rate": SAMPLE_RATE,
    }
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        except requests.RequestException as e:
            last_err = f"network error: {e}"
            time.sleep(2 * attempt)
            continue
        if r.status_code == 200:
            data = r.json()
            audios = data.get("audios") or []
            if not audios:
                sys.exit(f"ERROR: empty audio in response: {data}")
            return base64.b64decode(audios[0])
        if r.status_code in (429, 500, 502, 503):
            last_err = f"{r.status_code}: {r.text[:200]}"
            time.sleep(2 * attempt)  # backoff and retry
            continue
        # non-retryable
        sys.exit(f"ERROR {r.status_code}: {r.text[:400]}")
    sys.exit(f"ERROR: failed after {MAX_RETRIES} retries. Last: {last_err}")


# ---------------------------------------------------------------- WAV stitching
def _silence_frames(params, ms):
    n = int(params.framerate * ms / 1000)
    return b"\x00" * (n * params.sampwidth * params.nchannels)


def stitch_wavs(wav_bytes_list, out_path):
    """Concatenate multiple in-memory WAVs into one WAV file with small gaps."""
    params = None
    frames = []
    for wb in wav_bytes_list:
        with wave.open(io.BytesIO(wb), "rb") as w:
            if params is None:
                params = w.getparams()
            frames.append(w.readframes(w.getnframes()))
    gap = _silence_frames(params, GAP_MS)
    with wave.open(out_path, "wb") as out:
        out.setparams(params)
        for i, fr in enumerate(frames):
            out.writeframes(fr)
            if i != len(frames) - 1:
                out.writeframes(gap)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Hinglish voiceover generator (Sarvam / ElevenLabs)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--in", dest="infile", help="path to a .txt script file")
    src.add_argument("--text", help="inline script text")
    ap.add_argument("--out", required=True, help="output WAV path")
    ap.add_argument("--channel", choices=CHANNEL_PRESETS.keys(),
                    help="voice preset (overrides --speaker/--pace)")
    ap.add_argument("--engine", choices=["auto", "sarvam", "eleven"], default="auto",
                    help="TTS engine. 'auto' uses ElevenLabs if ELEVENLABS_API_KEY is set, "
                         "otherwise Sarvam.")
    ap.add_argument("--voice-id", dest="voice_id", default=None,
                    help="ElevenLabs voice id (overrides channel/.env default)")
    ap.add_argument("--speaker", default="shubh", help="Bulbul v3 speaker name (lowercase)")
    ap.add_argument("--lang", default=LANG_DEFAULT, help="BCP-47 code, e.g. hi-IN")
    ap.add_argument("--pace", type=float, default=1.0, help="0.5-2.0")
    ap.add_argument("--temperature", type=float, default=0.6, help="0.01-2.0")
    args = ap.parse_args()

    if args.infile:
        with open(args.infile, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = args.text

    text = normalize_for_speech(text)
    chunks = chunk_text(text)

    # decide engine: explicit flag, else auto (ElevenLabs when its key exists)
    engine = args.engine
    if engine == "auto":
        engine = "eleven" if load_env_value("ELEVENLABS_API_KEY") else "sarvam"

    wavs = []
    if engine == "eleven":
        key = load_env_value("ELEVENLABS_API_KEY")
        if not key:
            sys.exit("ERROR: --engine eleven needs ELEVENLABS_API_KEY in .env.")
        voice_id, preset = resolve_eleven_voice(args.channel, args.voice_id)
        print(f"Voice: ElevenLabs ({ELEVEN_MODEL}) voice={voice_id} | {len(chunks)} chunk(s)")
        for i, ch in enumerate(chunks, 1):
            print(f"  [{i}/{len(chunks)}] synthesizing {len(ch)} chars...")
            wavs.append(synth_chunk_eleven(key, ch, voice_id, preset))
    else:
        # Sarvam path: explicit --speaker / --pace / --temperature OVERRIDE the
        # channel preset. This is critical when the user wants to A/B test a
        # different speaker without editing channel.json.
        speaker, pace, temperature = args.speaker, args.pace, args.temperature
        if args.channel:
            p = CHANNEL_PRESETS[args.channel]
            # only fall back to preset values when the CLI did NOT supply them
            if not speaker or speaker == "shubh":  # 'shubh' is argparse default
                speaker = p["speaker"]
            if pace == 1.0:
                pace = p["pace"]
            if temperature == 0.6:
                temperature = p["temperature"]
        key = load_api_key()
        print(f"Voice: Sarvam speaker={speaker} pace={pace} temp={temperature} | {len(chunks)} chunk(s)")
        for i, ch in enumerate(chunks, 1):
            print(f"  [{i}/{len(chunks)}] synthesizing {len(ch)} chars...")
            wavs.append(synth_chunk(key, ch, speaker, args.lang, pace, temperature))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    stitch_wavs(wavs, args.out)
    size = os.path.getsize(args.out)
    print(f"OK -> {args.out} ({size:,} bytes)")


if __name__ == "__main__":
    main()
