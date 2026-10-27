---
name: reels
description: "Turn a finished long-form video into vertical reels and tell the creator exactly which hooks to film. Plan 3-6 reels, score three filmed hook options per reel with the Kallaway framework, attach recorded hooks, and render variants of the same body. Trigger on 'make reels from this video', 'what hooks should I film', 'attach my filmed hooks', '/reels', or requests to plan, film, and render reels from a finished video."
---

# Reels

Turn one finished video into 3-6 reels. Each reel has one hook from the video and three new hooks to film. Keep the body the same so the creator can compare hooks.

## When This Skill Activates

**Activate when the user wants to:**
- Make reels from a finished local video or YouTube URL
- Get a short list of hooks to record
- Attach filmed hooks to an existing plan
- Render vertical reels with different openings

**Example triggers:**
- "Make reels from this video"
- "What hooks should I film?"
- "Attach my filmed hooks"
- `/reels` or `/reels <video path or YouTube URL>`

## Input and Setup

Use the finished edit, its transcript, and the raw camera takes with their matching `microphone.wav` files. Use the creator's Voice DNA if it exists. For a local file, channel onboarding is optional.

Use one working folder per video. Run the commands below from that folder, called `BASE`. Keep these files there:

```text
work/words.json       Word timestamps from the finished edit
work/reels.json       Reel bodies and hook variants
repurpose-plan.md     Ideas, exact excerpts, scores, and edit notes
film-hooks.md         Lines the creator still needs to film
hooks-filmed/         R1-H2.mov, R1-H3.mov, ...
out/                 R1-H1.mp4, R1-H2.mp4, ...
```

Check for `ffmpeg`, `ffprobe`, `whisper-cli`, Python 3, NumPy, and Pillow. Setup commands are in the plugin README. Whisper also needs a local model file. Read `whisper-cli --help` for the installed version's word timestamp options.

The renderer and film-list tool live at `${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/`. Check that both scripts exist before running them. If they are missing, report that rendering is unavailable. Keep the plan and filming list useful without claiming a render was made.

## Three-Step Loop

### Step 1: Plan

**Get the transcript and word timestamps.** All ranges must use the finished edit's timeline, in seconds.

For a YouTube URL, use the existing transcript helpers in order:

```bash
node "${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/scripts/fetch-transcript-apify.js" "<youtube-url>"
node "${CLAUDE_PLUGIN_ROOT}/skills/content-cascade/scripts/fetch-transcript.js" "<youtube-url>"
```

Use the second helper if the first fails. Check the opening lines against the title and the actual video. These helpers return plain text. They help find ideas but do not supply word timestamps.

Get timed captions with the `yt-dlp` subtitle fallback in `${CLAUDE_PLUGIN_ROOT}/skills/short-form/SKILL.md`. Keep the JSON3 timing data. Use real word offsets if the track has them. Do not divide a caption line into guessed word times.

For a local file, or if the URL's captions lack word timing, transcribe the finished edit with `whisper-cli`. For a URL, use the creator's matching local edit or download the video with `yt-dlp` first. Confirm that the media and transcript are the same cut.

```bash
mkdir -p work hooks-filmed out
ffmpeg -i "<finished-edit.mp4>" -vn -ar 16000 -ac 1 -c:a pcm_s16le work/edited-audio.wav
whisper-cli -m "<local-whisper-model.bin>" -f work/edited-audio.wav -ojf -sow -ml 1 -of work/whisper
```

Use full JSON and word splitting supported by the installed CLI. Normalize the timed word tokens into `work/words.json`: a list of `{"start": 0.12, "end": 0.34, "w": " word"}`. Convert millisecond offsets to seconds where needed. In Whisper tokens, a leading space begins a new word; join subword tokens before snapping cuts. Omit special tokens. Listen at sample timestamps to check timing. Never estimate edit ranges from reading speed. If word timing is still missing, report it and stop before rendering.

**Pick 3-6 ideas.** Read `${CLAUDE_PLUGIN_ROOT}/skills/short-form/SKILL.md` and apply its clip rules:
- One idea with a payoff that stands on its own
- Aim for 30-90 seconds including the hook
- Prefer a clear demo, useful quote, emotional peak, surprising result, or supported contrarian point
- Use the 70+ shock target where the source supports it; do not invent claims to raise a score
- Skip setup without payoff, references to earlier sections, transitions, and demos that cannot be read in the top panel
- Rank the choices for reach, conversions, and engagement

Use exact footage, not a rewritten body that was never recorded. Put body segments in playback order and snap cuts to word boundaries. Keep enough context for each idea to make sense.

**Write four hook options per reel.** Use stable IDs: `R1`, `R2`, and so on; `H1` for footage and `H2`-`H4` for film hooks.

- **One footage hook:** an exact line already in the finished edit, with its source range.
- **Three film hooks:** each at most 15 words and at most 4 seconds when spoken. Read each aloud and shorten it if needed. Pick three distinct angles from [hook-angles.md](references/hook-angles.md).
- Give each hook an `on_screen_text` of at most six words. For film hooks, add a `shot_note` with delivery and what the viewer sees.

Read `${CLAUDE_PLUGIN_ROOT}/skills/hooks/SKILL.md`. Apply its Kallaway framework to every film hook:

1. Map a core desire (Money, Time, Health, or Status) to a concrete proxy desire.
2. Draft the five desire-based variations, then select three short film hooks with different angles.
3. Align the visual, spoken line, and text overlay around the same promise.
4. Score the six power words: subject, action, objective, contrast, optional proof, optional time. Show the count out of six.
5. Score the Four Commandments: Alignment, Speed to Value, Clarity, and Curiosity. Show pass/fail for each. Recommend only hooks that pass all four. Proof and time are optional; never make them up for a higher score.

Keep scores and the five draft variations in `repurpose-plan.md`. Put the desire and angle in each hook's `framework` string. Do not add score fields to the shared JSON contract.

**Save the plan.** Follow [reels-json.md](references/reels-json.md) for the schema and example. Write `work/reels.json` with the source, exact segments, four hooks per reel, caption, hashtags, CTA, and estimated duration. Include the hook once when estimating duration. Use `null` for a missing long-form URL.

Write `repurpose-plan.md` with the ranked ideas, source ranges, exact excerpts, hook scores, first-frame visuals, layout notes, and any missing media. Use a CTA back to the long-form video or the creator's community after delivering the payoff. For Samin, that can be Claude Club.

Generate the teleprompter list:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/film_list.py" --plan work/reels.json --out film-hooks.md
```

It lists film hooks that do not yet exist in `hooks-filmed/`. If the script is missing, write the same list by hand and say why. Include reel/hook ID, exact line, overlay, shot note, and target filename. Tell the creator which lines to film first and why.

### Step 2: Film

The creator records each film hook and saves it as:

```text
hooks-filmed/<reelId>-<hookId>.mov
```

`.mp4` also works. For example, `hooks-filmed/R1-H2.mov`. Keep one file per hook ID.

**Batch-filming tips:**
- Use the same outfit and light as the long-form video.
- Record one take per line. Keep the spoken line at most 4 seconds and 15 words.
- Leave a 1 second pause before and after the line. The pauses are outside the spoken hook's time limit.
- Use the `shot_note` for energy, gesture, props, and framing. Leave room for the captions at the seam.

When asked to attach filmed hooks, read the existing plan. Match files to its reel and hook IDs. Check playback, audio, spoken words, and duration. If a filename is unclear, ask which line it belongs to. Keep the body and IDs stable. Run `film_list.py` again to show what is still missing. Missing film hooks do not block the footage variant.

### Step 3: Render and QA

Render every reel with every hook that exists:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/make_reel.py" --plan work/reels.json --all
```

Footage hooks render from the edit. Film hooks render only when a matching file exists. With all three film hooks recorded, each reel has four variants of the same body. Missing hooks stay on the filming list.

For a single variant and debug output:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/make_reel.py" --plan work/reels.json --reel R1 --hook H1 --out out/R1-H1.mp4 --debug
```

`--debug` also writes `out/R1-H1.align.json` and a contact sheet `.jpg`. Use `--all --debug` when reviewing the full batch. Other supported overrides are `--edited`, `--raw-dir`, and `--hooks-dir`.

**Check every rendered variant:**
- Inspect its contact sheet for crop, readable proof, camera framing, hook text, and captions at the seam.
- Play the whole reel with sound. Match captions to audio, check lip sync across jump cuts, and check the hook-to-body cut. A contact sheet alone cannot prove sync.
- Check captions on filmed hooks too. The transcript of the finished edit does not cover new recordings.
- Measure integrated loudness with FFmpeg's `ebur128` or `loudnorm` analysis. Target -14 LUFS. Listen for clipping and a volume jump between the filmed hook and body.
- Confirm 1080x1920, 30 fps, H.264 video, and AAC audio with `ffprobe`. Check the actual duration and that the opening hook was not repeated.
- Read alignment logs. Record each low-confidence window and review its fallback camera tile in playback.

Report render paths, missing hook files, fallback windows, and any failed checks. Keep outputs as local drafts until the creator asks to publish.

## Layout Defaults and Other Videos

The default is Samin's Borumi layout in a 1920x1080 edit:

| Part | Default |
|------|---------|
| Output | 9:16, 1080x1920, 30 fps, H.264 + AAC, -14 LUFS |
| Top | About 1080x810; the edited visuals panel, scaled to fit the width |
| Bottom | About 1080x1110; face and upper body from the raw 4K camera |
| Captions | 2-4 words, bold white with dark stroke; current word in orange `#E8774A` |
| Caption position | On the seam, around y 790-900 |
| Hook text | Over the top of the frame for roughly the first 2.5 seconds |
| Audio | Mastered edit audio for footage; the filmed hook's own audio, loudness-matched |

The source visuals panel is about x 20-1494, y 20-1060. The small camera tile is about x 1530-1884, y 230-850. Use the raw camera for the bottom panel when alignment succeeds.

For a different source layout, inspect a frame before rendering. Set `--panel-crop x,y,w,h` in source pixels to select the visuals. Set `--cam-center x` from 0 to 1 to choose the horizontal center of the raw camera crop. `0.5` is the middle. For example, this explicitly selects the default Borumi panel:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/make_reel.py" --plan work/reels.json --all --panel-crop 20,20,1474,1040 --cam-center 0.5
```

For other videos, replace those values after checking the source. Keep UI text and the creator's face in frame. These flags adjust the source crops; the output keeps the same top/bottom layout. Check fallback windows closely if the source camera tile is elsewhere.

## Raw-Camera Alignment

The edited video's mastered audio is the reference. The tool cross-correlates it against each take's raw `microphone.wav` to find the matching camera time. Camera and mic from the same take must share a timeline.

Alignment happens per window so jump cuts inside one segment can switch to the right raw camera time. A single offset for the whole reel is not enough. If confidence is low, use the edited video's camera tile for that window only, scale it into the bottom panel, and log the fallback. Tell the creator about the lower-quality windows. Do not call the raw camera synced until playback confirms it.
