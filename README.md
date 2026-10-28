# Content Repurpose System

**Turn one finished video into blog and social drafts, clip plans, vertical reels with hooks you can test, and carousels. Then get one folder that's ready to post, with a plan for where and when.**

This [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin has ten skills. **Onboard once** to set your channel and voice. Then use the skills to plan each video and reuse the finished edit. Title ideas use your channel performance data.

> The running example in this README uses the channel **[@SaminYasar_](https://www.youtube.com/@SaminYasar_)** — Claude Code tutorials for stock-trading automation. Swap in your own handle during onboarding and everything below works the same.

---

## The mental model

```
                         ┌─────────────┐
                         │  /onboard   │   ← run once: channel + Voice DNA + keys
                         └──────┬──────┘
                                │
        BEFORE you film ────────┼──────── AFTER you publish
                                │
   /ideation  →  /yt-titles     │     /content-cascade  →  blog + Twitter + LinkedIn (+guide)
       ↓             ↓          │            ↓
   /hooks     →  /outlines      │     /short-form       →  3–5 clip plans
       │                        │            ↓
       │                        │     /reels            →  plan → film hooks → render 9:16 variants
       │                        │            ↓
       │                        │     /carousels        →  tweet-style slides + LinkedIn PDF
       │                        │            ↓
       └──── film the video ────┘     /publish-pack     →  finished/ folder + PUBLISH PLAN.md
```

You publish **one** video. The system turns it into **a week of content** across six channels. Every run ends in one `finished/` folder: numbered sections, captions per platform, and a plan that says what to post where, day by day.

---

## Install

### Option A — as a plugin (recommended)

In Claude Code:

```
/plugin marketplace add AI-Answer/ContentRepurposeSystem
/plugin install content-repurpose-system
```

Restart Claude Code so the skills load, then run `/onboard`.

### Option B — clone and install the skills directly

```bash
git clone https://github.com/AI-Answer/ContentRepurposeSystem.git
cd ContentRepurposeSystem
cp -R skills/* ~/.claude/skills/      # note: no trailing slash on skills/*
```

Restart Claude Code, then run `/onboard`.

### Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| **yt-dlp** | reads your upload history + "latest video" | `pip install yt-dlp` |
| **Node.js** | transcript fetching + thread posting | [nodejs.org](https://nodejs.org) |
| **Python 3** | channel performance and reel scripts | install Python 3 if missing |
| **ffmpeg + ffprobe** | reel crops, audio, rendering, and checks | `brew install ffmpeg whisper-cpp` |
| **whisper-cli** | local word timestamps for reel cuts and captions | included in `brew install ffmpeg whisper-cpp` |
| **NumPy + Pillow** | raw-camera alignment, reel images, and carousel slides | `python3 -m pip install numpy Pillow` |
| `youtube-transcript` *(optional)* | free transcript fallback | `npm install youtube-transcript` |

The `/onboard` skill checks the base channel tools. `/reels` also checks the reel tools above. `/carousels` and `/publish-pack` need only Python 3 and Pillow. Whisper needs a local model file; point `whisper-cli -m` at it. For Python packages, use a virtual environment if your Python requires one.

---

## Step-by-step walkthrough

Here's exactly what a session looks like, from zero to a full content drop, using @SaminYasar_ as the example.

### Step 1 — `/onboard` (once)

```
You:  /onboard
```

Claude walks you through three things:

**1. Connect your channel.**
```
Claude: What's your YouTube channel handle or URL?
You:    @SaminYasar_
Claude: Connected to @SaminYasar_. I can now read your upload history
        and pull your latest video automatically.
```
This writes your channel into the performance script and resolves your canonical channel ID, so later skills can find your real videos.

**2. Capture your Voice DNA.** Claude asks ~3 questions and folds the answers into every content prompt:
```
Claude: In one or two sentences, how would you describe your voice?
You:    Warm and confident, analogy-first (poker, thermostats, car
        insurance), I always back claims with real numbers, and I close
        with a soft "come build with us in the Claude Club."
Claude: Who's your audience and what do you teach them?
You:    Non-coders learning to build and automate with Claude — right now,
        stock-trading automation.
```
From now on, your blog/Twitter/LinkedIn output sounds like *you*, not like a template.

**3. Optional keys.** Apify (reliable transcripts), Supabase (auto-save drafts), Twitter (auto-post). All skippable — say "skip" and add them later.

**4. Carousel profile (optional).** The name, handle, badge, and headshot path that show on your carousel slides. It's saved in `skills/carousels/profile.json`, which git ignores. Only the path to your photo is stored.

**At the end, onboarding prints your workflow map** and a suggested first command. You only do this once per channel.

---

### Step 2 — `/ideation` — what should I make?

```
You:  /ideation Claude Code for stock trading
```

You get **7–10 positioned ideas**, each mapped to a core desire, scored for "shock," and checked against competitive gaps. The Tier 1 picks look like:

```
## I Let Claude Code Copy Every Trade a Senator Makes

- Angle:           Turn public Capitol Trades disclosures into an automated
                   paper-trading bot — nobody has shown the full build.
- Core Desire:     Money  →  Proxy: "trade like someone with inside access,
                   legally, on autopilot"
- Shock Score:     86/100
- Format:          Case Study (build + result reveal)
- Competitive Gap: Plenty of "politicians beat the market" explainers,
                   zero end-to-end "here's the bot" tutorials.
- Why Now:         Capitol Trades API is free + congressional trading is
                   trending after the latest disclosure cycle.
```

Pick one and carry it into the next steps.

---

### Step 3 — `/yt-titles` — title it like your hits

```
You:  /yt-titles a video where I build a bot that copies senator stock trades
```

This is the skill that makes the system *yours*: **Step 1 pulls your actual top performers** (via `channel_performance.py`), finds the title patterns your audience already rewards, then generates titles in that pattern. Output:

```
## Your Top Performers (last 3 months)
Your "I Let Claude…" + concrete-outcome format outperforms your how-to titles
~3x on views/day. Numbers and a clear result are doing the work.

## Title Options

### Tier 1 — High Confidence
1. I Built a Bot That Copies Senator Stock Trades (Claude Code)
   Based on your "I Built…" pattern — proven, names the tool, concrete.
2. Claude Code vs. Congress: I Copied Their Trades for 30 Days
   Your contrarian + timeframe pattern; "vs." adds tension.

### Tier 3 — Swing for the Fences
8. I Gave Claude My Brokerage Account. Here's What Happened.
   Pattern-break curiosity gap — higher risk, higher ceiling.

## Thumbnail Text Options
For "I Built a Bot That Copies Senator Stock Trades":
1. "LEGAL?"      — tension against the title's premise
2. "+18% / MO"   — concrete proof the title withholds
```

---

### Step 4 — `/hooks` — nail the first 15 seconds

```
You:  /hooks I Built a Bot That Copies Senator Stock Trades with Claude Code
```

Uses the Kallaway desire-based framework to produce **three fully-aligned hooks** (visual + spoken + on-screen text), each scored against the Four Commandments:

```
### Hook 1 — Case Study + "About Me"
Spoken:       "I gave Claude Code a list of every stock a senator bought
              last quarter — and let it trade them for me."
Visual:       Screen recording: Capitol Trades feed → Claude Code running →
              Alpaca paper account ticking up
Text overlay: "COPYING CONGRESS"
Power Words:  Subject ✓ Action ✓ Objective ✓ Contrast ✓ Time ✓ (5/6)
Commandments: Alignment ✓ Speed ✓ Clarity ✓ Curiosity ✓ (4/4)
```

---

### Step 5 — `/outlines` — a recording-ready script

```
You:  /outlines the senator-copy-trading bot video, ~14 minutes
```

You get a full outline in recording format: hook, structured body sections with talking points, **visual-aid callouts**, demo beats, source citations, per-section time budgets, and a production-notes block (competitive landscape, title ideas, thumbnail moments, honest limitations). You sit down and film straight from it.

```
## Hook (~60s)            [the aligned hook from Step 4]
## Section 1 — The Setup (~2.5 min)
   Core idea:  Congressional trades are public — and weirdly good.
   Talking points: • Capitol Trades is free  • the disclosure lag
   Visual aid: → screen recording of the Capitol Trades feed
   Source:     capitoltrades.com
## Section 2 — Wiring Claude Code to Alpaca (~5 min)  [demo-heavy]
...
## Production Notes  →  3 competitor titles, 3 thumbnail moments, limitations
```

**→ Now you film and upload the video.** YouTube takes 30–60 min to generate captions; once they're live, continue.

---

### Step 6 — `/content-cascade` — the long-tail content

```
You:  /content-cascade latest
```

Claude auto-detects your latest upload, fetches the transcript, classifies the video (tutorial vs. discussion), and generates — **in your voice**:

- **A 1,500–2,500 word blog post** with SEO metadata (title, description, slug, keywords, tags, cover image)
- **A Twitter/X thread** built around the single best angle
- **A LinkedIn post** mirroring the video's premise
- Because this one is a *tutorial*, it also generates a **LinkedIn lead-magnet post** + a **Skool-ready HTML guide**

Each piece is shown to you for review before saving. With keys configured it can auto-save drafts to Supabase and auto-post the thread; without them, everything saves as local markdown under the video folder's `content/`, next to the reels and carousels.

---

### Step 7 — `/short-form` — slice the clips

```
You:  /short-form latest
```

Scans the transcript for the **3–5 most clip-worthy moments** (self-contained insight, shock value, emotional peak, demo reveal) and for each one gives you timestamps, a scroll-stopping hook, a ready-to-paste caption, and hashtags — ranked by *best for reach / conversions / engagement*.

```
### Clip 1: "Is this legal?" — Best for reach
Timestamps:   02:14 → 03:01   (~47s)
Hook:         Text "IS THIS LEGAL?"  |  Spoken "Yes, copying a senator's
              stock trades is completely legal — here's the catch."
Caption:      Congress has to disclose their trades. So I had Claude trade
              them for me 👀  Full build on the channel.
Hashtags:     #claudecode #ai #stocktrading #investing #fintech
```

---

### Step 8: `/reels`: plan, film, render

```
You:  /reels /path/to/finished-edit.mp4
```

Use this after `/short-form`, or go straight to `/reels` when you want rendered files. It takes a finished local video or a YouTube URL. Add the raw camera takes and their matching mic files for the bottom camera panel.

1. **Plan.** Claude picks 3-6 ideas from the word-timed transcript. It writes `work/reels.json`, `repurpose-plan.md`, and `film-hooks.md`. Each reel gets one footage hook and three film hooks scored with the Kallaway framework.
2. **Film.** Record the listed lines. Each is at most 15 words and 4 seconds. Save them as `hooks-filmed/R1-H2.mov`, and so on. Say "attach my filmed hooks" to resume.
3. **Render.** The renderer's `--all` option makes every reel with each available hook. Each variant keeps the same body. Check the contact sheets, captions against audio, sync, and loudness before posting.

The default is 1080x1920: visuals on top, your raw camera on the bottom, and captions on the seam. Use `--panel-crop x,y,w,h` and `--cam-center x` for a different source layout. The [reels skill](skills/reels/SKILL.md) has the commands and [plan schema](skills/reels/references/reels-json.md).

---

### Step 9: `/carousels`: slides people save

```
You:  /carousels the tips video
```

Claude picks 1-5 ideas that work without the video: a list, prompts to copy, a framework. It writes 6-10 slides per idea in your voice. The cover gets a frame from the video. Other slides get real proof: docs pages, posts, your own screen. Then it renders:

```
carousels/2 - Steal my 2 prompts/
  slides/01.png ... 08.png          1080x1350, light or dark
  Steal my 2 prompts - LinkedIn.pdf one page per slide
  captions.txt                      Instagram, LinkedIn, TikTok (photo mode)
  config.json                       edit and re-render any time
```

The renderer warns about text that runs off a slide, a lone word on a last line, and a cover with no image. Claude opens every slide and fixes what it finds. The [carousels skill](skills/carousels/SKILL.md) has the config format and an [example](skills/carousels/examples/example-config.json).

---

### Step 10: `/publish-pack`: one folder, ready to post

```
You:  make the finished products folder
```

Claude gathers every output for the video into `<video>/finished/`:

```
finished/
  README.md
  PUBLISH PLAN.md
  1 YouTube long-form/
  2 Reels - Instagram, TikTok, YouTube Shorts/      1 - R1 Don't read the docs.mp4 + captions
  3 Hooks to film/
  4 Carousels - Instagram, LinkedIn, TikTok/
  5 Articles - blog, LinkedIn, Substack/
  6 Text posts - X, LinkedIn, Threads, newsletter/
  7 Claude Club - Opus 5.5 playbook/
```

Files are numbered in posting order. Each reel and carousel has a captions file with one section per platform. `PUBLISH PLAN.md` has four parts: what's here, a matrix of where each piece goes, a day-by-day calendar, and a checklist. A script does the copying (APFS clones on a Mac, so big videos take no extra space) and drafts the plan. Claude writes the captions, the "why that split" notes, and the final calendar.

---

## What you have at the end

After the content commands, the reel filming loop, and `/publish-pack`, you have one folder of local files and drafts:

| Asset | From | Ready for |
|-------|------|-----------|
| 📝 Blog post (SEO-optimized) | `content-cascade` | your website / newsletter |
| 🐦 Twitter/X thread | `content-cascade` | X (optionally auto-posted) |
| 💼 LinkedIn post | `content-cascade` | LinkedIn |
| 🧲 LinkedIn lead-magnet post | `content-cascade` *(tutorials)* | LinkedIn → email capture |
| 📚 Skool guide (HTML) | `content-cascade` *(tutorials)* | your Skool / Claude Club |
| 🎬 3–5 clip plans | `short-form` | Timestamps, hooks, and captions for editing |
| 🎬 3-6 reels with available hook variants | `reels` | Reviewed 9:16 files in `out/` |
| 🖼️ 1-5 carousels + LinkedIn PDFs | `carousels` | Instagram, LinkedIn, TikTok photo mode |
| 📦 `finished/` folder + `PUBLISH PLAN.md` | `publish-pack` | Posting, day by day |

Plus, from the pre-production side: a ranked idea, a tested title + thumbnail text, an aligned hook, and a filmable outline — so the next video is faster than the last.

---

## The skills

| Order | Skill | Command | What it does |
|------|-------|---------|--------------|
| 0 | **onboard** | `/onboard` | One-time setup: channel, Voice DNA, optional keys |
| 1 | **ideation** | `/ideation <topic>` | Positioned video ideas with gaps, desire mapping, shock scores |
| 2 | **yt-titles** | `/yt-titles <idea>` | Titles ranked against *your* top performers + thumbnail text |
| 3 | **hooks** | `/hooks <title>` | Kallaway-framework hooks (visual + spoken + text), scored |
| 4 | **outlines** | `/outlines <idea>` | Recording-ready outline with time budgets + production notes |
| 5 | **content-cascade** | `/content-cascade <url\|latest>` | Blog + Twitter + LinkedIn (+ lead magnet + guide) |
| 6 | **short-form** | `/short-form <url\|latest>` | 3–5 clips with hooks, captions, hashtags, timestamps |
| 7 | **reels** | `/reels <video path\|url>` | Plan 3-6 reels, list hooks to film, and render variants |
| 8 | **carousels** | `/carousels <video folder>` | Tweet-style slides, a LinkedIn PDF, and captions per platform |
| 9 | **publish-pack** | `/publish-pack <video folder>` | The numbered `finished/` folder, captions files, and `PUBLISH PLAN.md` |

You can also ask in plain English. "Give me title ideas" triggers `yt-titles`. "Make shorts from my latest video" triggers `short-form`. "What hooks should I film?" and "attach my filmed hooks" trigger `reels`. "Make carousels from this video" triggers `carousels`. "Make the finished products folder", "package everything to publish", and "where should I post what?" trigger `publish-pack`.

---

## Configuration & optional integrations

Everything optional lives in `skills/content-cascade/.env` (copy from [`.env.example`](.env.example)). `/onboard` can write it for you.

- **Apify** — most reliable transcript fetching, especially for videos uploaded in the last hour. Free tier.
- **Supabase** — auto-save blog posts and social drafts to a database instead of local files.
- **Twitter/X** — auto-post the generated thread.

Without any of these, the system still does the full pipeline — it just saves to local markdown and you copy-paste to publish.

> **Note on competitor scanning:** the `ideation`, `outlines`, and `yt-titles` skills can optionally run a YouTube competitor scan via a separate `yt-search` helper that does **not** ship with this plugin. Those steps are clearly marked optional and degrade gracefully — every skill produces its full output without them. Your *own* channel performance data (used by `yt-titles`) is built in and works out of the box.

---

## FAQ

**Do I have to run the skills in order?**
No — each works standalone. The order is the *recommended* end-to-end flow. Already filmed? Jump straight to `/content-cascade`.

**Does this post to my accounts?**
Only if you set up the Twitter keys and explicitly say to post. By default everything saves as a draft for your review.

**"Captions aren't available yet."**
YouTube takes 30–60 minutes to generate captions after upload. Run the cascade again a bit later, or add an Apify token for more reliable fetching of fresh uploads.

**How do I switch channels or refresh my voice?**
Re-run `/onboard` — it updates the same config in place.

---

## License

MIT © [Samin Yasar](https://github.com/Samin12) — see [LICENSE](LICENSE).
