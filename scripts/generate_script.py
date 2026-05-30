#!/usr/bin/env python3
"""
generate_script.py  -  turn a one-line idea into a complete job .json file.

WHY THIS EXISTS
  Writing a tight 28-second viral Hinglish script + 5 captions + emoji + B-roll
  search terms is creative work that takes 10-15 minutes per video by hand. An
  LLM does it in 3 seconds. We just need:
    1) a free LLM that handles Hinglish well
    2) a strict prompt that produces the exact job-file JSON schema

  Provider precedence (auto-falls-through):
    1) Groq        - free tier, 6000 tokens/min, llama-3.3-70b. FAST and good Hinglish.
    2) Gemini      - free tier, gemini-2.0-flash. Backup.
    3) BluesMinds  - paid only on user's plan; tried last.

USAGE
  # one-shot from a one-line idea:
  python scripts/generate_script.py --channel ai-tadka --idea "ChatGPT se LinkedIn bio" --out channels/ai-tadka/jobs/linkedin-bio.json

  # interactive (asks for the idea):
  python scripts/generate_script.py --channel ai-tadka

OUTPUT
  Writes a fully-formed job .json that scripts/make_video.py can render directly.

REQUIRES
  GROQ_API_KEY  or  GEMINI_API_KEY  in .env (free tiers).
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- env
def _load_env_value(name):
    """Case-insensitive read from env or project .env."""
    nl = name.lower()
    for k in (name, nl, name.upper()):
        v = os.environ.get(k)
        if v:
            return v.strip()
    env = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env):
        return None
    with open(env, "r", encoding="utf-8") as f:
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


# ---------------------------------------------------------------- channel context
def _load_channel(channel_id):
    cdir = os.path.join(PROJECT_ROOT, "channels", channel_id)
    cfg_path = os.path.join(cdir, "channel.json")
    if not os.path.exists(cfg_path):
        sys.exit(f"ERROR: channel '{channel_id}' not found ({cfg_path}).")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- prompt
SYSTEM_PROMPT = """You are a professional viral Hinglish YouTube Shorts script writer and video editor.
Your scripts are optimized for RETENTION, aiming for swipe-away rates < 20% and replay rates > 10%.

RETENTION RULES for professional video editing:
- DURATION: Targeted at 45-55 seconds. This is a hard requirement. The video MUST be around 50 seconds long.
- WORD COUNT: You MUST write at least 130-150 words. If the script is too short, the video will be rejected.
- SUBTITLES: Must be punchy. 1-3 words per line maximum. Long sentences create "visual noise".
- SYNC: The voice script (Hinglish) and captions must be perfectly aligned.
- B-ROLL: Every scene MUST have a specific English search query for stock footage.
- HOOK: The first 1 second must be a pattern interrupt. No "Hi everyone".
- CONTENT: Do NOT just tease. You MUST actually deliver the value/method promised in the script. Detailed explanations are mandatory.

You ALWAYS return a single valid JSON object that matches this exact schema:
{
  "channel": "<channel id from input>",
  "title": "<plain English title, 6-10 words. Hook + keyword.>",
  "description": "<viral hook + tease. Mixed Hindi+English. 120 chars.>",
  "hashtags": ["<5 relevant hashtags>"],
  "music": "music/bgm.mp3",
  "voice": "<45-55 second Hinglish script. 130-150 words total. Mix Devanagari Hindi with Latin English. Use commas for breathing pauses, ? for questions, ... for tension. The script must have: 1. A pattern-interrupt Hook (5s), 2. A Bridge setting up the problem (10s), 3. A detailed Step-by-Step explanation of the solution/method (30s), 4. A clear Call to Action (5s).>",
  "captions": [
    {"icon": "<emoji>", "kicker": "<1-2 word TOPIC>", "line": "<1-3 words MAX per line, mixed Hindi+English, wrap *payoff* in asterisks>", "broll": "<specific 3-5 word English search query for stock footage>"},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "...", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "PAYOFF", "line": "*The result*", "broll": "..."}
  ]
}

CRITICAL RULES:
- line is MAX 3 words. This is non-negotiable for professional subtitle styling.
- captions list should have exactly 12 items to match the longer video length and maintain visual pacing.
- voice MUST be long and detailed. At least 130 words.
- Wrap the most important PAYOFF word in *asterisks* in the final caption.
- Output JSON ONLY. No preamble or markdown fences.
"""


def _build_user_prompt(channel_id, channel_cfg, idea):
    return f"""Channel: {channel_id} ({channel_cfg.get('name')})
Niche: {channel_cfg.get('niche')}
Tagline: {channel_cfg.get('tagline')}

TOPIC SEED: {idea}

Write a 50-second Hinglish script (exactly 140 words) and exactly 12 captions. The script must be detailed and explain the method fully. Write the full job JSON now."""




# ---------------------------------------------------------------- providers
def _post_json(url, headers, payload, timeout=60):
    body = json.dumps(payload).encode()
    # Add a browser-like User-Agent to avoid simple 403/1010 blocks
    std_headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, data=body, method="POST", headers={**std_headers, **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _try_claude(system, user):
    """Anthropic Claude (paid). Best-quality output for Hinglish creative writing.
    Tries claude-3-5-sonnet-latest first (best balance), falls back to haiku
    on quota errors. Returns None if no key, key invalid, or no credits."""
    key = _load_env_value("ANTHROPIC_API_KEY") or _load_env_value("CLAUDE_API_KEY")
    if not key:
        return None
    for model in ("claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"):
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model": model,
                    "max_tokens": 1500,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                    "temperature": 0.85,
                }).encode(),
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
            text = data["content"][0]["text"]
            print(f"[script] generated via Anthropic ({model})")
            return text
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            # 400 with "credit balance is too low" or 429 -> try next model, but
            # both will fail the same way; just bail.
            print(f"[script] Claude {model} HTTP {e.code}: {body}")
            if "credit balance" in body or "billing" in body.lower():
                return None  # no point trying haiku
            continue
        except Exception as e:
            print(f"[script] Claude {model} error: {e}")
            continue
    return None


def _try_groq(system, user):
    key = _load_env_value("GROQ_API_KEY")
    if not key:
        return None
    try:
        data = _post_json(
            "https://api.groq.com/openai/v1/chat/completions",
            {"Authorization": f"Bearer {key}"},
            {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.85,
                "max_tokens": 1200,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        text = data["choices"][0]["message"]["content"]
        print("[script] generated via Groq (llama-3.3-70b-versatile)")
        return text
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        print(f"[script] Groq HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"[script] Groq error: {e}")
        return None


def _try_gemini(system, user):
    key = _load_env_value("GEMINI_API_KEY")
    if not key:
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        data = _post_json(
            url,
            {},
            {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": 0.85,
                    "maxOutputTokens": 1200,
                    "responseMimeType": "application/json",
                },
            },
            timeout=90,
        )
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        print("[script] generated via Gemini (gemini-2.0-flash)")
        return text
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        print(f"[script] Gemini HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"[script] Gemini error: {e}")
        return None


def _try_bluesminds(system, user):
    """Last-resort: BluesMinds (will likely 403 on free tier)."""
    key = _load_env_value("BLUESMINDS_API_KEY")
    if not key:
        return None
    base = _load_env_value("BLUESMINDS_BASE") or "https://api.bluesminds.com/v1"
    for model in ("gpt-5-nano", "deepseek-ai/deepseek-v4-pro", "claude-sonnet-4-6"):
        try:
            data = _post_json(
                f"{base.rstrip('/')}/chat/completions",
                {"Authorization": f"Bearer {key}"},
                {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.85,
                    "max_tokens": 1200,
                },
                timeout=120,
            )
            text = data["choices"][0]["message"]["content"]
            print(f"[script] generated via BluesMinds ({model})")
            return text
        except Exception as e:
            print(f"[script] BluesMinds {model} failed: {e}")
            continue
    return None


def generate(channel_id, idea):
    channel_cfg = _load_channel(channel_id)
    system = SYSTEM_PROMPT
    user = _build_user_prompt(channel_id, channel_cfg, idea)
    # Provider precedence: Claude (best for Hinglish creative) -> Groq (fast/free)
    # -> Gemini (free) -> BluesMinds (last resort, paid).
    for fn in (_try_claude, _try_groq, _try_gemini, _try_bluesminds):
        text = fn(system, user)
        if text:
            return text
    sys.exit(
        "ERROR: no LLM provider available. Add one of these to .env:\n"
        "  ANTHROPIC_API_KEY=sk-ant-...  (best quality - Claude. Needs $5+ credits at console.anthropic.com/settings/billing)\n"
        "  GROQ_API_KEY=gsk_...          (free, Llama 3.3 70B. Get key at console.groq.com - NOT grok.com)\n"
        "  GEMINI_API_KEY=AIzaSy...      (free if quota available. Get key at aistudio.google.com/app/apikey)\n"
        "  BLUESMINDS_API_KEY=sk-...     (paid; free tier blocks the good models)\n"
    )


# ---------------------------------------------------------------- output
def _slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return (s or "short")[:50]


def _validate_job(job):
    """Light schema check + repair."""
    issues = []
    for f in ("channel", "title", "voice", "captions"):
        if not job.get(f):
            issues.append(f"missing field: {f}")
    if not isinstance(job.get("captions"), list) or not (1 <= len(job["captions"]) <= 12):
        issues.append("captions must be a list of 1-12 items")
    for i, c in enumerate(job.get("captions") or []):
        for cf in ("kicker", "line", "icon", "broll"):
            if cf not in c:
                issues.append(f"caption[{i}] missing '{cf}'")
        if c.get("line") and len(c["line"].split()) > 8:
            issues.append(f"caption[{i}] line exceeds 6-7 words: '{c['line']}'")
    return issues


def main():
    ap = argparse.ArgumentParser(description="Generate a viral Hinglish job file from a one-line idea.")
    ap.add_argument("--channel", required=True, choices=("ai-tadka", "paisa-pathshala", "dhandha-dimaag"))
    ap.add_argument("--idea", help="one-line video idea (interactive prompt if missing)")
    ap.add_argument("--out", help="output path; defaults to channels/<channel>/jobs/<slug>-<stamp>.json")
    args = ap.parse_args()

    idea = args.idea
    if not idea:
        try:
            idea = input("One-line video idea: ").strip()
        except EOFError:
            idea = ""
    if not idea:
        sys.exit("ERROR: empty idea.")

    raw = generate(args.channel, idea)
    # try to extract JSON if the model wrapped it in markdown despite our instructions
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        job = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: model did not return valid JSON: {e}")
        print("--- raw output ---")
        print(raw[:1500])
        sys.exit(1)

    # ensure channel field matches the requested channel
    job["channel"] = args.channel
    if not job.get("music"):
        job["music"] = "music/bgm.mp3"

    issues = _validate_job(job)
    if issues:
        print("[validate] WARNINGS:")
        for it in issues:
            print(f"  - {it}")

    out_path = args.out
    if not out_path:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        out_path = os.path.join(
            PROJECT_ROOT, "channels", args.channel, "jobs",
            f"{_slugify(job.get('title', idea))}-{stamp}.json",
        )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    print(f"\nWritten: {out_path}")
    print(f"\nRender it next:\n  python scripts/make_video.py --job \"{out_path}\"")


if __name__ == "__main__":
    main()
