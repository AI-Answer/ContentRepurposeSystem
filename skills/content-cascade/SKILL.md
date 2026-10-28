---
name: content-cascade
description: "Generate blog post, Twitter thread, and LinkedIn post from a YouTube video. Fetches transcript, generates all three content pieces following your voice/style guidelines, and optionally saves as drafts to Supabase. Trigger on phrases like 'generate content for this video', 'content cascade for', 'write a blog post from my video', 'create content from YouTube', 'run content cascade on my latest video', or any request to turn a YouTube video into blog/social content."
---

# Content Cascade

Turn a YouTube video into a full content cascade: blog post + Twitter thread + LinkedIn post. Fetches the transcript, generates all three pieces following your voice guidelines, and optionally saves everything as drafts to Supabase.

## Setup Required

**Run `/onboard` first.** It configures everything below in one pass (channel, Voice DNA, optional keys). If onboarding hasn't been run yet and no channel is configured, suggest running `/onboard` before proceeding. The items below are what onboarding sets up — only do them manually if the user is configuring by hand:

1. **Voice prompts** — Your blog/social voice guidelines live in `${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/`. `/onboard` writes a Voice DNA block into each; otherwise edit the template files directly.
2. **YouTube channel** — `YOUR_CHANNEL_ID` below is replaced with your real channel ID by `/onboard`.
3. **Supabase (optional)** — If you want auto-saving to a database, set up your Supabase project and update the config section at the bottom.
4. **Apify (optional)** — For reliable transcript fetching, get a free API token at https://apify.com and set `APIFY_API_TOKEN` env var.
5. **Twitter/X (optional)** — For auto-posting threads, set Twitter API credentials in `${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/.env`.

## When This Skill Activates

**Activate when the user wants to:**
- Generate blog/social content from a YouTube video
- Create a content cascade from a video they just published
- Write a blog post, Twitter thread, or LinkedIn post from a video transcript
- Run the content pipeline for a new video

**Example triggers:**
- "Run the content cascade on my latest video"
- "Content cascade for my latest video"
- "Generate content for https://youtube.com/watch?v=XYZ"
- "Create blog + twitter + linkedin for [URL]"
- `/content-cascade`
- `/content-cascade [URL]`

## Pipeline Steps

### Step 1 — Get the Video

**If the user provided a YouTube URL**, use it.

**If the user said "latest video" or didn't provide a URL**, auto-detect the most recent upload:

```bash
yt-dlp --flat-playlist --playlist-end 1 --print url --print title "https://www.youtube.com/channel/YOUR_CHANNEL_ID/videos"
```

This returns the URL on the first line and the title on the second line. Confirm with the user: "Found your latest video: [TITLE]. Running the cascade on this one."

### Step 2 — Fetch Transcript

Try these methods in order. If a method fails, move to the next one.

**Method 1 — Apify (most reliable, especially for fresh uploads):**
```bash
node "${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/scripts/fetch-transcript-apify.js" "<youtube-url>"
```
This uses the `karamelo~youtube-transcripts` Apify actor with proxy support and up to 8 retries. Note: this is a synchronous call that may take 30-60 seconds to complete.

**Method 2 — youtube-transcript (free):**
```bash
node "${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/scripts/fetch-transcript.js" "<youtube-url>"
```

**Method 3 — yt-dlp subtitles with original track (free):**

Try `en-orig` first (original uploaded captions), then fall back to `en` (auto-generated). **WARNING:** The `en` auto-generated track sometimes returns wrong transcripts, especially for recently uploaded videos.

```bash
yt-dlp --write-sub --sub-lang en-orig --skip-download --sub-format json3 -o "$TEMP/yt-transcript" "<youtube-url>"
```

If `en-orig` isn't available, fall back to auto-generated:
```bash
yt-dlp --write-auto-sub --sub-lang en --skip-download --sub-format json3 -o "$TEMP/yt-transcript" "<youtube-url>"
```

Then parse the json3 file with Node.js:
```bash
node -e "
const fs = require('fs');
const path = require('path');
const dir = process.env.TEMP;
const file = fs.readdirSync(dir).find(f => f.startsWith('yt-transcript') && f.endsWith('.json3'));
if (!file) { console.error('No subtitle file found'); process.exit(1); }
const data = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
const text = data.events.filter(e => e.segs).map(e => e.segs.map(s => s.utf8 || '').join('')).join(' ').replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
console.log(text);
"
```

**IMPORTANT — Transcript Validation:** After fetching the transcript with ANY method, sanity-check the first 1-2 sentences against the video title. If the transcript content clearly doesn't match the video topic, the transcript is wrong. Discard it and try the next method. If all methods return wrong/no transcripts, tell the user.

**If all methods fail**, captions probably aren't available yet. Tell the user:
> "Captions aren't available for this video yet — YouTube can take 30-60 minutes to generate them after upload. Try running the cascade again in a bit."

Do NOT proceed without a transcript. Stop here.

### Step 3 — Extract Video Metadata

Extract from the URL or yt-dlp output:
- **Video ID** — the 11-character ID
- **Video Title** — from Step 1 auto-detect, or fetch it:
```bash
yt-dlp --get-title "<youtube-url>"
```

### Step 3.5 — Classify Video Type

Based on the transcript content, classify the video as either **tutorial** or **discussion**.

**Tutorial signals** (generates guide + lead magnet LinkedIn post):
- Step-by-step instructions, processes, or workflows ("first... then... next...")
- How-to framing ("how to set up...", "how to build...", "let me show you...")
- Tool setup, configuration, installation, or code demos
- The viewer is expected to follow along or replicate something

**Discussion signals** (regular LinkedIn post only, NO guide):
- Opinions, predictions, reactions, or commentary ("I think...", "My take on...")
- Industry news, trend analysis, or comparisons
- Philosophical/strategic content without clear step-by-step actions

Tell the user which type was detected. If the user disagrees, let them override.

### Step 4 — Generate Blog Post

Read your blog system prompt:
```
Read file: ${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/blog-system-prompt.md
```

Then generate the blog post by following ALL the guidelines in that prompt. The transcript is your source material.

**Long-form visual requirement:** Every long-form article must include real visual assets, not placeholder prose. Generate or attach actual `.jpg`, `.jpeg`, or `.png` image files from a strong image model such as GPT Image, Higgsfield, Nous/FAL image generation, or another approved high-quality model. Use those files in the article with captions and alt text. Add relevant generated images, diagrams exported as image files, and source-video screenshots where they explain a workflow, tool UI, before/after result, architecture, or multi-step process. Do not leave the article as text-only unless the user explicitly asks for text-only.

**Explainer diagram style:** Default long-form article visuals to simple Anthropic-light explainer diagrams inspired by clean editorial references such as clawd.rip, without copying them. Use an off-white canvas, black/charcoal type, thin gray rules, warm clay/orange accents, simple boxes/arrows/pixel-style accents, lots of whitespace, and a clear left-to-right or top-to-bottom flow. Each image should visualize the adjacent text's core idea, not decorate it. Keep text inside images to 0-4 short labels, no paragraphs. If exact labels matter, create deterministic SVG/HTML/Canvas/Pillow diagrams and export them to real PNG files instead of asking an image model to render text. Size article images to the same max width as the text column and make them responsive (`width: 100%; max-width: var(--content-width); height: auto;`).

**Generate these fields:**
- `meta_title` — under 60 chars with primary keyword
- `meta_description` — 150-160 chars with keyword and CTA
- `primary_keyword` — main keyword from the content
- `secondary_keywords` — 3-5 related terms
- `slug` — lowercase-hyphenated, under 60 chars
- `excerpt` — 1-2 sentence summary for preview cards
- `tags` — 3-7 topic tags
- `cover_image` — always use the YouTube thumbnail: `https://i.ytimg.com/vi/VIDEO_ID_HERE/maxresdefault.jpg`
- `visual_assets` — 5-8 actual visual files for the article. Each asset must be a real `.jpg`, `.jpeg`, or `.png` file generated or captured before publishing. Prefer `generated_diagram_image` assets in the simple Anthropic-light explainer style above. Include the type (`generated_image`, `generated_diagram_image`, `chart_image`, or `video_screenshot`), model/source used (for example GPT Image, Higgsfield, Nous/FAL, or deterministic SVG/HTML/Pillow diagram renderer), local/public file path, exact placement after an H2/H3, alt text, caption, and source frame/timestamp when using a screenshot from the video.
- `content` — the full blog post in markdown (1,500-2,500 words)
- `review_notes` — what was cut from the transcript and any [STAT NEEDED] flags

**Show the user the generated blog post** for review before saving.

### Step 4.5 — Check for Existing Blog Post (Supabase users only)

If you have Supabase configured, check if a blog post already exists for this video:

```bash
curl -s "YOUR_SUPABASE_URL/rest/v1/posts?youtube_video_id=eq.VIDEO_ID_HERE&select=id" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

If a post exists, skip the insert and use the returned `id` as `post_id`.

### Step 5 — Save Blog (Supabase — optional)

If Supabase is configured, save the blog post via REST API. Write the JSON payload to a temp file first, then POST:

```bash
curl -s "YOUR_SUPABASE_URL/rest/v1/posts" \
  -X POST \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d @"/path/to/temp/blog-payload.json"
```

If Supabase is NOT configured, save the blog as a local markdown file instead.

### Step 6 — Generate Twitter Thread

Read the Twitter system prompt:
```
Read file: ${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/twitter-system-prompt.md
```

Generate a Twitter thread following ALL the guidelines. Use the transcript as source material. The thread should pick the single best angle from the video, not try to summarize everything.

**Show the thread to the user** before saving.

### Step 7 — Save Twitter Thread

Save to Supabase (if configured) or locally.

### Step 7.5 — Post Twitter Thread (Optional)

If the user wants to post and Twitter API is configured:

1. Write the thread to a temp file. Each tweet MUST start with `1/`, `2/`, etc.
2. Run:
```bash
node "${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/scripts/post-thread.js" "$TEMP/thread.txt" "https://youtu.be/VIDEO_ID_HERE"
```

### Step 8 — Generate LinkedIn Post (Regular)

Read the LinkedIn system prompt:
```
Read file: ${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/linkedin-system-prompt.md
```

Generate a LinkedIn post following ALL the guidelines. Mirror the video's full premise.

**Show the post to the user** before saving.

### Step 8b — Generate LinkedIn Lead Magnet Post (TUTORIAL VIDEOS ONLY)

**Skip this step entirely if the video was classified as "discussion" in Step 3.5.**

Read the lead magnet LinkedIn system prompt:
```
Read file: ${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/linkedin-lead-magnet-system-prompt.md
```

Generate a **lead magnet** LinkedIn post.

**Show the post to the user** labeled as **"LINKEDIN (LEAD MAGNET)"** so they can compare both versions.

### Step 8c — Generate Skool Guide as HTML (TUTORIAL VIDEOS ONLY)

**Skip this step entirely if the video was classified as "discussion" in Step 3.5.**

Read the guide system prompt:
```
Read file: ${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/prompts/guide-system-prompt.md
```

Generate a **Skool-ready guide** as HTML:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GUIDE_TITLE_HERE</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 40px 20px; line-height: 1.7; color: #1a1a1a; }
  h1 { font-size: 28px; margin-top: 40px; }
  h2 { font-size: 22px; margin-top: 36px; }
  h3 { font-size: 18px; margin-top: 28px; }
  a { color: #0066cc; }
  ul, ol { padding-left: 24px; }
  li { margin-bottom: 6px; }
  strong { font-weight: 600; }
  code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 14px; }
  pre { background: #f5f5f5; padding: 16px; border-radius: 6px; overflow-x: auto; }
  pre code { background: none; padding: 0; }
</style>
</head>
<body>
<!-- GUIDE CONTENT HERE -->
</body>
</html>
```

### Step 9 — Save to Vault / Local Files

Save a local copy of each generated piece in the video's working folder. This is the same per-video folder `/reels` and `/carousels` use (`<video>/`), so `/publish-pack` can find everything. If there is no video folder yet, make one named after the video's slug and tell the user.

- **Blog post** — `<video>/content/blog/YYYY-MM-DD-SLUG.md`
- **Article images** — `<video>/content/blog/images/`
- **Twitter thread** — `<video>/content/twitter/YYYY-MM-DD-SLUG.md`
- **LinkedIn (regular)** — `<video>/content/linkedin/YYYY-MM-DD-SLUG.md`
- **LinkedIn (lead magnet)** — `<video>/content/linkedin/YYYY-MM-DD-SLUG-lead-magnet.md` (tutorials only)
- **Skool guide (HTML)** — `<video>/content/guides/SLUG-guide.html` (tutorials only)

### Step 10 — Summary

Report what was created:
- Blog post title
- Twitter thread (number of tweets)
- LinkedIn post (regular version)
- Video type classification (tutorial or discussion)
- If tutorial: LinkedIn lead magnet + Skool guide
- Files saved
- Any issues or review notes

End by pointing at the next steps: `/carousels` turns the best ideas into slide posts, and `/publish-pack` puts every piece in `<video>/finished/` with captions per platform and a `PUBLISH PLAN.md` that says where and when to post each one.

## Autonomy Rules

**Ask before saving.** Show each piece of content to the user before saving. If the user says "just do everything", skip the review pauses.

**If the user only wants specific pieces** (e.g., "just the blog"), only generate those.

## Supabase REST API Config (Optional)

If you want auto-saving to a database, configure these:

- **Base URL:** `YOUR_SUPABASE_URL/rest/v1/`
- **Service Role Key:** Set `SUPABASE_SERVICE_ROLE_KEY` environment variable
- **Required headers for every request:**
  - `apikey: $SUPABASE_SERVICE_ROLE_KEY`
  - `Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY`
  - `Content-Type: application/json`
- **To get the response back after insert/update:** add header `Prefer: return=representation`

**Tables needed:**
- `posts` — blog posts (fields: id, title, slug, excerpt, content, cover_image, tags, published, published_at, youtube_video_id, meta_title, meta_description)
- `social_content` — twitter/linkedin content (fields: id, post_id, platform, content, status, published_at)

## Notes

- The blog prompt is the most critical — follow it exactly
- All content saves as drafts by default — only publish when the user explicitly says to
- If using Supabase, the `youtube_video_id` column on `posts` has a unique constraint — always check first (Step 4.5)
