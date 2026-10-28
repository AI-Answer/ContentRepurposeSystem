#!/usr/bin/env python3
"""
Build the "finished products" folder for one video from a small manifest.

    python3 build_publish_pack.py <manifest.json> [--out DIR] [--force] [--dry-run]

What it does:
  - Makes <video>/finished/ with the numbered layout:
        1 YouTube long-form
        2 Reels - Instagram, TikTok, YouTube Shorts
        3 Hooks to film
        4 Carousels - Instagram, LinkedIn, TikTok
        5 Articles - blog, LinkedIn, Substack
        6 Text posts - X, LinkedIn, Threads, newsletter
        7 <lead magnet label>
  - Copies every piece in, named in posting order. On macOS it makes APFS
    clones (cp -c), which take no extra disk space. Otherwise it copies.
  - Writes a captions file per reel (and per carousel that has none), one
    section per platform. Captions given in the manifest are filled in;
    the rest are marked [CLAUDE: ...] for Claude to write.
  - Writes PUBLISH PLAN.md (what's here, where each piece goes, day by day,
    checklist) and README.md. Judgment parts are marked [CLAUDE: ...].

Re-running is safe. Copied files are refreshed when the source changed.
Written text files (captions, PUBLISH PLAN.md, README.md) are kept if they
already exist, so edits survive. Pass --force to rewrite them.

Manifest paths are relative to "video_dir" (default: the manifest's folder).
See ../examples/manifest.example.json for every field.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FOLDERS = {
    "long_form": "1 YouTube long-form",
    "reels": "2 Reels - Instagram, TikTok, YouTube Shorts",
    "hooks": "3 Hooks to film",
    "carousels": "4 Carousels - Instagram, LinkedIn, TikTok",
    "articles": "5 Articles - blog, LinkedIn, Substack",
    "text_posts": "6 Text posts - X, LinkedIn, Threads, newsletter",
    "lead_magnet": "7 {label}",
}
DEFAULT_LEAD_LABEL = "Lead magnet - community guide"

PLATFORM_ORDER = ["YouTube", "Shorts", "Instagram", "TikTok", "LinkedIn", "X",
                  "Threads", "Blog", "Substack", "Newsletter", "Community"]
ALIASES = {
    "youtube shorts": "Shorts", "shorts": "Shorts", "yt shorts": "Shorts",
    "instagram reels": "Instagram", "ig": "Instagram", "ig reels": "Instagram",
    "instagram": "Instagram", "tiktok": "TikTok", "tik tok": "TikTok",
    "linkedin": "LinkedIn", "x": "X", "twitter": "X", "threads": "Threads",
    "blog": "Blog", "website": "Blog", "substack": "Substack", "medium": "Substack",
    "newsletter": "Newsletter", "email": "Newsletter", "community": "Community",
    "skool": "Community", "youtube": "YouTube",
}
TEXT_EXT = {".md", ".html", ".htm", ".txt", ".pdf", ".docx"}
VIDEO_EXT = {".mp4", ".mov", ".m4v"}

LOG = []
WARN = []


def log(msg):
    LOG.append(msg)
    print(msg)


def warn(msg):
    WARN.append(msg)
    print(f"  ! {msg}")


# ---------------------------------------------------------------------------
# Copying
# ---------------------------------------------------------------------------
def _same(src, dst):
    if not dst.exists():
        return False
    a, b = src.stat(), dst.stat()
    return a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime)


def clone_file(src, dst, dry):
    """APFS clone with cp -c when possible, else a normal copy. Returns how."""
    if _same(src, dst):
        return "same"
    if dry:
        return "would copy"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    if sys.platform == "darwin" and shutil.which("cp"):
        r = subprocess.run(["cp", "-c", "-p", str(src), str(dst)], capture_output=True)
        if r.returncode == 0:
            return "cloned"
    shutil.copy2(src, dst)
    return "copied"


def clone_any(src, dst, dry):
    """Copy a file or a whole folder. Returns a count of files touched."""
    if src.is_dir():
        n = 0
        for f in sorted(src.rglob("*")):
            if f.is_file() and f.name != ".DS_Store":
                how = clone_file(f, dst / f.relative_to(src), dry)
                n += how != "same"
        return n
    return int(clone_file(src, dst, dry) != "same")


def write_text(path, text, force, dry):
    """Write a generated file unless it exists (then keep the user's edits)."""
    if path.exists() and not force:
        return "kept"
    if dry:
        return "would write"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return "written"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe(name):
    name = re.sub(r'[/\\:*?"<>|]', "-", str(name)).strip()
    return re.sub(r"\s+", " ", name) or "untitled"


def norm_platforms(items):
    out = []
    for p in items or []:
        key = str(p).strip()
        canon = ALIASES.get(key.lower(), key)
        if canon not in out:
            out.append(canon)
    return out


def guess_platforms(name, section):
    n = name.lower()
    found = []
    if section == "articles":
        if "linkedin" in n:
            found.append("LinkedIn")
        if "substack" in n or "medium" in n:
            found.append("Substack")
        return found or ["Blog"]
    rules = [(r"\bx\b|twitter|tweet", "X"), (r"linkedin", "LinkedIn"),
             (r"\bthreads\b", "Threads"), (r"newsletter|email", "Newsletter"),
             (r"community|skool|club|discord", "Community")]
    for pat, plat in rules:
        if re.search(pat, n):
            found.append(plat)
    return found


def fill(text_or_none, what):
    if text_or_none:
        return text_or_none.strip()
    return f"[CLAUDE: {what}]"


# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------
def reel_captions(n, reel):
    caps = reel.get("captions") or {}
    plats = reel["platforms"]
    head = f"{n} - {reel.get('id', '')} {reel['title']}".replace("  ", " ")
    meta = []
    if reel.get("length"):
        meta.append(f"Length: {reel['length']}")
    if reel.get("opens_on"):
        meta.append(f"Opens on: \"{reel['opens_on']}\"")
    out = [head]
    if meta:
        out.append(" · ".join(meta))
    out.append("")

    def get(*keys):
        for k in keys:
            if caps.get(k):
                return caps[k]
        return None

    if "Instagram" in plats:
        out += ["== Instagram Reels ==",
                fill(get("Instagram", "Instagram Reels"),
                     "hook line, 2-3 lines of value, CTA (comment keyword, full video, offer), 5-8 hashtags"),
                ""]
    if "TikTok" in plats:
        out += ["== TikTok ==",
                fill(get("TikTok"), "one or two short lines, CTA, 3-5 hashtags"), ""]
    if "Shorts" in plats:
        out += ["== YouTube Shorts ==",
                fill(get("YouTube Shorts", "Shorts"),
                     "Title: <short title> #shorts\nDescription: one line. Set the long-form as the related video."),
                ""]
    extra = [p for p in plats if p in ("LinkedIn", "X", "Threads")]
    if extra:
        out += [f"== {' / '.join(extra)} ==",
                fill(get(*extra, " / ".join(extra)),
                     "a longer, plain caption; put links in the first comment or a reply"),
                ""]
    hooks = reel.get("hooks_to_film") or []
    if hooks:
        out.append("== Hooks still to film for this reel (test them later) ==")
        out += [f"- {h}" for h in hooks]
        out.append("")
    return "\n".join(out)


def carousel_captions(c):
    caps = c.get("captions") or {}
    sections = []
    for plat, hint in [("Instagram", "hook, the core in a few short lines, CTA, 5-8 hashtags"),
                       ("LinkedIn", "open with the result, short story, point to the document above, link, end with a question"),
                       ("TikTok (photo mode)", "one or two lines, 3-5 hashtags")]:
        if plat.split()[0] in c["platforms"]:
            sections.append(f"== {plat} ==\n{fill(caps.get(plat) or caps.get(plat.split()[0]), hint)}\n")
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Plan and README
# ---------------------------------------------------------------------------
def day_label(start, day):
    if not start:
        return ""
    d = start + dt.timedelta(days=day)
    return d.strftime("%a %b %-d") if sys.platform != "win32" else d.strftime("%a %b %d")


def build_plan(m, pieces, made, missing_sections, out_dir):
    title = m["title"]
    start = None
    if m.get("start_date"):
        try:
            start = dt.date.fromisoformat(m["start_date"])
        except ValueError:
            warn(f"start_date '{m['start_date']}' is not YYYY-MM-DD; dates left out")

    L = [f"# {title}: what to publish, where, and when", "",
         "[CLAUDE: one or two lines. What is ready to post, and what still needs work (for example hooks to film).]",
         "", "## What's here", "", "| Folder | What | Publish on |", "|---|---|---|"]
    for key, folder in made:
        group = [p for p in pieces if p["section"] == key and p["platforms"]]
        plats = norm_platforms([pl for p in group for pl in p["platforms"]])
        what = {
            "long_form": "The edit + title ideas, description, chapters",
            "reels": f"{len(group)} vertical reels (1080x1920), each with a captions file",
            "hooks": "New hook lines to record. Not a post: they become extra reel versions",
            "carousels": f"{len(group)} carousels: slides, LinkedIn PDF, captions",
            "articles": "Blog article, images, cross-post versions",
            "text_posts": f"{len(group)} text pieces",
            "lead_magnet": "The guide people get from the CTA",
        }[key]
        where = ", ".join(f"**{p}**" for p in plats) if plats else "Not a post"
        L.append(f"| `{folder}/` | {what} | {where} |")

    # Matrix
    cols = [p for p in PLATFORM_ORDER if any(p in x["platforms"] for x in pieces)]
    cols += sorted({pl for x in pieces for pl in x["platforms"]} - set(cols))
    L += ["", "## Where each piece goes", "",
          "| # | Piece | " + " | ".join(cols) + " |",
          "|---|---|" + "---|" * len(cols)]
    for p in pieces:
        if not p["platforms"]:
            continue
        ticks = " | ".join("✅" if c in p["platforms"] else "" for c in cols)
        L.append(f"| {p['ref']} | {p['label']} | {ticks} |")
    L += ["", "Why that split:",
          "- [CLAUDE: which audience each platform reaches and why each piece goes there or not.]",
          "- [CLAUDE: which pieces are most technical and stay on fewer platforms.]"]

    # Calendar
    day0, queues = [], {"reels": [], "carousels": [], "other": []}
    fixed = {}
    for p in pieces:
        if not p["platforms"]:
            continue
        if p.get("day") is not None:
            fixed.setdefault(int(p["day"]), []).append(p)
        elif p["section"] in ("long_form", "lead_magnet"):
            day0.append(p)
        elif p["section"] == "articles" and "Blog" in p["platforms"]:
            day0.append(p)
        elif p["section"] == "text_posts" and set(p["platforms"]) & {"Newsletter", "Community"}:
            day0.append(p)
        elif p["section"] in ("reels", "carousels"):
            queues[p["section"]].append(p)
        else:
            queues["other"].append(p)
    days = {0: day0}
    n_days = max([len(q) for q in queues.values()] + [0])
    for i in range(n_days):
        for q in queues.values():
            if i < len(q):
                days.setdefault(i + 1, []).append(q[i])
    for d, ps in fixed.items():
        days.setdefault(d, []).extend(ps)

    L += ["", "## Day by day", "",
          "A first draft: day 0 is launch day, then one reel, one carousel and one text post a day. "
          "[CLAUDE: adjust to the creator's real cadence and best days.]", "",
          "| Day | Date | Post | Where |", "|---|---|---|---|"]
    for d in sorted(days):
        for p in days[d]:
            L.append(f"| Day {d} | {day_label(start, d)} | {p['label']} | {', '.join(p['platforms'])} |")

    links = m.get("links") or {}
    L += ["", "## Links to fill in", ""]
    L.append(f"- Long-form video: {links.get('video') or '[VIDEO LINK] (add once it is live, then search the folder for [VIDEO LINK])'}")
    L.append(f"- Offer / lead magnet: {links.get('offer') or '[OFFER LINK]'}")

    L += ["", "## Before you post: checklist", "",
          "- [ ] Every [VIDEO LINK], [OFFER LINK] and [CLAUDE: ...] placeholder is filled in",
          "- [ ] Lead magnet is live where the CTAs point"]
    if any(p["section"] == "long_form" for p in pieces):
        L.append("- [ ] YouTube title picked, chapters checked against the timeline, end screen and pinned comment set")
    if any(p["section"] == "reels" for p in pieces):
        L += ["- [ ] Each reel watched once with sound on a phone",
              "- [ ] Shorts linked to the long-form as related video"]
    if any(p["section"] == "carousels" for p in pieces):
        L.append("- [ ] Every carousel slide opened and checked; LinkedIn PDF uploaded as a document post")
    if any(p["section"] == "articles" for p in pieces):
        L.append("- [ ] Article placeholders (domain, video ID) filled; images uploaded with the post")
    L.append("- [ ] [CLAUDE: claims to double-check before posting, from the run's review notes]")

    if missing_sections or WARN:
        L += ["", "## Not made yet", ""]
        for s in missing_sections:
            L.append(f"- {s}")
        for w in WARN:
            L.append(f"- Missing file: {w}")
    L.append("")
    return "\n".join(L)


def build_readme(m, made, manifest_path):
    L = [f"# {m['title']}: finished products", "",
         "Everything for this video, ready to post. Start with **PUBLISH PLAN.md**: "
         "it says what goes where, and on which day.", "", "## Folders", ""]
    blurbs = {
        "long_form": "the main video, title ideas, description and chapters",
        "reels": "vertical reels in posting order, each with a captions file (one section per platform)",
        "hooks": "hook lines to film; they become extra versions of the reels",
        "carousels": "one folder per carousel: `slides/`, a LinkedIn PDF, `captions.txt`, `config.json`",
        "articles": "the blog article with its images, plus LinkedIn and Substack versions",
        "text_posts": "X, LinkedIn, Threads, newsletter and community posts",
        "lead_magnet": "the guide the CTAs point to",
    }
    for key, folder in made:
        L.append(f"- `{folder}/`: {blurbs[key]}")
    L += ["", "## Rebuild", "",
          "This folder was built by `/publish-pack`. To refresh the copies after a change:", "",
          "```bash",
          f'python3 "${{CLAUDE_PLUGIN_ROOT}}/skills/publish-pack/scripts/build_publish_pack.py" "{manifest_path}"',
          "```", "",
          "Captions files, PUBLISH PLAN.md and this README are kept as they are. "
          "Add `--force` to rewrite them from the manifest.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Build the finished products folder for one video.")
    ap.add_argument("manifest")
    ap.add_argument("--out", help="output folder (default: <video_dir>/finished)")
    ap.add_argument("--force", action="store_true", help="rewrite captions, plan and README")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen")
    args = ap.parse_args()

    mpath = Path(args.manifest).resolve()
    m = json.loads(mpath.read_text())
    if not m.get("title"):
        sys.exit("Manifest needs a \"title\".")
    base = Path(os.path.expanduser(m.get("video_dir") or mpath.parent))
    if not base.is_absolute():
        base = (mpath.parent / base).resolve()
    out = Path(args.out).resolve() if args.out else (base / (m.get("out") or "finished"))
    dry, force = args.dry_run, args.force

    def src_of(p):
        if not p:
            return None
        q = Path(os.path.expanduser(p))
        return q if q.is_absolute() else base / q

    lead = m.get("lead_magnet") or {}
    folders = dict(FOLDERS)
    folders["lead_magnet"] = FOLDERS["lead_magnet"].format(label=safe(lead.get("label") or DEFAULT_LEAD_LABEL))

    pieces, made, missing_sections = [], [], []
    log(f"Building {out}{'  (dry run)' if dry else ''}")

    def used(key):
        if (key, folders[key]) not in made:
            made.append((key, folders[key]))
        return out / folders[key]

    # 1 Long-form
    lf = m.get("long_form")
    if lf and (lf.get("file") or lf.get("notes")):
        d = used("long_form")
        if lf.get("file"):
            s = src_of(lf["file"])
            if s.exists():
                clone_any(s, d / f"{safe(m['title'])} - final{s.suffix}", dry)
            else:
                warn(f"long-form video {s}")
        notes = d / "YouTube title, description, chapters.md"
        if lf.get("notes") and src_of(lf["notes"]).exists():
            clone_any(src_of(lf["notes"]), notes, dry)
        else:
            if lf.get("notes"):
                warn(f"long-form notes {src_of(lf['notes'])}")
            length = f" ({lf['length']})" if lf.get("length") else ""
            skel = (f"# YouTube: {m['title']}{length}\n\n## Title ideas\n\n[CLAUDE: 3 options from /yt-titles]\n\n"
                    "## Description\n\n```\n[OFFER LINK] on line 1\n\n[CLAUDE: 2-3 lines about the video]\n\n"
                    "Chapters\n0:00 Intro\n[CLAUDE: chapters]\n\nResources\n[CLAUDE: every tool and link shown]\n```\n")
            write_text(notes, skel, force, dry)
        pieces.append({"section": "long_form", "ref": "0", "label": f"Long-form: {m['title']}",
                       "platforms": norm_platforms(lf.get("platforms") or ["YouTube"]), "day": lf.get("day")})
    else:
        missing_sections.append("YouTube long-form: add `long_form` to the manifest.")

    # 2 Reels
    reels = m.get("reels") or []
    if reels:
        d = used("reels")
        for n, r in enumerate(reels, 1):
            r = dict(r)
            r.setdefault("title", r.get("id", f"Reel {n}"))
            r["platforms"] = norm_platforms(r.get("platforms") or ["Shorts", "Instagram", "TikTok"])
            stem = safe(f"{n} - {r.get('id', '')} {r['title']}".replace("  ", " "))
            s = src_of(r.get("file"))
            r_missing = not (s and s.exists())
            if r_missing:
                warn(f"reel {r.get('id', n)} {s}")
            else:
                clone_any(s, d / f"{stem}{s.suffix}", dry)
            for v in r.get("variants") or []:
                vs = src_of(v)
                if vs.exists():
                    clone_any(vs, d / "hook variants" / vs.name, dry)
                else:
                    warn(f"reel variant {vs}")
            cap_src = src_of(r.get("captions_file"))
            cap_dst = d / f"{stem} - captions.txt"
            if cap_src and cap_src.exists():
                clone_any(cap_src, cap_dst, dry)
            else:
                write_text(cap_dst, reel_captions(n, r), force, dry)
            length = f" ({r['length']})" if r.get("length") else ""
            length += " (missing)" if r_missing else ""
            pieces.append({"section": "reels", "ref": str(n), "label": f"Reel {n}: {r.get('id', '')} {r['title']}{length}".replace("  ", " "),
                           "platforms": r["platforms"], "day": r.get("day")})
    else:
        missing_sections.append("Reels: run `/reels` on the finished edit.")

    # 3 Hooks to film
    hk = m.get("hooks_to_film")
    if hk:
        s = src_of(hk)
        if s.exists():
            clone_any(s, used("hooks") / s.name, dry)
            pieces.append({"section": "hooks", "ref": "-", "label": "Hooks to film", "platforms": []})
        else:
            warn(f"hooks to film {s}")

    # 4 Carousels
    cars = m.get("carousels") or []
    if cars:
        d = used("carousels")
        for n, c in enumerate(cars, 1):
            c = dict(c)
            s = src_of(c.get("dir"))
            title = c.get("title") or (s.name.split(" - ", 1)[-1] if s else f"Carousel {n}")
            c["platforms"] = norm_platforms(c.get("platforms") or ["Instagram", "LinkedIn", "TikTok"])
            dest = d / safe(f"{n} - {title}")
            if s and s.is_dir():
                clone_any(s, dest, dry)
                if not (s / "captions.txt").exists():
                    write_text(dest / "captions.txt", carousel_captions(c), force, dry)
                if not list(s.glob("slides/*.png")):
                    warn(f"carousel '{title}' has no slides/*.png yet (run /carousels)")
            else:
                warn(f"carousel folder {s}")
            pieces.append({"section": "carousels", "ref": f"C{n}", "label": f"Carousel {n}: {title}",
                           "platforms": c["platforms"], "day": c.get("day")})
    else:
        missing_sections.append("Carousels: run `/carousels`.")

    # 5 Articles, 6 Text posts, 7 Lead magnet (plain file lists)
    def file_section(key, items, ref_prefix, empty_msg, default_plats=None):
        if not items:
            missing_sections.append(empty_msg)
            return
        d = used(key)
        for n, it in enumerate(items, 1):
            s = src_of(it.get("src"))
            name = safe(it.get("name") or (s.name if s else f"item {n}"))
            missing = not (s and s.exists())
            if missing:
                warn(f"{key.replace('_', ' ')} {s}")
            else:
                clone_any(s, d / name, dry)
            is_piece = s is not None and not s.is_dir() and Path(name).suffix.lower() in TEXT_EXT
            if "platforms" in it:
                plats = norm_platforms(it["platforms"])
            elif default_plats is not None:
                plats = default_plats if n == 1 else []
            else:
                plats = guess_platforms(name, key) if is_piece else []
            pieces.append({"section": key, "ref": f"{ref_prefix}{n}",
                           "label": Path(name).stem + (" (missing)" if missing else ""),
                           "platforms": plats, "day": it.get("day")})

    file_section("articles", m.get("articles"), "A",
                 "Articles: run `/content-cascade` (blog post + images).")
    file_section("text_posts", m.get("text_posts"), "T",
                 "Text posts: run `/content-cascade` (X thread, LinkedIn, newsletter).")
    lead_items = lead.get("files") or []
    if lead_items:
        for it in lead_items:
            it.setdefault("platforms", [])
        lead_items[0]["platforms"] = norm_platforms(lead.get("platforms") or ["Community"])
    file_section("lead_magnet", lead_items, "L",
                 "Lead magnet: `/content-cascade` writes the guide for tutorial videos.")

    made.sort(key=lambda kv: folders[kv[0]])
    plan = build_plan(m, pieces, made, missing_sections, out)
    r1 = write_text(out / "PUBLISH PLAN.md", plan, force, dry)
    r2 = write_text(out / "README.md", build_readme(m, made, mpath), force, dry)

    print()
    print(f"Folders: {len(made)}  Pieces: {sum(1 for p in pieces if p['platforms'])}  "
          f"Missing files: {len(WARN)}")
    print(f"PUBLISH PLAN.md: {r1}   README.md: {r2}")
    if not dry:
        todo = 0
        for f in out.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".txt"):
                try:
                    todo += f.read_text().count("[CLAUDE:")
                except UnicodeDecodeError:
                    pass
        print(f"[CLAUDE: ...] placeholders left to fill: {todo}")
    sys.exit(1 if WARN else 0)


if __name__ == "__main__":
    main()
