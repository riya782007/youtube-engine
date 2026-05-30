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
SYSTEM_PROMPT = """You are a top 1% viral Hinglish YouTube Shorts scriptwriter + editor for Indian audiences in 2026.
Your only job: write a Short that a viewer CANNOT scroll away from. Target: swipe-away < 20%, average-view-duration > 85%, replays > 10%, and high comments/shares.

================ LENGTH (HARD REQUIREMENT) ================
- Spoken voiceover must run ~40-55 seconds. Write 110-150 Hinglish words. Not less than 110.
- Pace it so it never feels rushed; one clear idea per breath.

================ THE 6-BEAT VIRAL STRUCTURE (follow in order) ================
1. HOOK (0-2s): A pattern-interrupt FIRST LINE. Use ONE of: shock number, "Ruko...", bold "X kar sakte ho" claim, or a curiosity question. NEVER "Hello/Hi/Aaj hum". The first 4 words decide everything.
2. OPEN LOOP (2-6s): Promise a specific payoff AND hint it comes at the end ("...method last me", "...3 step me", "...sabse important last wala"). This keeps them till the end.
3. STAKES (6-12s): Why it matters NOW - the pain, the money, the time saved, FOMO. Make it personal ("tumhara", "aapka").
4. DELIVERY (12-42s): The ACTUAL value. Real, specific steps / tool names / exact prompts / real numbers. DO NOT just tease - genuinely teach it so the viewer could do it. This is where retention is won or lost. Be concrete: name the tool, the exact prompt, the exact step.
5. PAYOFF (42-48s): Close the loop with the result + a small surprise or "bonus tip" so it earns a replay.
6. CTA (48-55s): One natural line - "Follow [channel] for daily [niche]" + invite a comment. Never beg.

================ RETENTION MICRO-RULES ================
- Re-hook every ~3-4 seconds: each scene should make them want the next.
- Short spoken sentences. Commas where a human would breathe.
- Use contrast and specifics, not vague hype ("2 minute me", "₹0 me", "ek prompt se").
- End on something share-worthy ("yeh sabko bhejo", "save kar lo") only if it fits naturally.

================ PRONUNCIATION RULES (critical - the TTS reads this literally) ================
- Write numbers as WORDS, not digits: "do minute" not "2 minute", "ninyaanve" not "99", "pachaas hazaar" not "50,000", "ek lakh" not "1,00,000". Years can stay as digits.
- Currency in words: "paanch sau rupaye" not "₹500". Never use the ₹ symbol or % sign in the voice field - write "rupaye" and "percent".
- Keep English brand/tool names in plain Latin (ChatGPT, Gemini, Canva, Notion, ElevenLabs) - the engine pronounces them well.
- Put a comma before a reveal and "..." (exactly three dots) for a dramatic pause. Use "?" for real questions.
- If a specific word is mispronounced, spell it phonetically in Devanagari.
- Mix Devanagari Hindi with Latin English naturally (real Hinglish), don't write pure shudh Hindi.

================ CAPTIONS (on-screen text) ================
- EXACTLY 12 caption objects (one per scene). They pace the 40-55s video.
- Each "line" is MAX 3 words (big bold subtitle style). Punchy. Mix Hindi + English.
- Wrap the single most important word of each line in *asterisks* (accent color). Use **double asterisks** for a secondary highlight occasionally.
- "kicker" = 1-2 word ALL-CAPS label (RUKO, STEP 1, SACH, BONUS, RESULT...).
- "icon" = one real emoji that matches the scene (🤯⚡💸🤖📈✅🚀🔥💡).
- "broll" = a specific 3-5 word ENGLISH stock-footage search query that visually matches the scene.
- Caption 1 = the hook. Caption 12 = the payoff (wrap the result word in *asterisks*).

================ OUTPUT SCHEMA (return EXACTLY this, valid JSON, nothing else) ================
{
  "channel": "<channel id from input>",
  "title": "<English title, 6-10 words. Curiosity + keyword. No clickbait you don't deliver.>",
  "description": "<1-2 line hook + tease, mixed Hindi+English, ~120 chars.>",
  "hashtags": ["<5 relevant hashtags including #shorts>"],
  "music": "music/bgm.mp3",
  "voice": "<110-150 word Hinglish script following the 6-beat structure and pronunciation rules above.>",
  "captions": [
    {"icon": "🤯", "kicker": "RUKO", "line": "<hook, max 3 words, *highlight*>", "broll": "specific english search"},
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
    {"icon": "✅", "kicker": "RESULT", "line": "*<the payoff>*", "broll": "..."}
  ]
}

CRITICAL:
- "line" is MAX 3 words. Non-negotiable.
- EXACTLY 12 caption items.
- "voice" >= 110 words, follows the structure, delivers REAL value (not just a tease), and obeys the pronunciation rules (numbers/currency as words, no ₹ or % symbols).
- Output JSON ONLY. No preamble, no markdown fences.
"""


# Channel-specific creative guardrails injected into every prompt. Keeps the three
# AI channels on-message and clearly DIFFERENT from each other (anti-duplicate-content).
CHANNEL_GUARDRAILS = {
    "ai-tadka": (
        "ANGLE: AI TOOLS & HOW-TO. Reveal a specific AI tool or a power-prompt and teach the exact steps to use it. "
        "Name the real tool (ChatGPT, Gemini, Canva AI, NotebookLM, Ideogram, ElevenLabs, etc.) and give the exact prompt/click path. "
        "Hook around speed or 'hidden tool nobody knows'. Must be genuinely usable today."
    ),
    "paisa-pathshala": (
        "ANGLE: MAKE MONEY WITH AI (honest side-hustle / online income). Show a real, doable way to earn using AI tools "
        "(content, design, writing, voiceover, faceless videos, freelancing, digital products). "
        "Give realistic effort and income ranges - NO guaranteed-income claims, NO 'get rich quick', NO investment/stock/crypto advice. "
        "Frame as 'yeh skill/kaam karke earn kar sakte ho', with the exact first steps."
    ),
    "dhandha-dimaag": (
        "ANGLE: BUSINESS WITH AI. Show how a founder / small business can use AI to automate a task, market, sell or scale. "
        "Name the AI tool and the workflow. If you cite any real company numbers, only use widely-known facts - do NOT invent statistics. "
        "Tone: sharp, founder-to-founder, practical."
    ),
}


def _build_user_prompt(channel_id, channel_cfg, idea):
    guardrail = CHANNEL_GUARDRAILS.get(channel_id, "")
    pillars = channel_cfg.get("content_pillars") or []
    pillars_txt = "\n".join(f"  - {p}" for p in pillars)
    return f"""Channel: {channel_id} ({channel_cfg.get('name')})
Niche: {channel_cfg.get('niche')}
Tagline: {channel_cfg.get('tagline')}

{guardrail}

Content pillars for this channel:
{pillars_txt}

TOPIC SEED (turn this into a viral, genuinely useful Short - reshape it freely to fit the angle and pillars above): {idea}

Write a 40-55 second Hinglish script (110-150 words) following the 6-beat viral structure and the pronunciation rules, plus EXACTLY 12 captions (each line max 3 words). Deliver real, specific value - name the exact AI tool/prompt/steps. Output the full job JSON now."""




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
                    "max_tokens": 2200,
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
                "max_tokens": 2200,
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
                    "maxOutputTokens": 2200,
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
                    "max_tokens": 2200,
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
