---
name: onboard
description: "First-run setup for the Content Repurpose System. Walks a creator through connecting their YouTube channel, writing their Voice DNA into the content prompts, and (optionally) wiring up Apify, Supabase, and Twitter keys — then prints the end-to-end workflow they can run next. Trigger on 'onboard', 'set up the content system', 'set up content repurpose', 'get started with content repurpose', 'configure my channel', or the first time someone tries to use ideation / hooks / outlines / content-cascade / short-form / yt-titles without having configured a channel yet."
---

# Onboarding — Content Repurpose System

This is **Step 0** of the system. Run it once. It personalizes every other skill to one creator so the titles, hooks, blog posts, and clips come out in *their* voice and grounded in *their* channel's data — not generic AI slop.

Be conversational and fast. Ask for what you need, write the config, confirm, and hand off to the workflow. Do not lecture.

## What this sets up

By the end the creator will have:

1. **Their channel connected** — so `yt-titles` and `content-cascade` can read their real upload history and "latest video."
2. **Their Voice DNA written into the prompts** — so `content-cascade` writes blog/Twitter/LinkedIn in their voice, not a template voice.
3. **Optional integrations** — Apify (reliable transcripts), Supabase (auto-save drafts), Twitter (auto-post threads). All skippable.

Everything is stored inside the plugin at `${CLAUDE_PLUGIN_ROOT}`, so it survives across sessions.

## Step 1 — Connect the channel (required)

Ask: **"What's your YouTube channel handle or URL?"** (e.g. `@SaminYasar_` or `https://www.youtube.com/@SaminYasar_`)

Normalize whatever they give you to a handle (`@SaminYasar_`) and a videos URL (`https://www.youtube.com/@SaminYasar_/videos`).

Then write it into the two places the skills read from:

**a) The performance script** — replace the `CHANNEL_URL` constant:

```bash
python3 - "$CLAUDE_PLUGIN_ROOT" "@THEIR_HANDLE" <<'PY'
import re, sys, pathlib
root, handle = sys.argv[1], sys.argv[2]
p = pathlib.Path(root, "skills/yt-titles/scripts/channel_performance.py")
url = f"https://www.youtube.com/{handle}/videos"
text = p.read_text()
text = re.sub(r'CHANNEL_URL = "[^"]*"', f'CHANNEL_URL = "{url}"', text)
p.write_text(text)
print("Channel set to", url)
PY
```

**b) The channel ID used for "latest video" auto-detect.** The `content-cascade` and `short-form` skills auto-detect the latest upload with `yt-dlp`. A handle works directly — resolve and store the canonical channel ID once so it's unambiguous:

```bash
yt-dlp --flat-playlist --playlist-items 0 --print channel_id "https://www.youtube.com/@THEIR_HANDLE/videos"
```

Take the returned `UC...` id and replace every `YOUR_CHANNEL_ID` placeholder in the skills:

```bash
grep -rl 'YOUR_CHANNEL_ID' "$CLAUDE_PLUGIN_ROOT/skills" | while read -r f; do
  perl -pi -e 's/YOUR_CHANNEL_ID/UCxxxxxxxxxxxxxxxxxxxxxx/g' "$f"
done
```

(If `yt-dlp` isn't installed yet, skip the ID resolution, leave the handle-based URL in place, and note it in the prerequisites step below — the handle URL still works for most operations.)

Confirm: *"Connected to [@handle]. I can now read your upload history and pull your latest video automatically."*

## Step 2 — Capture Voice DNA (required, ~3 questions)

The single biggest quality lever in this system is the voice prompts. Out of the box they are generic. Personalize them.

Ask the creator (batch these, don't drag it out):

1. **"In one or two sentences, how would you describe your voice?"** (e.g. *warm-confident, analogy-first, real-number proof, soft community CTAs*)
2. **"Who's your audience and what do you teach them?"** (e.g. *non-coders learning to build and automate with Claude*)
3. **"Any signature moves?"** — recurring analogies, phrases you always/never use, a standard CTA (e.g. *"links in the description," "come build with us in the Claude Club"*).

If they already keep a voice profile somewhere (many creators do — e.g. a `voice-dna.md`), offer: *"If you have a voice doc, point me at it and I'll fold it in."* Read it if provided.

Then weave their answers into the **top** of each prompt file as a `## Voice DNA` block (don't delete the existing craft guidance below it — that's the framework; their voice is the flavor):

- `${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/blog-system-prompt.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/twitter-system-prompt.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/linkedin-system-prompt.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/linkedin-lead-magnet-system-prompt.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/guide-system-prompt.md`

Insert a block like this at the top of each (tailored per platform — punchier for Twitter, more structured for the blog):

```markdown
## Voice DNA — [Creator Name]
- **Voice:** [their description]
- **Audience:** [who they teach]
- **Signature moves:** [analogies / phrases / CTA]
- **Avoid:** [anything they said they never do]

Write everything below through this voice. When the craft guidance and the voice conflict, the voice wins.
```

Confirm what you wrote and let them tweak it.

## Step 3 — Optional integrations

Say plainly: *"These are all optional. The system works without them — they just add reliability and automation. Want to set any up now, or skip and add later?"*

If they want any, copy the env template and fill what they give you:

```bash
cp "$CLAUDE_PLUGIN_ROOT/.env.example" "$CLAUDE_PLUGIN_ROOT/skills/content-cascade/.env" 2>/dev/null || true
```

- **Apify** (`APIFY_API_TOKEN`) — most reliable transcript fetching, especially for videos uploaded in the last hour. Free tier at apify.com.
- **Supabase** (`SUPABASE_SERVICE_ROLE_KEY` + project URL) — auto-saves blog posts and social drafts to a database instead of local files. If they want this, also replace `YOUR_SUPABASE_URL` in `content-cascade/SKILL.md` with their project URL.
- **Twitter/X** (4 keys) — lets `content-cascade` auto-post the generated thread.

Write the values into `${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/.env`. Never echo secrets back in full — confirm with the last 4 characters only.

## Step 3b — Carousel profile (optional)

`/carousels` draws slides that look like posts on X: photo, name, badge, handle. Ask: *"For carousels: what name and handle should show on each slide, do you have a verified badge, and where is a square headshot photo on this computer?"* Skip if they don't want carousels yet.

Write the answers to `${CLAUDE_PLUGIN_ROOT}/skills/carousels/profile.json` (git ignores it):

```json
{ "name": "Samin Yasar", "handle": "@SaminYasar_", "verified": true, "headshot": "/Users/you/Pictures/headshot.png" }
```

Store only the path to the photo. Never copy the photo into the plugin. If the file doesn't exist, say so; the slides draw a gray circle until it does.

## Step 4 — Prerequisites check

These power transcript fetching and channel data. Check and report; offer the install commands if missing:

```bash
command -v yt-dlp >/dev/null && echo "yt-dlp ✓" || echo "yt-dlp ✗  → pip install yt-dlp"
command -v node   >/dev/null && echo "node ✓"   || echo "node ✗    → install Node.js"
command -v python3 >/dev/null && echo "python3 ✓" || echo "python3 ✗"
python3 -c "import PIL" 2>/dev/null && echo "Pillow ✓" || echo "Pillow ✗  → python3 -m pip install Pillow (for /carousels and /reels)"
```

If `youtube-transcript` (the free Node fallback) matters to them: `npm install youtube-transcript`.

## Step 5 — Show them the workflow

Finish by printing the end-to-end map so they know what to run next. Keep it tight:

```
✅ Content Repurpose System is set up for [@handle].

The workflow, start to finish:

  BEFORE you film
  1. /ideation <topic>     → positioned video ideas (gaps + desire + shock score)
  2. /yt-titles <idea>     → titles ranked against YOUR best performers
  3. /hooks <title>        → scroll-stopping hook (visual + spoken + text)
  4. /outlines <idea>      → a recording-ready outline

  → film & upload the video →

  AFTER you publish
  5. /content-cascade <url or "latest">  → blog + Twitter thread + LinkedIn post (your voice)
  6. /short-form <url or "latest">       → 3–5 Reels/Shorts/TikTok clips with hooks & captions
  7. /reels <video path or url>          → plan, film hooks, render 9:16 reels
  8. /carousels <video folder>           → tweet-style slides + LinkedIn PDF + captions
  9. /publish-pack <video folder>        → finished/ folder + PUBLISH PLAN.md (where and when)

Try this now:  /ideation Claude Code for stock trading
```

## Notes

- Re-running `/onboard` is safe — it updates the same config in place. Use it when the creator switches channels or wants to refresh their Voice DNA.
- Nothing here touches their YouTube account or posts anything. It only reads public upload data and writes local config.
