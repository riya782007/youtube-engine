# Setup Guide — channels, credentials, assets, and the v3 engine

This is your **do-this-now** guide. Work through Parts A–C in parallel while I finish the
engine. Part D explains what changed in **v3** (real stock footage, faster motion, louder
mix, optional ElevenLabs voice); Part E is the psychology that drives the design; Part F is
your exact day-to-day procedure once everything is connected.

A quick safety note: **I cannot create accounts, sign in, or enter your passwords for you.**
Account creation and Google sign-in/consent must be done by you. I'll automate everything
*after* the credentials exist on your machine.

---

## PART A — Create the 3 YouTube channels

You'll make three channels under your one Google account using **Brand Accounts** (this lets
one login own multiple channels — far easier than three separate Gmail logins).

1. Sign in to **youtube.com** with your Google account.
2. Click your **profile picture (top-right) → "Create a channel"**.
3. When asked, choose **"Use a custom name"** (this creates a Brand Account) and name it **AI Tadka**.
4. Make the second and third channels: profile picture → **Switch account → Create a channel** →
   name them **Paisa Pathshala** and **Dhandha Dimaag**.
   (Or: youtube.com → Settings → *Add or manage your channel(s)* → **Create a channel**.)
5. For **each** channel, set:
   - **Handle:** `@AITadka`, `@PaisaPathshala`, `@DhandhaDimaag` (Settings → Channel → Basic info).
     If a handle is taken, pick the closest variant and tell me so I update `channel.json`.
   - **Profile picture & banner** (your logo / a simple branded banner).
   - **Description:** copy the `description_footer` from each `channels/<name>/channel.json`.
   - **Keywords:** use the `seo.tags` list from the same `channel.json`.

> Tip: keep each channel visually distinct (the engine already gives them different colour
> themes). YouTube's "inauthentic/duplicate content" policy is the #1 risk for multi-channel
> AI content — different voices, themes, and angles (already built in) keep you on the safe side.

---

## PART B — Get the upload credentials (Google Cloud, one time)

This is what lets `scripts/upload.py` post videos for you (always as **private** first, so you
review before anything goes public).

1. Go to **console.cloud.google.com** → create a project, name it **youtube-engine**.
2. **APIs & Services → Library →** search **"YouTube Data API v3" → Enable**.
3. **APIs & Services → OAuth consent screen:**
   - User type: **External** → Create.
   - App name: `youtube-engine`; user support email: your email; developer email: your email.
   - **Scopes:** add `https://www.googleapis.com/auth/youtube.upload`.
   - **Test users:** add your own Gmail address. (Leave the app in "Testing" — that's fine.)
4. **APIs & Services → Credentials → Create credentials → OAuth client ID:**
   - Application type: **Desktop app** → Create.
   - **Download the JSON.** Save it in the project root exactly as:
     `C:\Users\Riya yadav\youtube engine\client_secret.json`
     (It's already gitignored — it never leaves your machine.)
5. Install the upload libraries once (double-click a `.bat` I can make, or run):
   `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`

**Multi-channel note:** OAuth authorizes whichever channel you pick during sign-in. The first
time you upload to each channel, run with a separate token file so they don't clash, e.g.
`python scripts/upload.py --dir "<render folder>" --token youtube_token_aitadka.json`
— and on the Google screen, choose that channel's Brand Account. I'll wire a clean per-channel
upload command once your `client_secret.json` is in place.

This OAuth set is the only credential I still need from you. Your **Sarvam** (voice) and
**Pexels** (stock footage) keys are already in `.env` and working.

### Optional but recommended: ElevenLabs (the pronunciation fix)
You flagged the voice as sounding "unreal." Sarvam is good but has a ceiling. The real fix is
**ElevenLabs' multilingual voice**, which the engine now supports automatically: the moment an
`ELEVENLABS_API_KEY` exists in `.env`, every video uses it instead of Sarvam — nothing else to
change. To enable it: make a free account at **elevenlabs.io → Profile → API key**, then add one
line to `.env`: `ELEVENLABS_API_KEY=your_key_here`. Defaults pick a sensible voice per channel;
we can fine-tune later. (If you'd rather stay free for now, leave it blank — Sarvam keeps working.)

---

## PART C — Assets to download (the "what it'll take" list)

**Big change in v3: you no longer need to find video footage or pictures.** The engine now pulls
real, moving **stock B-roll from Pexels automatically** for every scene (using the per-scene
search terms in each job file) and dims it behind the text. So the asset list is now just audio.
Drop these files into each channel's `music/` folder; the pipeline auto-detects them.

**1. Background music — `channels/<name>/music/bgm.mp3`** (one per channel)
- Match the mood in each `channel.json` → `music_mood`:
  - AI Tadka → upbeat electronic / tech
  - Paisa Pathshala → calm confident lo-fi / corporate
  - Dhandha Dimaag → cinematic build / motivational
- Free, safe sources (check "no attribution / free for YouTube"):
  - **YouTube Audio Library** (studio.youtube.com → Audio Library) — safest for monetization
  - **Pixabay Music** (pixabay.com/music)
  - **Chosic** (chosic.com/free-music)

**2. Sound effects (optional but recommended) — two tiny files per channel:**
- `channels/<name>/music/sfx_whoosh.mp3` — a short whoosh (plays on each scene change)
- `channels/<name>/music/sfx_ding.mp3` — a soft pop/ding (plays on the final payoff)
- Free sources: **Pixabay SFX** (pixabay.com/sound-effects — search "whoosh transition",
  "notification pop"), **Mixkit** (mixkit.co/free-sound-effects), **Freesound** (freesound.org).
- Keep them short (whoosh < 1s, ding < 1s). One pair can be reused across all three channels.

**Nothing else is required.** Footage is automatic (Pexels), fonts load from Google Fonts, and
icons are emoji. The only files you place by hand are the music + the two SFX per channel above.

---

## PART D — What I upgraded in the engine (v3)

**Real stock footage (the "I saw none of this" fix):**
- Every scene now plays a **real, moving Pexels clip behind the text**, cropped to 1080×1920,
  with a slow **Ken Burns push** and a **crossfade** between clips.
- A **readability scrim** dims the footage just enough so the white text always pops.
- You control the footage per scene with a `"broll"` search term in the job file (e.g.
  `"broll": "typing on laptop keyboard closeup"`). No term → that scene falls back to the
  animated gradient, so a video never breaks if Pexels has nothing.

**Faster, punchier motion (the "boring" fix):**
- Each scene now **zoom-punches in** and the words snap on a **tighter stagger**.
- A subtle **cut "flash"** punctuates every scene change (lands with the whoosh SFX).
- Living overlay texture (grid + particles + glow) rides **above** the footage, so the frame
  is never static even when the clip is calm.
- Branded **end Call-To-Action** card + bottom progress bar.

**Better sound (the "great sound" ask):**
- After rendering, the whole mix is **normalized to YouTube's −14 LUFS** target, so the voice
  is consistently loud and "produced" (borrowed from the pro Shorts-editing playbook).
- If the SFX files exist, a **whoosh** hits every scene change and a **ding** lands on the payoff.

**Pronunciation (the "unreal" fix):**
- Sarvam path: cleaner punctuation → better prosody, more expressive voices, numbers spelled in
  words. This is the free baseline.
- **The real fix is ElevenLabs** (see Part B): add one key and the engine auto-switches to a far
  more natural multilingual voice. This is the single biggest quality jump available.

---

## PART E — The psychology behind it (why it retains)

These are baked into the template + the example scripts; keep them in mind when you write new ones.

- **Win the first 1–2 seconds.** Open on a *pattern interrupt* — a bold claim or a question
  ("Resume pe ghante mat lagao", "Salary 2 hafte me gayab?"). The hook scene is built for this.
- **Open a curiosity loop**, pay it off at the end. The brain stays to "close" the loop.
- **Never go static.** Constant subtle motion holds the eye — that's the whole point of the
  living background + camera breathing.
- **One idea per scene, fast cadence** (~3–4s). Each cut is a tiny re-hook.
- **Sync sight + sound.** Word reveal + whoosh on the same beat feels satisfying and "produced".
- **Emphasise the payoff word** (colour + scale pulse) so the key idea lands visually.
- **Keep it ~15–20s.** Higher % watched → the algorithm pushes Shorts harder. End on a clear CTA.
- **Write like you talk:** short lines, commas where you'd breathe, `?` and `...` for tension.

---

## PART F — Your exact day-to-day procedure (once connected)

This is the loop you'll run per video. Steps 2–4 are one command; I can also run them for you.

1. **Write the idea** into a job file (copy `channels/<name>/jobs/example.json` to a new name).
   Fill `title`, `voice` (the spoken script), 5 `captions` (each with `icon`, `kicker`, `line`,
   and a short **English** `broll` search term). That's the only creative work.
2. **Build it** — double-click `scripts/run_demo_v3.bat` (AI Tadka), or run:
   `python scripts/make_video.py --job channels/<name>/jobs/<your_job>.json`
   The engine: makes the voice → fetches Pexels B-roll → renders → normalizes audio → writes
   `output.mp4` in a new `renders/` folder.
3. **Review** `output.mp4` yourself (quality gate — nothing ever auto-posts).
4. **Upload** as *private* with `python scripts/upload.py --dir "<that render folder>"`, then
   you flip it to Public in YouTube Studio when you're happy. (We'll wire per-channel tokens
   once `client_secret.json` exists.)

**What it takes per video:** ~2 minutes of your typing + ~1–3 minutes of machine time. The only
running costs are API calls (Sarvam/Pexels free tiers cover daily posting; ElevenLabs optional).

---

## Your setup checklist (one-time)

1. ☐ Create the 3 channels + branding (Part A); tell me any handle you had to change.
2. ☐ Do the Google Cloud setup and drop `client_secret.json` in the project root (Part B).
3. ☐ *(Optional, big quality jump)* add `ELEVENLABS_API_KEY` to `.env` for natural voice (Part B).
4. ☐ Download 1 `bgm.mp3` per channel + a `sfx_whoosh.mp3` / `sfx_ding.mp3` pair into each
   `channels/<name>/music/` (Part C). **Footage is automatic now — skip video hunting.**
5. ☐ Double-click `scripts/run_demo_v3.bat` to render a v3 demo, then tell me how it looks —
   we tune from there and wire per-channel uploads.

You handle accounts + audio; I handle all the building and automation. Footage, voice, motion,
captions, and the audio mix are all automatic.

> ⚠️ **Security:** the Sarvam and Pexels keys were pasted in chat earlier, so treat them as
> exposed — **regenerate both** (Sarvam dashboard / Pexels API page) and paste the new ones
> into `.env` only. Keys live in `.env` (gitignored) and are never hard-coded in any script.
