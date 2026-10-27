# reels.json

Save the plan as `BASE/work/reels.json`. `BASE` is the video's working folder. Run the CLI from `BASE`. Keep source paths absolute so they resolve without guessing. The examples below use sample paths and timestamps; replace them with real media and word boundaries.

## Schema

Use these fields from the shared contract. Time values are seconds on the finished edit's timeline.

| Field | Type | Meaning |
|-------|------|---------|
| `source` | object | The long-form source |
| `source.edited` | string | Path to the finished edit with mastered audio |
| `source.raw_dir` | string | Folder of raw camera takes and matching `microphone.wav` files |
| `source.title` | string | Long-form title |
| `source.long_form_url` | string or null | Long-form URL, or `null` before upload |
| `reels` | array | 3-6 reel objects for a full plan |
| `reels[].id` | string | Stable reel ID, such as `R1` |
| `reels[].title` | string | Short internal title |
| `reels[].idea` | string | One idea the reel delivers |
| `reels[].segments` | array | Body ranges in playback order |
| `segments[].start`, `segments[].end` | number | Start and end in the edit; `0 <= start < end` |
| `segments[].note` | string | What the range covers |
| `reels[].hooks` | array | One footage hook and three film hooks |
| `hooks[].id` | string | Stable hook ID within the reel, such as `H1` |
| `hooks[].type` | string | `footage` or `film` |
| `hooks[].spoken` | string | Exact source line for footage; the line to record for film |
| `hooks[].range` | object | Footage only: `start` and `end` seconds in the edit |
| `hooks[].on_screen_text` | string | At most six words shown over the top for about 2.5 seconds |
| `hooks[].shot_note` | string | Film only: delivery, gesture, prop, and what is visible |
| `hooks[].framework` | string | Kallaway core/proxy desire and selected angle |
| `reels[].caption` | string | Post caption |
| `reels[].hashtags` | array of strings | Relevant hashtags |
| `reels[].cta` | string | Spoken or on-screen CTA back to the long-form or community |
| `reels[].est_duration` | number | Estimated reel duration in seconds, including the hook once |

Reel IDs must be unique. Hook IDs must be unique within each reel. Use filename-safe IDs. Snap ranges to real word boundaries and stay within the source duration. Film hooks must be at most 15 words and 4 seconds when spoken.

The renderer plays `[hook] + segments`. If the footage hook's range overlaps the first segment's start, it skips the extra hook insert so the body opens on that line once. Check this in playback.

Film hooks render only when `BASE/hooks-filmed/<reelId>-<hookId>.mov` or `.mp4` exists. Outputs are `BASE/out/<reelId>-<hookId>.mp4`. Each hook uses the same body. Keep the word transcript at `BASE/work/words.json` as a list of `{start,end,w}` objects in seconds. A Whisper token starting with a space begins a new word. Scores and edit notes belong in `repurpose-plan.md`, not new JSON fields.

## Example: One Reel

This shows one reel's shape. A full plan has 3-6 reels.

```json
{
  "source": {
    "edited": "/path/to/video/edited.mp4",
    "raw_dir": "/path/to/video/Raw Recordings",
    "title": "Claude skills I use every day",
    "long_form_url": null
  },
  "reels": [
    {
      "id": "R1",
      "title": "Save the repeated prompt",
      "idea": "Save a repeated Claude prompt as a skill.",
      "segments": [{"start": 43.82, "end": 78.2, "note": "Create and run the skill"}],
      "hooks": [
        {
          "id": "H1",
          "type": "footage",
          "spoken": "I save this prompt as a skill.",
          "range": {"start": 39.4, "end": 42.1},
          "on_screen_text": "Stop typing it again",
          "framework": "Time / reuse a prompt / personal experience"
        },
        {
          "id": "H2",
          "type": "film",
          "spoken": "Stop typing the same Claude prompt. Save it as a skill.",
          "on_screen_text": "One file, less typing",
          "shot_note": "Say it plainly. Point to the skill file above you.",
          "framework": "Time / reuse a prompt / contrarian"
        },
        {
          "id": "H3",
          "type": "film",
          "spoken": "This file tells Claude what to do every time.",
          "on_screen_text": "The prompt stays saved",
          "shot_note": "Show the saved skill and then run it.",
          "framework": "Time / reuse a prompt / curiosity gap"
        },
        {
          "id": "H4",
          "type": "film",
          "spoken": "Still pasting prompts into Claude? Save this one as a skill.",
          "on_screen_text": "Keep the useful prompt",
          "shot_note": "Look at the lens. Show the saved file as you finish.",
          "framework": "Time / reuse a prompt / call out the viewer"
        }
      ],
      "caption": "Save the prompt you keep using. Full walkthrough on the channel.",
      "hashtags": ["#claude", "#claudecode", "#ai", "#claudecodetips", "#aiautomation"],
      "cta": "Watch the full video for the rest of the workflow.",
      "est_duration": 38
    }
  ]
}
```

## CLI

From `BASE`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/film_list.py" --plan work/reels.json --out film-hooks.md
python3 "${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/make_reel.py" --plan work/reels.json --reel R1 --hook H1 --out out/R1-H1.mp4
python3 "${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/make_reel.py" --plan work/reels.json --all
python3 "${CLAUDE_PLUGIN_ROOT}/skills/reels/scripts/make_reel.py" --plan work/reels.json --all --debug
```

`--debug` writes an alignment `.align.json` and contact sheet `.jpg` next to each render. Optional renderer overrides: `--edited`, `--raw-dir`, `--hooks-dir`, `--panel-crop x,y,w,h`, and `--cam-center x` (0-1). Media and hook defaults come from the plan and `BASE`. The film-list tool lists only film hooks whose recordings are still missing.
