---
name: publish-pack
description: "Package every repurposed piece of one video into a numbered finished products folder with captions per platform, a PUBLISH PLAN.md (what's here, where each piece goes, day by day, checklist), and a README. Trigger on 'make the finished products folder', 'package everything to publish', 'where should I post what', 'make the publish plan', 'what do I post when', '/publish-pack', or the end of a /content-cascade, /reels, or /carousels run."
---

# Publish Pack

Put everything made from one video into one folder the creator can post from. Each piece gets its captions, and one plan says where it goes and on which day.

## When This Skill Activates

**Activate when the user wants to:**
- Collect the outputs of `/reels`, `/carousels`, and `/content-cascade` in one place
- Know where to post each piece, and when
- Refresh the folder after a re-render or an edit

**Example triggers:**
- "Make the finished products folder"
- "Package everything to publish"
- "Where should I post what?"
- `/publish-pack` or `/publish-pack <video folder>`

## The Folder

The pack lives in `<video>/finished/`. `<video>` is the video's working folder, the same `BASE` that `/reels` uses.

```text
<video>/finished/
  README.md
  PUBLISH PLAN.md
  1 YouTube long-form/                         <title> - final.mp4, YouTube title, description, chapters.md
  2 Reels - Instagram, TikTok, YouTube Shorts/ 1 - R1 <title>.mp4 + 1 - R1 <title> - captions.txt, ...
                                               hook variants/ (other hook versions, for testing)
  3 Hooks to film/                             film-hooks.md
  4 Carousels - Instagram, LinkedIn, TikTok/   1 - <title>/ slides/, <title> - LinkedIn.pdf, captions.txt, config.json
  5 Articles - blog, LinkedIn, Substack/       article.md, article.html, images/, LinkedIn article.md, ...
  6 Text posts - X, LinkedIn, Threads, newsletter/  X thread.md, LinkedIn post - story.md, Newsletter email.md, ...
  7 <lead magnet label>/                       the guide (HTML and PDF), how to post it
```

Numbers inside a folder are the posting order. Empty sections are left out and listed under "Not made yet" in the plan.

Where the other skills save, inside `<video>/`:

| Skill | Saves to |
|---|---|
| `/reels` | `out/`, `film-hooks.md`, `work/reels.json`, `repurpose-plan.md` |
| `/carousels` | `carousels/<n> - <title>/` |
| `/content-cascade` | `content/blog/`, `content/twitter/`, `content/linkedin/`, `content/guides/` |

## Steps

### Step 1: Find every piece

Find the video folder. Ask if it isn't clear. List what exists: the final edit, reels in `out/`, `film-hooks.md`, carousel folders, and everything under `content/`. Read `work/reels.json` and `repurpose-plan.md` for reel titles, lengths, captions, hashtags, and CTAs. Read the `/content-cascade` review notes for claims to check.

If a whole section is missing, say which skill makes it. Don't block on it; the plan lists it under "Not made yet".

### Step 2: Decide the order and the platforms

**Order:** widest appeal first. The idea anyone can use goes before the most technical one.

**Platforms.** Start from these defaults, then use judgment:
- **Reels:** YouTube Shorts, Instagram Reels, and TikTok get every reel, same file, same day.
- **LinkedIn video:** only the "work smarter" reels that land with business people.
- **X video:** reels with hard numbers or a dev angle.
- **The most technical reel** stays on the short-form apps, where a comment keyword CTA does the work.
- **Carousels:** Instagram, LinkedIn (as a PDF document post), and TikTok photo mode.
- **Articles:** the blog first. The LinkedIn article and Substack or Medium a few days later, with a canonical link back.
- **Text posts:** X thread, LinkedIn posts, Threads, the newsletter, and the community post, each on its own platform.
- **Lead magnet:** the community or the page the CTAs point to. It must be live on day 0.

### Step 3: Write the manifest

Save it as `<video>/publish-pack.json`. See [examples/manifest.example.json](examples/manifest.example.json) for every field. Paths are relative to `video_dir`.

- `title`, `start_date` (day 0, `YYYY-MM-DD`, optional), `links.video`, `links.offer`
- `long_form`: `file`, `notes` (the title, description, chapters file), `length`
- `reels[]`: `id`, `title`, `file`, `length`, `opens_on`, `platforms`, `variants`, `hooks_to_film`, `captions` (per platform), or `captions_file`
- `hooks_to_film`: path to `film-hooks.md`
- `carousels[]`: `title`, `dir` (a `/carousels` output folder)
- `articles[]`, `text_posts[]`: `src` (file or folder), `name` (name in the pack), `platforms` (optional; guessed from the name)
- `lead_magnet`: `label` (folder 7's name, e.g. "Claude Club - Opus 5.5 playbook"), `platforms`, `files[]`
- Any piece can set `"day": N` to pin it to a day in the calendar.

Put the captions you already have (from `reels.json` or `/short-form`) into the manifest. The script fills the rest with `[CLAUDE: ...]` markers.

### Step 4: Build the folder

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/publish-pack/scripts/build_publish_pack.py" "<video>/publish-pack.json"
```

Options: `--out <dir>` for another location, `--dry-run` to preview, `--force` to rewrite captions, the plan, and the README.

The script:
- Copies every piece in with its posting-order name. On macOS it makes APFS clones (`cp -c`), so big videos take no extra space. Elsewhere it copies.
- Writes a captions file per reel, and per carousel that has none. Each has one section per platform: `== Instagram Reels ==`, `== TikTok ==`, `== YouTube Shorts ==`, then LinkedIn or X if the reel goes there, then the hooks still to film.
- Writes `PUBLISH PLAN.md` and `README.md`.
- Prints missing files and how many `[CLAUDE: ...]` markers are left. It exits with code 1 if a file was missing.

Re-running is safe. Copies refresh when the source changed. Captions, the plan, and the README are kept, so your edits survive.

### Step 5: Fill the judgment parts

Replace every `[CLAUDE: ...]` marker. Write in the creator's Voice DNA.

- **Captions per platform.**
  - **Instagram:** a hook line, 2-3 lines of value, then the CTA (comment keyword, full video, offer), then 5-8 hashtags.
  - **TikTok:** one or two lines and 3-5 hashtags.
  - **YouTube Shorts:** a title with `#shorts` and a one-line description. Set the long-form as the Short's related video.
  - **LinkedIn and X:** a longer, plain version, with the link in the first comment or a reply.
- **YouTube notes** (if the script wrote a skeleton): title ideas from `/yt-titles`, the description with the offer link on line 1, chapters, and resources.
- **PUBLISH PLAN.md:**
  - **The opening lines:** what is ready, and what still needs work.
  - **Why that split:** one line per platform choice.
  - **Day by day:** the script's draft is day 0 for launch, then one reel, one carousel, and one text post a day. Adjust it to the creator's cadence.
  - **Hook testing:** if hooks are left to film, add how to test them, for example Instagram trial reels first, then the winner on TikTok and Shorts.
  - **Checklist:** add the claims to double-check from the review notes.

Then confirm none are left:

```bash
grep -rn "\[CLAUDE:" "<video>/finished" || echo "all filled"
```

Leave `[VIDEO LINK]` and other link placeholders in place until the video is live. List them in the report.

### Step 6: Report

Give the folder path, a one-line summary per numbered folder, the publish matrix, the first three days of the calendar, missing pieces, and open placeholders. Nothing is posted. Everything stays local until the creator asks to publish.

## Notes

- One video, one pack. Run it again after any re-render to refresh the copies.
- Keep the creator's own edits. Use `--force` only when they ask to rebuild the captions or the plan from scratch.
