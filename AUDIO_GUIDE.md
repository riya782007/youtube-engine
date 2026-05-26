# Audio Guide — Music + SFX for the YouTube Engine

This is the practical guide. Drop these files in the right places and the engine
picks them up automatically — no code changes needed.

---

## Where files go

```
channels/<channel-name>/music/
├─ bgm.mp3          # background music (loops under the voice)
├─ sfx_whoosh.mp3   # plays at every scene cut (optional)
└─ sfx_ding.mp3     # plays at the final payoff scene (optional)
```

The engine checks for each file's existence. Missing = silently skipped (the
render still works).

**Format requirements:**
- MP3 or WAV (MP3 preferred for size)
- Sample rate: 44.1 kHz or 48 kHz (anything modern)
- BGM: 30 seconds is plenty (the engine loops or trims as needed)
- SFX: under 1 second each (whoosh ~0.4s, ding ~0.3s)
- All channels (mono or stereo both work; stereo is converted at mix time)

---

## PART 1 — YouTube Audio Library (your best free source)

YouTube's official library is the safest option because it's pre-cleared for
monetization and explicitly licensed for YouTube use.

### How to access it

1. Go to **studio.youtube.com** (you must be signed in to your channel)
2. In the left sidebar, scroll to the bottom → click **Audio Library**
3. You'll see two tabs at the top: **Music** and **Sound effects**

### How to download music for BGM

1. Click the **Music** tab
2. Use the filters at the top:
   - **Track title** — search by mood or keyword
   - **Genre** — pick one that fits the channel
   - **Mood** — Happy, Calm, Dramatic, Inspirational, Bright, Funky, Angry, etc.
   - **Duration** — set min to 30 seconds
   - **Attribution** — set to **No attribution required** (safest for monetization)
3. Click any track to preview
4. Click the **download arrow** (right side of the row) → saves as MP3
5. Rename the file to `bgm.mp3` and put it at:
   ```
   c:\Users\Riya yadav\youtube engine\channels\ai-tadka\music\bgm.mp3
   ```
6. Repeat for `paisa-pathshala` and `dhandha-dimaag`

### Recommended search terms per channel (paste into the search bar)

**AI Tadka 🤖** (energetic, modern, electronic)
- "future tech" • "cyber" • "electronic upbeat" • "synthwave"
- Filter: Genre = **Electronic** OR **Cinematic**, Mood = **Bright** OR **Funky**

**Paisa Pathshala 🪙** (calm, confident, trustworthy)
- "corporate" • "lo-fi piano" • "calm jazz" • "confident background"
- Filter: Genre = **Jazz & Blues** OR **Cinematic**, Mood = **Calm** OR **Inspirational**

**Dhandha Dimaag 📈** (cinematic, motivational, building energy)
- "motivational cinematic" • "epic build" • "documentary" • "inspiring orchestra"
- Filter: Genre = **Cinematic**, Mood = **Inspirational** OR **Dramatic**

### How to download SFX (whoosh + ding)

1. Click the **Sound effects** tab
2. Set **Duration**: less than 1 minute (default is fine)
3. For the whoosh:
   - Search: `whoosh transition` or `swoosh`
   - Pick one that's < 1 second, sharp attack, clean tail
   - Rename to `sfx_whoosh.mp3` → put in each channel's `music/` folder
4. For the ding:
   - Search: `notification` or `pop` or `bell ding` or `success`
   - Pick a soft, short positive sound
   - Rename to `sfx_ding.mp3`
5. Same SFX pair can be reused across all 3 channels (one download = 3 channels)

**Pro tip:** YouTube Audio Library SFX has no attribution requirement at all.

---

## PART 2 — Other free SFX sources (when YouTube doesn't have what you want)

### Pixabay (best alternative — fully free, no attribution)
- URL: **pixabay.com/sound-effects/**
- License: Pixabay Content License — **no attribution required, free for commercial use**
- Quality: very high; lots of "modern" / TikTok-style transitions
- Search terms that work well:
  - `whoosh transition short`
  - `swoosh fast`
  - `tiktok pop`
  - `notification ding`
  - `bell pop short`
  - `riser` (build-up before a reveal)
  - `impact bass` (heavy hit on scene cut)
- Click any sound → green Download button → MP3
- **No account needed** (but free signup gets you longer downloads + history)

### Mixkit (curated, fewer choices but high-quality)
- URL: **mixkit.co/free-sound-effects/**
- License: Mixkit License — free for commercial, no attribution required
- Categories worth browsing:
  - **Cinematic** → "trailer impacts" / "impact whoosh"
  - **Notification** → soft pops + dings
  - **Game** → "swoosh" / "swipe" effects
- No account needed; instant MP3 download

### Freesound (huge library, mixed licenses — read carefully)
- URL: **freesound.org**
- Sounds are CC0, CC-BY, CC-BY-NC, etc. — **filter by license** before downloading
- Best for very specific niche sounds (cash register, keyboard typing, robot beep)
- Account required (free signup)
- For commercial YouTube use, **filter to CC0 only** to avoid attribution headaches

### Zapsplat (huge library, requires free account)
- URL: **zapsplat.com**
- Free tier: 320kbps MP3 (good enough), unlimited downloads
- License: free for commercial use **with attribution** on the standard tier
  - Their attribution can go in the YouTube video description (not on-screen)
- Premium tier removes attribution but isn't necessary for a side project

### Descript (your question — yes, this works too)
- URL: **descript.com** (specifically the "SquadCast" / Studio Sound tools)
- Descript's main product is an audio/video editor with an SFX library built in
- The library uses **Storyblocks** under the hood (paid subscription)
- **Verdict:** Descript's SFX is fine but **not worth the subscription just for SFX**.
  Pixabay + YouTube Audio Library together cover everything Descript offers.
- Where Descript IS valuable: **Studio Sound** filter — auto-removes background noise
  from voice recordings. Useful if you ever record human voice. Not needed for the
  current Sarvam/ElevenLabs pipeline (those produce clean audio).

### Quick comparison

| Source | Free? | Attribution? | Quality | Best For |
|---|---|---|---|---|
| YouTube Audio Library | ✅ | None | Good | First stop, safest licensing |
| Pixabay SFX | ✅ | None | Excellent | Modern TikTok-style transitions |
| Mixkit | ✅ | None | Excellent | Cinematic impacts, polished sounds |
| Freesound (CC0) | ✅ | None (CC0 only) | Mixed | Niche/specific sounds |
| Zapsplat | ✅ free tier | Required (free tier) | Excellent | Specific sounds you can't find elsewhere |
| Descript | ❌ subscription | None (paid) | Good | If you already have Descript for editing |

---

## PART 3 — Exact files to grab right now (5-minute setup)

To get the engine producing fully-polished videos, you need 9 files total:

### From YouTube Audio Library (one trip, 5 minutes)

**Music tab:**
1. Search `tech upbeat`, filter Genre=Electronic → download → rename `bgm.mp3` → put in `channels/ai-tadka/music/`
2. Search `corporate calm`, filter Genre=Jazz → download → rename `bgm.mp3` → put in `channels/paisa-pathshala/music/`
3. Search `motivational cinematic`, filter Genre=Cinematic → download → rename `bgm.mp3` → put in `channels/dhandha-dimaag/music/`

**Sound effects tab:**
4. Search `whoosh`, pick one short clean whoosh → download → name `sfx_whoosh.mp3`
5. Search `pop` or `notification`, pick a short soft pop → download → name `sfx_ding.mp3`
6. Copy both files into all 3 channels' `music/` folders (same SFX pair x 3)

### Alternative: Pixabay (if YouTube Audio Library is slow)

Same workflow but at:
- Music: pixabay.com/music
- SFX: pixabay.com/sound-effects

---

## PART 4 — Why the engine's auto-generated SFX sounded bad

The previous run synthesized `sfx_whoosh.mp3` and `sfx_ding.mp3` using ffmpeg
generators (white noise + sine waves with envelope shaping). That approach produces
the *shape* of a whoosh/ding but lacks the harmonic complexity, transient sharpness,
and tail decay of a real recorded sound. **It always sounds artificial and slightly
unsettling** — exactly what you noticed.

Real curated SFX are recorded from physical sources (cymbals, woodblocks, real wind
through microphones) or designed by audio engineers in DAWs. There's no shortcut.

The engine has been updated to:
1. **Not auto-generate** SFX anymore (the bad files have been deleted)
2. **Only play SFX when real curated files exist** in `channels/<name>/music/`
3. **Render cleanly with no SFX at all** if you skip Part 3 above

---

## PART 5 — Volume balancing (already wired, just FYI)

The engine mixes audio at these levels:
- Voice: 1.0 (full)
- Music: 0.12 (sits well under voice — you'll barely notice it consciously, that's correct)
- Whoosh SFX: 0.45 (loud enough to punctuate, not loud enough to mask voice)
- Ding SFX: 0.6 (single payoff hit, can be louder)

After the render, the entire mix is normalized to **YouTube's -14 LUFS** target so
loudness is consistent with everything else on the platform.

If a particular SFX sounds too loud or quiet *relative to your specific BGM*, edit
these constants in `scripts/make_video.py`:
```python
MUSIC_VOLUME = 0.12
SFX_WHOOSH_VOLUME = 0.45
SFX_DING_VOLUME = 0.6
```

---

## PART 6 — Music licensing safety checklist

Before using any track in a YouTube video for monetization, verify:

- ✅ License says "free for commercial use" or equivalent
- ✅ Attribution requirement is either none, or you can put it in the YouTube description
- ✅ You're allowed to use it on social platforms (some "free" tracks restrict to web only)
- ✅ The track isn't a remix of copyrighted material (e.g. don't use "Beat that sounds like Drake")

YouTube's own Audio Library tracks pass all four automatically. That's why it's
the recommended starting point.

---

## Summary — your action items

1. ☐ Open studio.youtube.com → Audio Library
2. ☐ Download 3 BGM tracks (one per channel) — set them as `bgm.mp3` in each `music/` folder
3. ☐ Download 1 whoosh + 1 ding SFX — name them `sfx_whoosh.mp3` / `sfx_ding.mp3`
4. ☐ Copy the SFX pair into all 3 channels' `music/` folders
5. ☐ Re-run `python scripts/make_video.py --job channels/ai-tadka/jobs/example.json`
6. ☐ The engine picks up the new audio automatically — no code changes

That's it. Once these 5 files exist, every render afterwards has proper sound.
