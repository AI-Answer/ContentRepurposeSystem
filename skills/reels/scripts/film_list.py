#!/usr/bin/env python3
"""
film_list.py - teleprompter list of the filmed hooks still to record.

Reads a reels plan (see CONTRACT.md) and writes a Markdown checklist of every
``type: "film"`` hook that has no clip yet in the hooks folder
(``<reelId>-<hookId>.mov`` / ``.mp4``). Each entry shows the line to say in
large type, the on-screen text, delivery notes and the exact filename to save
the take as, so recording is a straight read-through.

Usage::

    python3 tools/film_list.py --plan work/reels.json --out film-hooks.md
    python3 tools/film_list.py --plan work/reels.json --all     # include recorded ones (ticked)

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional

CLIP_EXTS = (".mov", ".mp4", ".m4v", ".MOV", ".MP4")
WORDS_PER_SECOND = 2.8   # brisk hook delivery


def recorded_clip(hooks_dir: Path, reel_id: str, hook_id: str) -> Optional[Path]:
    for ext in CLIP_EXTS:
        p = hooks_dir / f"{reel_id}-{hook_id}{ext}"
        if p.exists():
            return p
    return None


def hook_entry(reel: dict, hook: dict, clip: Optional[Path]) -> str:
    spoken = (hook.get("spoken") or "").strip()
    n_words = len(spoken.split())
    secs = n_words / WORDS_PER_SECOND if n_words else 0
    box = "x" if clip else " "
    lines = [
        f"### [{box}] {reel['id']}-{hook['id']}  ·  {reel.get('title', '')}",
        "",
        f"## {spoken or '(no line written yet)'}",
        "",
        f"- **On screen:** {hook.get('on_screen_text', '')}",
    ]
    if hook.get("shot_note"):
        lines.append(f"- **Delivery:** {hook['shot_note']}")
    if hook.get("framework"):
        lines.append(f"- **Why it works:** {hook['framework']}")
    if reel.get("idea"):
        lines.append(f"- **Reel idea:** {reel['idea']}")
    flags = []
    if n_words > 15:
        flags.append(f"{n_words} words (aim for 15 or fewer)")
    if secs > 4:
        flags.append(f"~{secs:.1f}s (aim for 4s or less)")
    lines.append(f"- **Length:** {n_words} words, ~{secs:.1f}s" + (f"  (!) {'; '.join(flags)}" if flags else ""))
    lines.append(f"- **Save as:** `hooks-filmed/{reel['id']}-{hook['id']}.mov`"
                 + (f"  (recorded: `{clip.name}`)" if clip else ""))
    lines.append("")
    return "\n".join(lines)


def build(plan: dict, hooks_dir: Path, include_done: bool) -> tuple[str, int, int]:
    todo, done, parts = 0, 0, []
    for reel in plan.get("reels", []):
        for hook in reel.get("hooks", []):
            if hook.get("type") != "film":
                continue
            clip = recorded_clip(hooks_dir, reel["id"], hook["id"])
            if clip:
                done += 1
                if not include_done:
                    continue
            else:
                todo += 1
            parts.append(hook_entry(reel, hook, clip))

    title = plan.get("source", {}).get("title") or "reels"
    head = [
        f"# Hooks to film: {title}",
        "",
        f"{todo} to record" + (f", {done} already recorded" if done else "") + ".",
        "",
        "How to record: same camera setup as the long-form, look into the lens, one clean take per line "
        "with a beat of silence before and after (the reel tool trims the dead air). Say the line exactly "
        "as written; the on-screen text is added automatically. Save each take under the name shown.",
        "",
        "---",
        "",
    ]
    if not parts:
        head.append("Nothing left to film." if done else "This plan has no film hooks.")
    return "\n".join(head + parts) + "\n", todo, done


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Write a teleprompter list of film hooks not yet recorded.")
    ap.add_argument("--plan", required=True, help="reels.json")
    ap.add_argument("--out", help="Markdown file to write (default: print to stdout)")
    ap.add_argument("--hooks-dir", help="folder of recorded hooks (default: <BASE>/hooks-filmed)")
    ap.add_argument("--all", action="store_true", help="also list hooks already recorded (ticked)")
    args = ap.parse_args(argv)

    plan_path = Path(args.plan).expanduser().resolve()
    plan = json.loads(plan_path.read_text())
    # <BASE>/work/reels.json -> <BASE>; a plan anywhere else -> its own folder
    BASE = plan_path.parent.parent if plan_path.parent.name == "work" else plan_path.parent
    hooks_dir = Path(os.path.expanduser(args.hooks_dir)) if args.hooks_dir else BASE / "hooks-filmed"
    if not hooks_dir.is_absolute():
        hooks_dir = BASE / hooks_dir
    md, todo, done = build(plan, hooks_dir, args.all)
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.write_text(md)
        print(f"wrote {out}: {todo} to film, {done} recorded")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
