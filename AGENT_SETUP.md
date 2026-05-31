# Daily Agent Activation — 5-minute setup

The daily 11 AM agent is **fully built**. Three short steps activate it for tomorrow:

---

## Step 1 — Free Groq API key (script generation)

Why: The LLM writes the daily script. Groq's free tier is fast, generous, and reliable.

1. Open **console.groq.com** in your browser
2. Sign in (Google / GitHub / email)
3. Left sidebar → **API Keys** → **Create API Key** → name it anything
4. Copy the key (starts with `gsk_...`)
5. Open `c:\Users\Riya yadav\youtube engine\.env` and edit this line:
   ```
   GROQ_API_KEY=gsk_your_real_key_here
   ```

Free tier: 6000 tokens/min — plenty for 3 scripts/day.

---

## Step 1b — Optional media keys (better footage, music & SFX)

These are all optional and free; the agent runs without them, but each one bumps quality.
Add any you want to `.env`:

- **PEXELS_API_KEY** — real stock B-roll behind every scene. Get it at pexels.com/api.
- **ELEVENLABS_API_KEY** — the natural-voice upgrade. If present, the engine auto-switches
  from Sarvam to ElevenLabs (far more natural Hinglish). Free tier at elevenlabs.io.
- **FREESOUND_API_KEY** — fresh CC0 whoosh/ding SFX per render. freesound.org/apiv2/apply.
- **JAMENDO_CLIENT_ID** — automatic royalty-free background music (also activates beat-synced
  cuts). Free Client ID at devportal.jamendo.com. See AUDIO_GUIDE.md. Without it, the agent
  uses whatever `bgm.mp3` you place in each `channels/<id>/music/` folder.

The 11 AM run prints a **PREFLIGHT** block showing exactly which keys are active, so your
daily log tells you at a glance what's on.

---

## Step 2 — Gmail App Password (so the agent can email you)

Why: Google blocks regular passwords for SMTP. App Password is required.

1. Sign in to **r782007y@gmail.com**
2. **myaccount.google.com/security** → enable **2-Step Verification** (if not already)
3. **myaccount.google.com/apppasswords**
4. App: **Mail**, Device: **Windows Computer** → **Generate**
5. Copy the 16-character password (no spaces)
6. Open `.env` and set:
   ```
   AGENT_EMAIL_APP_PASSWORD=abcdefghijklmnop
   ```

The agent will email **r782007y@gmail.com → ry342315@gmail.com** at 11 AM daily.

---

## Step 3 — Register the daily 11 AM scheduler

Open **Command Prompt** (not PowerShell — schtasks is more reliable from cmd) at the project root. Run:

```
python scripts\install_scheduler.py
```

This creates a Windows Task Scheduler entry called `YouTubeEngine_DailyShorts` that fires daily at 11:00 (your local timezone, IST).

To change time: `python scripts\install_scheduler.py --time 09:30`
To remove: `python scripts\install_scheduler.py --uninstall`

---

## Test before tomorrow morning

After Steps 1 + 2:

```
python scripts\daily_agent.py --dry-run --only ai-tadka
```

Expected:
- `[trends] ai-tadka top 5 (score / source / title): ...`
- `[trends] ai-tadka -> [CREATE/TEST/WEAK score=X] <topic>`
- `[script] generated via Groq (llama-3.3-70b-versatile)`
- `[agent] job file: channels/ai-tadka/jobs/auto-...json`

If that works, run a full production test (renders 1 video, sends 1 email):

```
python scripts\daily_agent.py --only ai-tadka
```

---

## What the agent does at 11 AM each day

For each of the 3 channels in sequence:

### 1. Trend research with retention scoring
- Pulls headlines from Google News (RSS, no key)
- Pulls actual YouTube Shorts titles in the niche (no key)
- Filters to channel-relevant keywords
- Scores each candidate 0-100 using your weighted framework:
  - Curiosity gap 20, Emotion 15, Proven demand 15, Recency 10, Mass appeal 10, Retention 15, Rewatch 10, Share 5
  - +15 India relevance bonus
  - +10 "3x3 pattern" (when a 3-word phrase repeats across 3+ titles in the niche → proven format)
  - +5 YouTube source (proven format vs raw news)
- Picks 80+ if available, else 65-80, else best of pool
- Prints top 5 with scores so you can see the reasoning

### 2. Script generation with viral mechanics built in
The LLM prompt enforces:
- 40-55 second scripts (110-150 Hinglish words) so each Short lands in the 35-60s sweet spot
- A 6-beat viral structure: hook → open loop → stakes → step-by-step delivery → payoff → CTA
- Pronunciation rules baked in: numbers/currency spelled as Hindi words ("ninyaanve", "ek lakh"),
  no ₹/% symbols in the spoken text, brand names in Latin, commas + "..." for natural pacing
- Per-channel guardrails:
  - **ai-tadka** → reveal a specific AI tool / power-prompt and teach the exact steps
  - **paisa-pathshala** → honest "make money with AI" side hustles (no guaranteed-income / no investment advice)
  - **dhandha-dimaag** → "business with AI" automation/ideas (no fabricated company numbers)

### 3. Render via the full pipeline
- ElevenLabs Liam voice (Hinglish, social-media tuned)
- Whisper word-level caption timing (aligned to original Hinglish script — no Urdu)
- Beat-snapped scene cuts to BGM
- Pexels stock B-roll per scene
- Freesound CC0 SFX (random pick per render)
- 4 transition variants (whip / zoom / glitch / 3D flip)
- Self-hosted fonts, audio normalized to -14 LUFS

### 4. SEO + thumbnail
- YouTube title (≤65 chars, includes #shorts)
- Description with hashtags
- 15-20 SEO tags
- Thumbnail PNG: extracted frame + text overlay via FFmpeg drawtext

### 5. Email summary
HTML + plain-text email arrives in your inbox with:
- Output.mp4 path for each channel
- Thumbnail path
- Title, description, tags
- The exact upload command for each

**Nothing auto-uploads.** You stay the gate.

---

## What to expect realistically

**Free-tier ElevenLabs limit**: 10k chars/month. 3 videos/day × ~350 chars × 30 days = ~31.5k chars. Free tier exhausts around day 9. After that, the engine auto-falls back to Sarvam (no breakage). Upgrade to ElevenLabs Starter ($5/mo, 30k chars) for full month coverage.

**Topics will not always score 80+**. The framework is strict. The agent picks the best available; the LLM's job is to take a so-so seed and turn it into a great script using the viral patterns. Score is a directional signal, not a gate.

**3-5 minutes per render**. 3 channels = ~15 min total. The agent runs in the background; the email arrives once everything's done.

**First email might land in spam**. Mark Not Spam once; subsequent emails arrive in inbox.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no LLM provider available` | Step 1 incomplete |
| `AGENT_EMAIL_APP_PASSWORD missing` | Step 2 incomplete |
| Email not arriving | Check spam. Mark Not Spam. Verify both addresses correct in `.env` |
| `render failed` | Run `python scripts\make_video.py --job <path>` manually to see error |
| Topic scores look low | Normal early on; the LLM can still produce good scripts from 50-65 seeds. Score 80+ is a goal, not a gate |
| Same topic two days in a row | Google News + YouTube refresh continuously, but if the same headline dominates both days the agent will pick it twice. Manual intervention: edit `TREND_QUERIES` in `daily_agent.py` to broaden the queries |

---

## Files created for the agent

- `scripts/daily_agent.py` — main orchestrator (research → script → render → SEO → email)
- `scripts/generate_script.py` — LLM-powered script writer with viral framework prompt
- `scripts/install_scheduler.py` — Windows Task Scheduler installer
- `.env` — all keys (now includes AGENT_EMAIL_FROM, AGENT_EMAIL_TO, AGENT_EMAIL_APP_PASSWORD placeholders)

Logs go to `scripts/logs/daily_agent_*.log` once the scheduler runs.
