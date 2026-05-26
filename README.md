# YouTube Engine — faceless Hinglish Shorts pipeline

One job file in → a finished, captioned, voiced vertical Short out.
Built on **Hyperframes** (HTML → MP4) + **Sarvam AI** (Hindi/Hinglish voice).

Three channels, each high-RPM and faceless-friendly:

| Folder | Channel | Niche | Voice |
|---|---|---|---|
| `channels/ai-tadka` | AI Tadka 🤖 | AI tools & how-to | rohan |
| `channels/paisa-pathshala` | Paisa Pathshala 🪙 | Personal finance (education only) | shreya |
| `channels/dhandha-dimaag` | Dhandha Dimaag 📈 | Business & startup stories | manan |

---

## How it fits together

```
job.json  ──►  voice.py (Sarvam VO)  ──►  caption timing + token fill
          ──►  index.html in a render folder  ──►  npx hyperframes render
          ──►  output.mp4  +  upload.json  ──►  upload.py (review-gate)
```

You only ever edit a **job file**. Everything else is automatic.

---

## One-time setup

1. **Install tools on your PC**
   - [Node.js](https://nodejs.org) **22 or newer** — check: `node -v`
   - **FFmpeg** (includes ffmpeg + ffprobe) — check: `ffmpeg -version` and `ffprobe -version`
     - If `ffprobe` is "not recognized", FFmpeg isn't on PATH. Reinstall with
       `winget install Gyan.FFmpeg` then **open a new terminal** and re-check.
   - Python 3 — then: `pip install requests`

2. **Add your Sarvam key**
   Open `.env` in this folder and replace the placeholder:
   ```
   SARVAM_API_KEY=sk_your_real_key_here
   ```
   `.env` is gitignored — it never leaves your machine.

3. **(Optional, for auto-upload)** see "Uploading" below.

> Hyperframes itself needs no install — `npx hyperframes` fetches it on first run.

---

## Make a video

```bash
python scripts/make_video.py --job channels/ai-tadka/jobs/example.json
```

This generates the voice, builds the composition, and renders
`channels/ai-tadka/renders/<title>-<timestamp>/output.mp4`.

Useful flags:
- `--no-render` — build `index.html` + voice only (fast check). Preview with
  `cd <render folder> && npx hyperframes preview`.

---

## Writing a job file

Copy any `channels/<name>/jobs/example.json` and edit it:

```json
{
  "channel": "ai-tadka",
  "title": "ChatGPT se 2 minute me professional resume",
  "description": "Optional extra blurb (channel footer is added automatically).",
  "hashtags": ["#ai", "#chatgpt"],
  "music": "music/bgm.mp3",
  "voice": "Pura Hinglish VO script yahan...",
  "captions": [
    { "kicker": "AI HACK", "line": "Resume banao *2 minute* me 🤖" },
    { "kicker": "STEP 1",  "line": "ChatGPT kholo, details daalo" }
  ]
}
```

**Caption markup** (so you never touch HTML):
- `*text*` → highlighted in the channel's **accent** colour
- `**text**` → highlighted in the **secondary** accent colour
- a newline inside `"line"` becomes a line break
- emojis: paste the real emoji, not `&#...;` codes
- 1 to 5 captions; they're spread evenly across the voiceover automatically

**The voiceover** (`voice`) drives the video length — the composition matches
the VO duration. Aim for ~12–20 seconds of speech for a tight Short.

---

## Background music

Drop a royalty-free track at `channels/<name>/music/bgm.mp3` (or any path you set
in the job's `"music"` field, relative to the channel folder). It's mixed in low,
under the voice. Leave `"music"` out to render voice-only.
Use YouTube Audio Library or other no-copyright sources.

---

## Uploading (review gate)

`scripts/upload.py` uploads to YouTube **as private by default** — nothing goes
public until you review it in YouTube Studio and flip it yourself.

First-time Google setup (once):
1. Google Cloud Console → new project → enable **YouTube Data API v3**.
2. OAuth consent screen (External; add yourself as a Test user).
3. Create **OAuth client ID → Desktop app**, download the JSON, save it here as
   `client_secret.json` (gitignored).
4. `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`

Then:
```bash
python scripts/upload.py --dir "channels/ai-tadka/renders/<the-render-folder>"
```
First run opens a browser to authorize; the token is cached in `youtube_token.json`.
Options: `--privacy unlisted|public`, `--publish-at 2026-05-25T13:00:00+05:30`.

> Each YouTube channel is tied to the Google account you authorize with. For a
> separate channel, run upload with `--token youtube_token_<channel>.json` while
> logged into that channel's account.

---

## Folder map

```
youtube engine/
├─ .env                     # your keys (gitignored)
├─ requirements.txt
├─ scripts/
│  ├─ voice.py              # Sarvam Hinglish VO  (text → voice.wav)
│  ├─ make_video.py         # orchestrator        (job → output.mp4)
│  └─ upload.py             # review-gate uploader (output.mp4 → YouTube)
└─ channels/<name>/
   ├─ channel.json          # brand, voice preset, theme, SEO defaults
   ├─ compositions/template.html   # themed Hyperframes template ({{TOKENS}})
   ├─ jobs/example.json      # sample job — copy & edit these
   ├─ music/                 # drop bgm.mp3 here
   └─ renders/               # output lands here (gitignored)
```

---

## Safety & good practice

- **Never paste API keys in chat or commit them.** Keys live only in `.env` /
  `client_secret.json`, both gitignored. Rotate any key that's been exposed.
- **Finance channel = education only.** No specific buy/sell calls (policy + trust).
- **Business channel = verify every fact/number** before rendering.
- **Vary content per channel** to stay clear of YouTube's "inauthentic content"
  rules — different voices, themes, and angles are already set up for you.
- Upload defaults to **private** so you always get the final say.

---

## Coming later (not wired yet)

- HeyGen avatar + ElevenLabs voice as an alternative to Sarvam
- Whisper word-level caption timing (instead of the current even split)
- A daily content scheduler
