---
name: carousels
description: "Turn the best ideas in a finished video into tweet-style or Pixel-Pal carousels for Instagram, LinkedIn, and TikTok photo mode. Writes the slides, picks real proof images, renders 1080x1350 PNG slides plus a LinkedIn PDF, and writes captions per platform. Trigger on 'make carousels from this video', 'turn this into a carousel', 'make an Instagram carousel', 'LinkedIn carousel', 'tweet-style slides', '/carousels', or any request to make carousel slides from a video, thread, or post."
---

# Carousels

Turn one finished video into 1-5 carousels. Each carousel carries one idea from the video. The slides look like posts on X: profile photo, name, badge, handle, then the text and an optional image.

## When This Skill Activates

**Activate when the user wants to:**
- Make Instagram, LinkedIn, or TikTok carousels from a finished video
- Turn a thread or post into slides
- Re-render a carousel after editing its text

**Example triggers:**
- "Make carousels from this video"
- "Turn the 2 prompts tip into a carousel"
- "Make a LinkedIn PDF carousel"
- `/carousels` or `/carousels <video folder, transcript, or YouTube URL>`

## Two styles

- **Tweet style (default).** Slides that look like posts on X, rendered locally by `render_carousel.py`. Exact text, real proof screenshots, free. Best for LinkedIn and for anything with a screenshot as proof.
- **Pixel-Pal.** An orange 8-bit pixel mascot, a dark serif hook slide, white teaching slides with numbered chips and tip boxes. Each slide is generated with GPT Image 2 on Higgsfield (`gpt_image_2`, aspect `3:4`, then cropped to 1080x1350). Best for Instagram and TikTok, where it stops the scroll. Use it when the user says "Pixel-Pal", "the pixel mascot style", or "make it with Higgsfield".

For Pixel-Pal, read [styles/pixel-pal/design-system.md](styles/pixel-pal/design-system.md) first. It holds the locked palette, the two slide types, the mascot spec, and the prompt template. Then:
1. Generate one mascot reference image and pass it as the reference on every slide, so the mascot stays the same.
2. Plan 6-8 slides: headline of 7 words or fewer, body of 2 short sentences or fewer. Put every string in quotes with "spelled exactly, verbatim", and ask for generous top and bottom margins (the 3:4 to 4:5 crop trims a little).
3. Keep 4 or fewer generations in flight. Download each result and crop it to 1080x1350.
4. Check every slide for spelling, the right orange word, the same mascot, and nothing cut off. Regenerate failures with the same prompt once, then with shorter copy.
5. Save into the carousel's folder under `pixel-pal/`, with `slides/`, a LinkedIn PDF, and `prompts.json`. The captions are shared with the tweet-style version.

The design system comes from [Samin12/pixel-pal-carousel](https://github.com/Samin12/pixel-pal-carousel).

## Input and Setup

Use whatever the video already has: the transcript, `repurpose-plan.md` from `/reels`, the posts from `/content-cascade`, and any proof screenshots. Use the creator's Voice DNA if it exists. Fetch a transcript the same way `/content-cascade` does if there is none.

**The renderer** is `${CLAUDE_PLUGIN_ROOT}/skills/carousels/scripts/render_carousel.py`. It needs Python 3 and Pillow (`python3 -m pip install Pillow`). `pilmoji` is optional and adds Apple emoji.

**The profile** (name, handle, verified badge, headshot path) comes from `/onboard`. It is saved in `${CLAUDE_PLUGIN_ROOT}/skills/carousels/profile.json`, which git ignores:

```json
{ "name": "Your Name", "handle": "@yourhandle", "verified": true, "headshot": "/path/to/your-headshot.png" }
```

If the file is missing, ask for the four values once and write it. Never guess a handle. Never copy the headshot into the plugin; store only its path. A `"profile"` block in a carousel config overrides the file field by field.

**Where files go.** Use the video's working folder (the same `BASE` that `/reels` uses). Each carousel gets its own numbered folder:

```text
<video>/carousels/
  1 - <short title>/
    config.json                  what the renderer reads
    ref/                         images the slides use
    slides/01.png, 02.png, ...   1080x1350 slides
    <short title> - LinkedIn.pdf one page per slide
    captions.txt                 Instagram, LinkedIn, TikTok sections
```

`/publish-pack` copies these folders into `finished/4 Carousels - Instagram, LinkedIn, TikTok/`.

## Steps

### Step 1: Pick the ideas

Pick 1-5 ideas that work without the video. Good picks:
- A list or a framework (the 10 tips, the 3 memory layers)
- Something to copy (exact prompts, commands, a checklist)
- A clear before and after, with proof

A reel and a carousel can share an idea. The reel shows it; the carousel lets people save it. Number the carousels in the order you would post them, widest appeal first.

### Step 2: Write the slides

Aim for 6-10 slides. Write them in the creator's voice.

- **Slide 1 is the hook.** It must work as a post on its own. Use a number, a list title ("Steal my 2 prompts"), a direct "you", or a known name. It always gets an image.
- **One idea per slide.** Arrow bullets (`→`) for lists. Order list items from shortest to longest.
- **Image slides get short text:** 1-3 short lines. Put the detail on the next slide.
- **Two short posts (under ~150 characters, no image) can share a slide.** A thin line separates them.
- **Quote prompts, commands, and numbers word for word** from the transcript or the source.
- **The last slide is the CTA:** save, follow, or comment, plus where the full video or offer lives.

Keep every claim backed. If the video says a number with no source, leave it out or soften it, and say so in your report. Do not make up proof to fill a slide.

### Step 3: Get the images

Prefer real things over generated art. Save every image in the carousel's `ref/` folder.

1. **A frame from the video** for the cover. Pick a moment that shows the idea:
   ```bash
   ffmpeg -ss 00:05:12 -i "<finished-edit.mp4>" -frames:v 1 -update 1 "ref/cover-frame.png"
   ```
2. **Proof screenshots:** docs pages, posts, repo headers, pricing pages, the creator's own screen. Crop to the part that proves the line on the slide. Text in a screenshot shrinks to about 85% of its width on the slide, so crop tight.
3. **Simple diagrams** for ideas with no screenshot. Draw them with Pillow or HTML in the Anthropic-light style used for articles: off-white canvas, charcoal text, thin gray lines, clay accents, 0-4 short labels.

Landscape or square images fit best. The renderer shrinks a tall image to fit, down to 55% width, and warns you.

### Step 4: Write config.json

See [examples/example-config.json](examples/example-config.json). Image paths can be relative to the config file.

```json
{
  "title": "Steal my 2 prompts",
  "theme": "light",
  "slides": [
    { "tweets": [ { "text": "Hook line.\n\nSecond line.", "image": "ref/cover-frame.png" } ] },
    { "tweets": [ { "text": "Short one.", "image": null }, { "text": "Short two.", "image": null } ] }
  ],
  "captions": {
    "Instagram": "...",
    "LinkedIn": "...",
    "TikTok (photo mode)": "..."
  }
}
```

- `theme`: `light` (white) or `dark` (black). Light is the default.
- `\n` breaks a line. `\n\n` starts a new paragraph.
- `captions` keys become the section names in `captions.txt`.

**Captions per platform:**
- **Instagram:** a hook line, the core of the carousel in a few short lines, the CTA, then 5-8 hashtags.
- **LinkedIn:** longer and more personal. Open with the result, tell the short story, point to "the document above", add the link, and end with a question. No hashtag wall.
- **TikTok (photo mode):** one or two lines and 3-5 hashtags.

### Step 5: Render and check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/carousels/scripts/render_carousel.py" \
  "<video>/carousels/1 - <short title>/config.json" "<video>/carousels/1 - <short title>"
```

Options: `--theme dark`, `--profile <file>`, `--no-pdf`, `--no-captions`.

The script prints one line per slide. It warns about text that runs off the slide, words wider than the slide, a lone word on a paragraph's last line, shrunk images, and a cover with no image. It exits with code 2 if anything would be cut off.

Then open every slide with Read and look at it. Check:
- Nothing is cut off, and no line has one leftover word
- Text inside screenshots can be read on a phone
- The cover image makes sense at a glance
- The name, badge, handle, and photo are right

Fix the config and render again until every slide passes. Open the PDF and check that it has one page per slide.

### Step 6: Report

List each carousel folder, its slide count, and its PDF. Note any claim you softened or left out, and any image you could not source. Keep everything as local drafts until the creator asks to publish.

**Next:** run `/publish-pack` to put the carousels in the finished folder with everything else.
