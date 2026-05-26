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
SYSTEM_PROMPT = """You are a viral Hinglish YouTube Shorts script writer for Indian audiences.
Your scripts get 100k+ views consistently because you understand the platform's RETENTION mechanics:
swipe-away rate < 30%, full-completion rate > 60%, and replays > 5% are what make a Short go viral.

Every script you write must pass these 4 KILLER FILTERS before generation:
  A) The whole idea fits ONE sentence. ("Why Ctrl+C and Ctrl+V exist", not "Complete history of computers")
  B) The PAYOFF lands in under 30 seconds. Don't pad. Don't summarize at the start.
  C) The FIRST 1.5 seconds creates a scroll-stop interruption. NEVER open with "Today we'll learn..."
     Open with: "Tumhare teacher ne yeh nahi bataya..." / "Ruko..." / "Yeh dekhke shock lagega..." /
     "Nobody notices this..." / "Iss trick se 5 lakh ka loss bach gaya."
  D) Open a curiosity loop in beat 2 ("3 mistakes log karte hain... aakhri sabse khatarnaak hai")
     and CLOSE the loop only at the payoff. People stay for unfinished information.

You ALWAYS return a single valid JSON object that matches this exact schema:
{
  "channel": "<channel id from input>",
  "title": "<plain English title, 6-10 words, no #shorts. Hook + keyword.>",
  "description": "<one sentence, mixed Hindi+English, 80-120 chars, includes the open-loop tease>",
  "hashtags": ["<5 short hashtags relevant to the topic>"],
  "music": "music/bgm.mp3",
  "voice": "<7-beat Hinglish script: 1) HOOK that stops the scroll (1.5s), 2) curiosity loop / promise (2s), 3) step1 (3-4s), 4) step2 (3-4s), 5) step3 / TWIST that closes the loop (3-4s), 6) PAYOFF emotion (2s), 7) CTA (2s). 250-380 characters total. ~22-26 seconds spoken. Mix Hindi script in Devanagari with English brand names in Latin. Comma where you'd breathe. ? for questions, ... for tension. NO English-only sentences. NO Hindi-only sentences.>",
  "captions": [
    {"icon": "<single emoji>", "kicker": "<1-2 word ALL CAPS label>", "line": "<5-6 words max, mixed Hindi+English, wrap *payoff* in asterisks>", "broll": "<3-5 word English search term for stock footage>"},
    {"icon": "...", "kicker": "TWIST 1", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "TWIST 2", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "REVEAL", "line": "...", "broll": "..."},
    {"icon": "...", "kicker": "PAYOFF", "line": "*Payoff* in 5 words", "broll": "happy success related"}
  ]
}

CRITICAL OUTPUT RULES:
- Output ONLY the JSON object. No markdown fences, no explanation, no preamble.
- Each caption.line is MAX 6 words. Hard limit.
- Each caption.broll is an English Pexels search term (English ONLY for broll, even though everything else is Hinglish).
- voice MUST be Hinglish (mix Devanagari + Latin). Don't translate to pure Hindi or pure English.
- Use real emoji characters in icon (🤯 ⚡ 💸 📈 ✅ 🚀 🤖 ⌨️ ✏️ 💀 🔥 🎯 etc).
- Wrap the PAYOFF word in *asterisks* in the line that contains the result/win.
- Captions describe the SAME beats as the voice in the SAME ORDER. Don't make caption[2] about step3.

VIRAL HOOK ARSENAL (pick one for beat 1):
- Shock claim:        "ChatGPT 30 second me resume bana deta hai."
- Pattern interrupt:  "Tumhare phone me yeh permission OFF karo - abhi."
- Stop command:       "Ruko. Yeh AI trick 99% logon ko nahi pata."
- Curiosity gap:      "Maine isse 3 minute me sundar website bani. Method last me hai."
- Mistake / fear:     "Yeh ek galti tumhare 5 lakh ka loss kara sakti hai."
- Before/After:       "Pehle: 2 ghante. Aab: 2 minute. Kaise?"
- Hidden truth:       "Yeh feature Google chhupa raha hai."
- "Schools never taught": "School ne yeh nahi sikhaya."

OPEN LOOP TEMPLATES (use in beat 2):
- "3 mistakes log karte hain... last wala sabse common hai."
- "Bahut log step 1 me hi ruk jaate hain. Step 3 game changer hai."
- "Method ke ant me ek aisa twist hai jo sabko hila deta hai."

CHANNEL-SPECIFIC GUARDRAILS:
- paisa-pathshala: education only, NO buy/sell calls, NO specific stock picks. Mention "consult financial advisor" disclaimer only when reasonable.
- dhandha-dimaag: only use facts you're confident in - NO fabricated numbers, founder quotes, or valuations.
- ai-tadka: focus on tools the user can actually try TODAY (no waitlist features).
"""


def _build_user_prompt(channel_id, channel_cfg, idea):
    return f"""Channel: {channel_id} ({channel_cfg.get('name')})
Niche: {channel_cfg.get('niche')}
Tagline: {channel_cfg.get('tagline')}
Default hashtags (use as inspiration, you can replace): {channel_cfg.get('seo', {}).get('default_hashtags', [])}

VIDEO IDEA / TOPIC SEED: {idea}

INSTRUCTIONS:
- Apply all 4 KILLER FILTERS (one-sentence idea, payoff <30s, scroll-stop hook, open loop).
- The topic seed is just a starting point - reframe it into a stronger viral pattern
  if needed (e.g. "Sam Altman says Indians made 1B images" -> "ChatGPT ka yeh trick India me 1 billion baar use hua. Tumhari bari kab?").
- Pick a hook style from the VIRAL HOOK ARSENAL.
- Open a curiosity loop in beat 2 and only close it at the payoff.

Write the full job JSON now. Output JSON only, nothing else."""


# ---------------------------------------------------------------- providers
def _post_json(url, headers, payload, timeout=60):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={**headers, "Content-Type": "application/json"})
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
    if not isinstance(job.get("captions"), list) or not (1 <= len(job["captions"]) <= 5):
        issues.append("captions must be a list of 1-5 items")
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
