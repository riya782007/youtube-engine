#!/usr/bin/env python3
"""
daily_agent.py  -  the autonomous daily Shorts producer.

WHAT IT DOES (one run = one day's worth of content)
  1) RESEARCH: pull trending topics for each channel niche from Google News /
     YouTube search results, score by recency + India relevance, pick one
     per channel.
  2) SCRIPT:   for each chosen topic, generate a complete job .json using the
     LLM script generator (Groq / Gemini / BluesMinds fallback chain).
  3) RENDER:   run make_video.py for each job sequentially. 3 channels = 3 videos.
  4) SEO:      generate viral title (≤60 chars), description (with hashtags),
     tags, and a thumbnail prompt for each video.
  5) EMAIL:    send a single summary email to the configured recipient with
     paths to each output.mp4 and the SEO bundle.

USAGE
  # one-off manual run (use this to test):
  python scripts/daily_agent.py
  # dry-run (research + script only, no renders, no email):
  python scripts/daily_agent.py --dry-run
  # only one channel:
  python scripts/daily_agent.py --only ai-tadka

DAILY 11AM SCHEDULE
  Use Windows Task Scheduler. We provide an installer:
    python scripts/install_scheduler.py
  This registers a SCHTASKS entry that runs `daily_agent.py` at 11:00 IST every day.

REQUIRED .env keys (all optional - missing pieces just degrade gracefully):
  SARVAM_API_KEY        - voice fallback (always required)
  PEXELS_API_KEY        - B-roll
  ELEVENLABS_API_KEY    - voice (auto-activates if present)
  FREESOUND_API_KEY     - SFX
  GROQ_API_KEY          - script generation (recommended; free)
  GEMINI_API_KEY        - script generation fallback (free)
  BLUESMINDS_API_KEY    - script generation last-resort
  AGENT_EMAIL_FROM      - sender Gmail address (e.g. you@gmail.com)
  AGENT_EMAIL_TO        - recipient (your inbox)
  AGENT_EMAIL_APP_PASSWORD - Gmail App Password (NOT your account password)
"""

import argparse
import datetime as dt
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.message import EmailMessage

# Force UTF-8 console output. Windows defaults to cp1252 which crashes on emoji
# and non-Latin characters that appear constantly in trending YouTube titles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _safe_print(s):
    """print() that won't crash on Unicode even if sys.stdout falls back to cp1252."""
    try:
        print(s)
    except UnicodeEncodeError:
        try:
            print(s.encode("utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"))
        except Exception:
            print(s.encode("ascii", errors="replace").decode("ascii"))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# ---- Reuse modules already in the project ------------------------------------
import generate_script  # noqa: E402

CHANNELS = ("ai-tadka", "paisa-pathshala", "dhandha-dimaag")

# Trend search queries per channel - tuned to surface high-engagement Indian content.
TREND_QUERIES = {
    "ai-tadka": [
        "ChatGPT trick India hindi",
        "AI tool productivity India",
        "Gemini AI feature India",
        "NotebookLM Perplexity India",
        "AI image prompt viral India",
    ],
    "paisa-pathshala": [
        "tax saving 80C India hindi",
        "SIP investment hack India",
        "credit card cashback trick India",
        "salary saving mistake India",
        "EPF NPS PPF India tips",
    ],
    "dhandha-dimaag": [
        "indian startup founder story 2026",
        "indian D2C brand growth secret",
        "small business idea India hindi",
        "indian unicorn business model",
        "Zerodha Zoho Boat business strategy",
    ],
}

# Per-channel keywords that MUST appear (lowercase) for a topic to qualify.
# Filters out politics / cricket / unrelated headlines that Google News surfaces.
REQUIRED_KEYWORDS = {
    "ai-tadka": ("ai", "chatgpt", "gemini", "claude", "openai", "perplexity",
                 "notebooklm", "midjourney", "tool", "prompt", "automation",
                 "machine learning", "deepseek"),
    "paisa-pathshala": ("tax", "sip", "investment", "salary", "saving", "epf",
                        "ppf", "nps", "credit card", "cashback", "money",
                        "income", "mutual fund", "finance", "personal finance",
                        "share market", "stock"),
    "dhandha-dimaag": ("startup", "founder", "business", "brand", "company",
                       "ipo", "valuation", "ceo", "entrepreneur", "d2c",
                       "unicorn", "venture", "small business"),
}


# ---------------------------------------------------------------- topic scoring (retention framework)
# Filters with weights (sum = 100). Each scoring rule is a regex/keyword check.
# 80+ -> create immediately, 65-80 -> test, < 65 -> skip.
SCORING_WEIGHTS = {
    "curiosity_gap": 20, # Does this create “I need to know the answer”?
    "emotion":       15, # Surprise, shock, humor, fear, motivation?
    "proven_demand": 15, # Has this format already hit 100k+–1M+ views repeatedly?
    "recency":       10, # Is it tied to something people are talking about now?
    "mass_appeal":   10, # Can a 13-year-old and a 35-year-old understand it instantly?
    "retention":     15, # Can I keep people till the last second?
    "rewatch":       10, # Will people watch again to catch details?
    "share":          5, # Will people send it to friends?
}

# Keyword indicators per filter. Lower-cased substring match against the headline.
SCORING_INDICATORS = {
    "curiosity_gap": (
        "secret", "nobody knows", "hidden", "trick", "hack", "kya", "kaise",
        "why", "how", "no one tells", "they don't", "schools never", "nobody talks",
        "shocking", "reveal", "exposed", "truth about", "what really", "unexpected",
        "unusual", "rare", "forbidden", "unseen", "mystery",
    ),
    "emotion": (
        "shock", "surprise", "scary", "warning", "loss", "lost", "destroy",
        "viral", "killing", "exposed", "scam", "fraud", "rs ", "₹", "crore",
        "lakh", "billion", "million", "first time", "never seen", "insane",
        "mind-blowing", "heartbreaking", "inspiring", "motivation", "angry",
        "danger", "safe", "mistake", "regret",
    ),
    "proven_demand": (
        "3 things", "5 things", "things you", "5 mistakes", "3 mistakes",
        "ways to", "tricks to", "hacks to", "vs", "battle", "compared",
        "before vs after", "myth", "trends", "trending", "viral", "challenge",
        "transformation", "routine", "day in life", "review", "worth it",
    ),
    "recency": (
        "2026", "today", "this week", "just announced", "new", "latest",
        "launched", "released", "rolled out", "yesterday", "breaking",
        "update", "now available", "soon", "imminent",
    ),
    "mass_appeal": (
        "everyone", "students", "salary", "job", "career", "phone", "whatsapp",
        "youtube", "instagram", "school", "college", "exam", "interview",
        "money", "tax", "ai", "chatgpt", "gemini", "iphone", "android",
        "free", "earn", "save", "home", "life", "health",
    ),
    "retention": (
        "step", "method", "trick", "watch till end", "till the end",
        "twist", "but here's the catch", "wait for it", "you won't believe",
        "last one", "finally", "outcome", "result", "reveal",
    ),
    "rewatch": (
        "easter egg", "did you notice", "missed detail", "every detail",
        "frame by frame", "blink and you'll miss", "did you see", "watch carefully",
        "re-watch", "loop", "smooth", "satisfying",
    ),
    "share": (
        "send to friend", "tag a friend", "everyone needs", "must know",
        "share with", "your friend", "family", "group", "whatsapp status",
        "useful", "important", "alert",
    ),
}

# Bonus boosts for stuff that consistently works on Indian Shorts.
INDIA_BOOST_KEYWORDS = ("india", "indian", "hindi", "hinglish", "delhi", "mumbai", "bengaluru")


def _score_topic(title):
    """Return (total_score 0-100, reasons dict). 80+ create, 65-80 test, <65 skip."""
    t = title.lower()
    reasons = {}
    total = 0
    for f, kws in SCORING_INDICATORS.items():
        weight = SCORING_WEIGHTS[f]
        hits = sum(1 for k in kws if k in t)
        # diminishing returns: first hit gives 70% of weight, subsequent +10% each
        if hits == 0:
            score = 0
        elif hits == 1:
            score = int(weight * 0.7)
        else:
            score = min(weight, int(weight * (0.7 + 0.1 * (hits - 1))))
        reasons[f] = score
        total += score
    # India relevance bonus, capped at +15
    india_hits = sum(1 for k in INDIA_BOOST_KEYWORDS if k in t)
    bonus = min(15, india_hits * 5)
    if bonus:
        reasons["india_bonus"] = bonus
        total += bonus
    return min(100, total), reasons


# ---------------------------------------------------------------- topic reframing
# Map raw news headlines into proven viral Shorts patterns.
PATTERN_TEMPLATES = (
    "3 things {subject} ka koi nahi batata",
    "Yeh {subject} trick 99% logon ko nahi pata",
    "{subject} ka chhupa raaz - schools nahi sikhati",
    "Ruko... {subject} pe yeh ek galti 5 lakh ka loss kara sakti hai",
    "{subject} ke baare me 3 myths jo aaj toot jaayenge",
    "Why your {subject} is wrong (and how to fix it in 30 seconds)",
)


def _reframe_topic(headline, channel_id):
    """Strip news-flavor noise and turn into a clean subject phrase the LLM can
    expand into a viral Short. We don't pre-write the title - we hand the LLM a
    clean subject + the chosen viral pattern hint so it can stay creative.

    Returns: a short instruction line for the LLM, e.g.
       'Topic seed: ChatGPT Images 2.0 anime selfies. Pattern hint: hidden trick / 99% nahi pata. Channel: ai-tadka.'
    """
    # Remove obvious news boilerplate.
    headline = re.sub(r"\s*[-–|]\s*[^-–|]+$", "", headline).strip()
    return headline


# ---------------------------------------------------------------- env
def _load_env_value(name):
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


# ---------------------------------------------------------------- trend research
def _google_news_rss(query, max_items=8):
    """Pull headlines from Google News RSS - public, no API key needed.
    Returns list of {title, link, pub_date} dicts, newest first."""
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            xml_text = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[trends] news rss failed for '{query}': {e}")
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for it in root.iterfind(".//item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        if title:
            items.append({"title": title, "link": link, "pub_date": pub})
        if len(items) >= max_items:
            break
    return items


def _youtube_search_titles(query, max_items=10):
    """Pull recent YouTube Shorts titles for a query (no API key, public RSS-ish
    fallback via Google's video search aggregator). Best-effort; returns [] on error.
    Used to detect format repetition (the 3x3 pattern rule)."""
    try:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query + ' shorts')}&sp=CAISBAgCEAE%253D"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            html_text = r.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    # YouTube embeds search results in a JS blob; extract titles via regex.
    titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]{6,120})"', html_text)
    # de-dupe preserving order
    seen, out = set(), []
    for t in titles:
        tl = t.lower()
        if tl in seen:
            continue
        seen.add(tl)
        out.append(t)
        if len(out) >= max_items:
            break
    return out


def research_topic_for_channel(channel_id):
    """Returns (title, score, reasons)"""
    queries = TREND_QUERIES.get(channel_id, [])
    keywords = REQUIRED_KEYWORDS.get(channel_id, ())
    pool = []  # (title, source, link)

    # Source 1: Google News headlines per query.
    for q in queries:
        for it in _google_news_rss(q, max_items=5):
            pool.append((it["title"], "news", it["link"]))

    # Source 2: actual YouTube Shorts titles already going viral in the niche.
    yt_titles = []
    for q in queries[:2]:
        yt_titles += _youtube_search_titles(q, max_items=8)
    for t in yt_titles:
        pool.append((t, "youtube", ""))

    if not pool:
        return None, 0, {}

    # Niche filter
    def in_niche(title):
        tl = title.lower()
        return (not keywords) or any(k in tl for k in keywords)

    in_niche_pool = [p for p in pool if in_niche(p[0])]
    if not in_niche_pool:
        in_niche_pool = pool

    # 3x3 pattern detection
    yt_pool_titles = [t for (t, src, _) in pool if src == "youtube"]
    pattern_freq = {}
    for t in yt_pool_titles:
        toks = re.findall(r"\w+", t.lower())
        for i in range(len(toks) - 2):
            tri = " ".join(toks[i:i + 3])
            if len(tri) >= 9:
                pattern_freq[tri] = pattern_freq.get(tri, 0) + 1
    proven_trigrams = {tri for tri, n in pattern_freq.items() if n >= 3}

    scored = []
    for title, source, link in in_niche_pool:
        s, reasons = _score_topic(title)
        tl = title.lower()
        if any(tri in tl for tri in proven_trigrams):
            s = min(100, s + 10)
            reasons["3x3_pattern"] = 10
        if source == "youtube":
            s = min(100, s + 5)
            reasons["youtube_source"] = 5
        scored.append((s, title, source, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    _safe_print(f"[trends] {channel_id} top 5 (score / source / title):")
    for s, t, src, _ in scored[:5]:
        _safe_print(f"  {s:3d}  {src:7s}  {t[:80]}")

    # Pick the highest-scoring.
    chosen = None
    for s, t, src, reasons in scored:
        if s >= 80:
            chosen = (s, t, src, reasons); break
    if not chosen:
        for s, t, src, reasons in scored:
            if s >= 65:
                chosen = (s, t, src, reasons); break
    if not chosen and scored:
        chosen = scored[0]
    if not chosen:
        return None, 0, {}

    score, title, source, reasons = chosen
    title = _reframe_topic(title, channel_id)
    bucket = ("CREATE" if score >= 80 else "TEST" if score >= 65 else "WEAK")
    _safe_print(f"[trends] {channel_id} -> [{bucket} score={score}] {title}")
    return title, score, reasons


# ---------------------------------------------------------------- SEO
SEO_PROMPT = """You are a YouTube Shorts SEO specialist for Indian creators.
Given a video title and channel niche, produce SEO metadata that maximizes CTR + retention.

Return ONLY valid JSON in this exact schema:
{
  "youtube_title": "<HOOK + KEYWORD, 50-65 chars, includes #shorts at end, mixed Hindi/English>",
  "description": "<3-5 sentences. Open with the hook. Include 2-3 line breaks. End with a CTA. 600-1500 chars total. Include hashtags at the very bottom.>",
  "tags": ["<15 to 20 SEO tags. Mix of high-volume India search terms in both Hindi and English. No # signs in tags.>"],
  "thumbnail_prompt": "<one-sentence description of an eye-catching thumbnail: subject + emotion + bold text overlay (max 4 words). Designed for 1080x1920 vertical.>",
  "thumbnail_text": "<3-4 word ALL CAPS punchy text to overlay on thumbnail>"
}

Rules:
- youtube_title MUST be 50-65 characters AND end with " #shorts"
- description must include the channel handle reference and call-to-action
- tags should include long-tail Indian search variations (e.g. "ai tools hindi me", not just "ai")
- thumbnail_text should be in Hinglish or Hindi for max click-through with Indian audience
"""


def generate_seo(channel_id, video_title, video_voice_script):
    """Use the same LLM stack as generate_script.py to build SEO metadata."""
    channel_cfg = generate_script._load_channel(channel_id)
    user = (
        f"Channel: {channel_id} ({channel_cfg.get('name')})\n"
        f"Niche: {channel_cfg.get('niche')}\n"
        f"Video title: {video_title}\n"
        f"Video script: {video_voice_script[:800]}\n\n"
        f"Generate the SEO JSON now."
    )
    for fn in (generate_script._try_groq, generate_script._try_gemini, generate_script._try_bluesminds):
        text = fn(SEO_PROMPT, user)
        if not text:
            continue
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```\s*$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    # Fallback SEO without LLM - heuristic only.
    print("[seo] no LLM available - using heuristic SEO fallback.")
    handle = channel_cfg.get("handle", "")
    footer = channel_cfg.get("seo", {}).get("description_footer", "")
    tags = channel_cfg.get("seo", {}).get("tags", [])
    return {
        "youtube_title": (video_title[:55] + " #shorts").strip(),
        "description": f"{video_title}\n\n{footer}".strip(),
        "tags": tags,
        "thumbnail_prompt": f"Bold vertical thumbnail for: {video_title}. Indian creator content, bright accent colors, large text overlay.",
        "thumbnail_text": "MUST WATCH",
    }


# ---------------------------------------------------------------- thumbnail (placeholder)
def generate_thumbnail(seo, render_dir, channel_cfg):
    """Generate a static thumbnail PNG. For now we extract a frame from the
    rendered video and overlay text using ffmpeg drawtext - simple, free,
    no extra API needed. Future upgrade: swap to AI image generation when
    a key is available."""
    out = os.path.join(render_dir, "thumbnail.jpg")
    src = os.path.join(render_dir, "output.mp4")
    if not os.path.exists(src):
        return None
    text = (seo.get("thumbnail_text") or "WATCH").strip().replace(":", " ").replace("'", "")
    # ffmpeg drawtext escaping
    safe_text = text.replace("\\", "\\\\").replace("%", "\\%")
    accent = (channel_cfg.get("theme", {}) or {}).get("accent", "#ff7a18").lstrip("#")
    cmd = [
        "ffmpeg", "-y", "-ss", "1.5", "-i", src, "-vframes", "1",
        "-vf",
        (
            f"drawbox=x=0:y=ih-380:w=iw:h=240:color=black@0.55:t=fill,"
            f"drawtext=text='{safe_text}':"
            f"fontcolor=white:fontsize=110:bordercolor=0x{accent}:borderw=8:"
            f"x=(w-text_w)/2:y=h-330"
        ),
        "-q:v", "2", out,
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0 and os.path.exists(out):
            return out
    except FileNotFoundError:
        return None
    return None


# ---------------------------------------------------------------- one channel pipeline
def run_one_channel(channel_id, dry_run=False):
    """Returns a dict with the day's result for this channel, or None on hard error."""
    print(f"\n========== {channel_id.upper()} ==========")
    topic, score, reasons = research_topic_for_channel(channel_id)
    if not topic:
        return {"channel": channel_id, "error": "no trending topic found"}

    # 1) script generation -> writes a job file
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    slug = generate_script._slugify(topic)
    job_path = os.path.join(PROJECT_ROOT, "channels", channel_id, "jobs", f"auto-{slug}-{stamp}.json")
    try:
        raw = generate_script.generate(channel_id, topic)
    except SystemExit as e:
        return {"channel": channel_id, "error": str(e), "topic": topic, "score": score, "reasons": reasons}
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        job = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"channel": channel_id, "error": f"LLM returned invalid JSON: {e}", "topic": topic, "score": score, "reasons": reasons, "raw": raw[:600]}
    job["channel"] = channel_id
    job.setdefault("music", "music/bgm.mp3")
    os.makedirs(os.path.dirname(job_path), exist_ok=True)
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    print(f"[agent] job file: {job_path}")

    if dry_run:
        return {"channel": channel_id, "topic": topic, "score": score, "reasons": reasons, "job_path": job_path, "dry_run": True, "job": job}

    # 2) render
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, "make_video.py"), "--job", job_path]
    print(f"[agent] rendering: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0:
        return {"channel": channel_id, "topic": topic, "score": score, "reasons": reasons, "job_path": job_path, "error": "render failed"}

    # find latest render dir for this slug
    rdir_root = os.path.join(PROJECT_ROOT, "channels", channel_id, "renders")
    candidates = [d for d in os.listdir(rdir_root) if d.startswith(generate_script._slugify(job.get("title", slug)))]
    candidates.sort(reverse=True)
    if not candidates:
        return {"channel": channel_id, "topic": topic, "score": score, "reasons": reasons, "job_path": job_path, "error": "render dir not found"}
    render_dir = os.path.join(rdir_root, candidates[0])
    output_mp4 = os.path.join(render_dir, "output.mp4")
    if not os.path.exists(output_mp4):
        return {"channel": channel_id, "topic": topic, "score": score, "reasons": reasons, "job_path": job_path, "error": "output.mp4 missing"}

    # 3) SEO
    channel_cfg = generate_script._load_channel(channel_id)
    seo = generate_seo(channel_id, job.get("title", topic), job.get("voice", ""))
    seo_path = os.path.join(render_dir, "seo.json")
    with open(seo_path, "w", encoding="utf-8") as f:
        json.dump(seo, f, ensure_ascii=False, indent=2)

    # 4) thumbnail
    thumb_path = generate_thumbnail(seo, render_dir, channel_cfg)

    return {
        "channel": channel_id,
        "topic": topic,
        "score": score,
        "reasons": reasons,
        "job_path": job_path,
        "render_dir": render_dir,
        "output_mp4": output_mp4,
        "thumbnail": thumb_path,
        "seo": seo,
    }


# ---------------------------------------------------------------- email
def send_email(results, smtp_server="smtp.gmail.com", smtp_port=465):
    sender = _load_env_value("AGENT_EMAIL_FROM")
    recipient = _load_env_value("AGENT_EMAIL_TO")
    app_pw = _load_env_value("AGENT_EMAIL_APP_PASSWORD")
    if not (sender and recipient and app_pw):
        print("[email] AGENT_EMAIL_FROM / AGENT_EMAIL_TO / AGENT_EMAIL_APP_PASSWORD missing - skipping send.")
        return False

    today = dt.datetime.now().strftime("%Y-%m-%d")
    subject = f"[YouTube Engine] Daily Shorts ready - {today}"

    # build HTML body
    rows = []
    for r in results:
        ch = r.get("channel", "?")
        if r.get("error"):
            rows.append(f"<h3>❌ {ch}</h3><p>Error: {r['error']}</p><p>Topic attempted: {r.get('topic','-')}</p>")
            continue
        seo = r.get("seo", {})
        reasons = r.get("reasons", {})
        score_html = "".join([f"<li>{k}: {v}</li>" for k, v in reasons.items()])
        rows.append(
            f"<h3>✅ {ch}</h3>"
            f"<p><b>Viral Score: {r.get('score', 0)}/100</b> (Hook probability: HIGH)</p>"
            f"<ul>{score_html}</ul>"
            f"<p><b>Topic:</b> {r.get('topic','-')}</p>"
            f"<p><b>YouTube title:</b> {seo.get('youtube_title','-')}</p>"
            f"<p><b>Video file:</b> <code>{r.get('output_mp4','-')}</code></p>"
            f"<p><b>Thumbnail:</b> <code>{r.get('thumbnail') or '(none)'}</code></p>"
            f"<details><summary>Description</summary><pre>{seo.get('description','')}</pre></details>"
            f"<details><summary>Tags ({len(seo.get('tags',[]))})</summary><pre>{', '.join(seo.get('tags',[]))}</pre></details>"
            f"<details><summary>Thumbnail prompt</summary><pre>{seo.get('thumbnail_prompt','')}</pre></details>"
        )
    html_body = (
        "<html><body style='font-family:system-ui,sans-serif'>"
        f"<h2>Daily Shorts - {today}</h2>"
        "<p>Three videos rendered locally and ready to review + upload. Defaults to private until you publish.</p>"
        + "<hr>".join(rows) +
        "<p><em>Review the .mp4 files at the paths above. Upload via "
        "<code>python scripts/upload.py --dir &lt;render folder&gt;</code></em></p>"
        "</body></html>"
    )
    text_body = "Daily Shorts ready. See HTML version. Files:\n" + "\n".join(
        f"- {r.get('channel')}: {r.get('output_mp4', r.get('error','?'))}" for r in results
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    # Attach videos and thumbnails
    total_size = 0
    MAX_EMAIL_SIZE = 25 * 1024 * 1024 # 25MB safety limit
    for r in results:
        if r.get("error"):
            continue
        
        # 1) Attach Video
        vpath = r.get("output_mp4")
        if vpath and os.path.exists(vpath):
            vsize = os.path.getsize(vpath)
            
            # If video is too large for email, try to compress it
            if vsize >= MAX_EMAIL_SIZE:
                print(f"[email] video {vpath} is too large ({vsize/1024/1024:.1f} MB). Compressing...")
                compressed_path = vpath.replace(".mp4", "_email.mp4")
                # Crf 28 is a good balance for email
                cmd = ["ffmpeg", "-y", "-i", vpath, "-vcodec", "libx264", "-crf", "28", "-preset", "faster", "-acodec", "aac", "-b:a", "128k", compressed_path]
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(compressed_path):
                        vpath = compressed_path
                        vsize = os.path.getsize(vpath)
                        print(f"[email] compressed to {vsize/1024/1024:.1f} MB")
                except Exception as e:
                    print(f"[email] compression failed: {e}")

            if vsize < MAX_EMAIL_SIZE:
                try:
                    with open(vpath, "rb") as f:
                        msg.add_attachment(
                            f.read(),
                            maintype="video",
                            subtype="mp4",
                            filename=f"{r['channel']}_{os.path.basename(vpath)}"
                        )
                    total_size += vsize
                    print(f"[email] attached video: {vpath} ({vsize/1024/1024:.1f} MB)")
                except Exception as e:
                    print(f"[email] failed to attach video {vpath}: {e}")
            else:
                print(f"[email] skipping video attachment (limit reached even after compression): {vpath}")

        # 2) Attach Thumbnail
        tpath = r.get("thumbnail")
        if tpath and os.path.exists(tpath):
            tsize = os.path.getsize(tpath)
            if total_size + tsize < MAX_EMAIL_SIZE:
                try:
                    with open(tpath, "rb") as f:
                        msg.add_attachment(
                            f.read(),
                            maintype="image",
                            subtype="jpeg",
                            filename=f"{r['channel']}_thumbnail.jpg"
                        )
                    total_size += tsize
                except Exception as e:
                    print(f"[email] failed to attach thumbnail {tpath}: {e}")

    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=ctx, timeout=300) as server:
            server.login(sender, app_pw)
            server.send_message(msg)
        print(f"[email] sent summary to {recipient}")
        return True
    except Exception as e:
        print(f"[email] send failed: {e}")
        return False


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Daily autonomous Shorts producer.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Research + script generation only. No render. No email.")
    ap.add_argument("--no-email", action="store_true", help="Skip email step.")
    ap.add_argument("--only", choices=CHANNELS, help="Only run one channel.")
    args = ap.parse_args()

    channels = (args.only,) if args.only else CHANNELS
    results = []
    for ch in channels:
        try:
            r = run_one_channel(ch, dry_run=args.dry_run)
            if r:
                results.append(r)
                if not args.dry_run and not args.no_email:
                    send_email([r])
        except Exception as e:
            print(f"[agent] {ch} fatal: {e}")
            results.append({"channel": ch, "error": str(e)})

    print("\n========== SUMMARY ==========")
    for r in results:
        if r.get("error"):
            print(f"  {r['channel']}: ERROR - {r['error']}")
        else:
            print(f"  {r['channel']}: OK -> {r.get('output_mp4', r.get('job_path','?'))}")


if __name__ == "__main__":
    main()
