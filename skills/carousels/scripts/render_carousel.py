#!/usr/bin/env python3
"""
Render a tweet-style carousel from a config JSON.

In:  config.json (profile, theme, slides, optional title and captions)
Out: <out_dir>/slides/01.png, 02.png, ...   1080x1350 PNG slides
     <out_dir>/<title> - LinkedIn.pdf       one page per slide
     <out_dir>/captions.txt                 one section per platform
     <out_dir>/config.json                  a copy of the config, for re-renders

Usage:
    python3 render_carousel.py <config.json> <out_dir> [--profile profile.json]
        [--theme light|dark] [--no-pdf] [--no-captions]

Ported from the instagram-thread-carousel skill (thread-to-carousel.py, plus the
image checks from generate_carousel_image.py). GIF, video and image-generation
features were left out on purpose.

Profile lookup (first match wins, field by field):
    1. "profile" in the config
    2. --profile <file>
    3. $CAROUSEL_PROFILE (path to a JSON file)
    4. ../profile.json next to this script (written by /onboard, git-ignored)
A missing headshot draws a gray circle and prints a warning.

Relative image and headshot paths are resolved from the file they appear in.
"""

import argparse
import json
import os
import sys
from contextlib import nullcontext
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("Pillow is missing. Install it with: python3 -m pip install Pillow")

try:
    from pilmoji import Pilmoji
    from pilmoji.source import AppleEmojiSource
    HAS_PILMOJI = True
except ImportError:
    HAS_PILMOJI = False

# ---------------------------------------------------------------------------
# Layout (1080x1350, Instagram 4:5 portrait)
# ---------------------------------------------------------------------------
SLIDE_W = 1080
SLIDE_H = 1350

THEMES = {
    "light": {"bg": "#FFFFFF", "text": "#0F1419", "handle": "#536471",
              "verified": "#1D9BF0", "divider": "#CFD9DE", "placeholder": "#CCD6DD"},
    "dark": {"bg": "#000000", "text": "#E7E9EA", "handle": "#71767B",
             "verified": "#1D9BF0", "divider": "#2F3336", "placeholder": "#2F3336"},
}

PADDING_X = 80
PROFILE_SIZE = 80
NAME_SIZE = 34
HANDLE_SIZE = 34
TWEET_SIZE = 46
TWEET_LINE_HEIGHT = 1.50
NAME_HANDLE_GAP = 8
HEADER_TEXT_GAP = 28
TEXT_IMAGE_GAP = 40
TWEET_GAP = 60
IMAGE_RADIUS = 20
TOP_MARGIN = 60           # minimum space above and below the content
MIN_IMAGE_SCALE = 0.55    # images shrink to fit, but never below 55% width

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE = SCRIPT_DIR.parent / "profile.json"


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
def _load(candidates, size, variation=None):
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            font = ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
        if path.endswith("SFNS.ttf"):
            try:
                font.set_variation_by_name(variation or "Regular")
            except Exception:
                continue
        return font, path
    try:
        return ImageFont.truetype("Arial", size), "Arial"
    except (OSError, IOError):
        return ImageFont.load_default(size), "Pillow default"


def load_fonts():
    bold = [
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/SF-Pro-Display-Bold.otf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    regular = [
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/SF-Pro-Display-Regular.otf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    name_font, name_path = _load(bold, NAME_SIZE, "Bold")
    handle_font, _ = _load(regular, HANDLE_SIZE, "Regular")
    tweet_font, tweet_path = _load(regular, TWEET_SIZE, "Regular")
    print(f"  Fonts: {Path(name_path).name} (bold), {Path(tweet_path).name} (text)")
    return {"name_bold": name_font, "handle": handle_font, "tweet": tweet_font}


# ---------------------------------------------------------------------------
# Image checks (from generate_carousel_image.py)
# ---------------------------------------------------------------------------
def check_image(path):
    """Return an error string if the file is missing or not a real image."""
    p = Path(path)
    if not p.exists():
        return f"image not found: {path}"
    with open(p, "rb") as fh:
        header = fh.read(256)
    if b"<!DOCTYPE" in header or b"<html" in header or b"<HTML" in header:
        return f"'{path}' is an HTML page, not an image (the download probably failed)"
    if len(header) < 8:
        return f"'{path}' is too small to be an image"
    try:
        with Image.open(p) as im:
            im.verify()
    except Exception as exc:
        return f"'{path}' could not be opened as an image: {exc}"
    return None


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def make_circular(img, size):
    img = img.convert("RGBA")
    # center-crop to a square so non-square headshots are not squashed
    s = min(img.size)
    left, top = (img.width - s) // 2, (img.height - s) // 2
    img = img.crop((left, top, left + s, top + s)).resize((size, size), Image.LANCZOS)
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    bg.paste(img, (0, 0), img)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(bg, (0, 0), mask)
    return out


def draw_verified_badge(draw, x, y, color, size=28):
    draw.ellipse([x, y, x + size, y + size], fill=color)
    cx, cy = x + size / 2, y + size / 2
    r = size * 0.28
    points = [(cx - r * 0.9, cy + r * 0.05), (cx - r * 0.15, cy + r * 0.75),
              (cx + r * 1.0, cy - r * 0.7)]
    draw.line(points, fill="white", width=max(3, int(size * 0.13)))


def round_corners(img, radius):
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0], img.size[1]],
                                           radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def wrap_text(text, font, max_width, draw):
    """Word-wrap, keeping explicit newlines.
    Returns (lines, overlong_words, widows). A widow is a paragraph whose last
    line holds one short word; it reads badly on a slide."""
    lines, overlong, widows = [], [], []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
            continue
        start = len(lines)
        cur = ""
        for word in paragraph.split(" "):
            test = f"{cur} {word}" if cur else word
            if draw.textlength(test, font=font) <= max_width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                if draw.textlength(word, font=font) > max_width:
                    overlong.append(word)
                cur = word
        if cur:
            lines.append(cur)
        last = lines[-1].strip()
        is_link = "/" in last or "@" in last or "." in last.rstrip(".!?:,")
        if len(lines) - start > 1 and " " not in last and not is_link:
            widows.append(last)
    return lines, overlong, widows


def text_block_height(lines):
    line_h = int(TWEET_SIZE * TWEET_LINE_HEIGHT)
    return sum(int(line_h * 0.55) if line == "" else line_h for line in lines)


# ---------------------------------------------------------------------------
# Tweet layout
# ---------------------------------------------------------------------------
class Renderer:
    def __init__(self, profile, theme, fonts):
        self.p = profile
        self.t = theme
        self.f = fonts
        self.max_w = SLIDE_W - PADDING_X * 2
        self.headshot = None
        hs = profile.get("headshot")
        if hs and os.path.exists(hs) and not check_image(hs):
            self.headshot = make_circular(Image.open(hs), PROFILE_SIZE)

    def layout(self, tweet, draw, image_scale=1.0):
        """Measure one tweet. Returns dict with lines, image size and height."""
        lines, overlong, widows = wrap_text(tweet.get("text", ""), self.f["tweet"], self.max_w, draw)
        h = PROFILE_SIZE + HEADER_TEXT_GAP + text_block_height(lines)
        img_size = None
        img_path = tweet.get("image")
        if img_path:
            with Image.open(img_path) as im:
                aspect = im.height / im.width
            w = int(self.max_w * image_scale)
            img_size = (w, int(w * aspect))
            h += TEXT_IMAGE_GAP + img_size[1]
        return {"lines": lines, "overlong": overlong, "widows": widows, "img": img_size, "h": h}

    def draw_tweet(self, canvas, draw, tweet, lay, x, y):
        if self.headshot is not None:
            canvas.paste(self.headshot, (x, y), self.headshot)
        else:
            draw.ellipse([x, y, x + PROFILE_SIZE, y + PROFILE_SIZE], fill=self.t["placeholder"])

        nx = x + PROFILE_SIZE + 16
        ny = y + (PROFILE_SIZE - NAME_SIZE) // 2 - 4
        name = self.p.get("name") or "Your Name"
        draw.text((nx, ny), name, fill=self.t["text"], font=self.f["name_bold"])
        cursor = nx + draw.textlength(name, font=self.f["name_bold"]) + NAME_HANDLE_GAP
        if self.p.get("verified", False):
            draw_verified_badge(draw, cursor, ny + (NAME_SIZE - 28) // 2 + 2, self.t["verified"])
            cursor += 28 + NAME_HANDLE_GAP
        draw.text((cursor, ny), self.p.get("handle") or "@handle",
                  fill=self.t["handle"], font=self.f["handle"])

        ty = y + PROFILE_SIZE + HEADER_TEXT_GAP
        line_h = int(TWEET_SIZE * TWEET_LINE_HEIGHT)
        ctx = Pilmoji(canvas, source=AppleEmojiSource) if HAS_PILMOJI else nullcontext()
        with ctx as pm:
            for line in lay["lines"]:
                if line == "":
                    ty += int(line_h * 0.55)
                    continue
                if pm:
                    pm.text((x, ty), line, fill=self.t["text"], font=self.f["tweet"],
                            emoji_position_offset=(0, -6))
                else:
                    draw.text((x, ty), line, fill=self.t["text"], font=self.f["tweet"])
                ty += line_h

        if lay["img"]:
            ty += TEXT_IMAGE_GAP
            w, h = lay["img"]
            with Image.open(tweet["image"]) as im:
                pic = round_corners(im.convert("RGBA").resize((w, h), Image.LANCZOS), IMAGE_RADIUS)
            ix = x + (self.max_w - w) // 2
            canvas.paste(pic, (ix, ty), pic)
            ty += h
        return ty

    def render_slide(self, tweets, out_path):
        """Render 1 or 2 tweets. Returns a list of warnings."""
        warnings = []
        canvas = Image.new("RGB", (SLIDE_W, SLIDE_H), self.t["bg"])
        draw = ImageDraw.Draw(canvas)
        budget = SLIDE_H - TOP_MARGIN * 2

        # Shrink images until the slide fits (never below MIN_IMAGE_SCALE).
        scale = 1.0
        while True:
            lays = [self.layout(t, draw, scale) for t in tweets]
            total = sum(l["h"] for l in lays) + TWEET_GAP * (len(lays) - 1)
            has_img = any(l["img"] for l in lays)
            if total <= budget or not has_img or scale <= MIN_IMAGE_SCALE:
                break
            scale = max(MIN_IMAGE_SCALE, scale - 0.05)
        if scale < 1.0:
            warnings.append(f"image shrunk to {int(scale * 100)}% width to fit")
        if total > budget:
            warnings.append(f"content is {total - budget}px too tall and will be cut off; "
                            "shorten the text or split the slide")
        for l in lays:
            for word in l["overlong"]:
                warnings.append(f"word wider than the slide: '{word[:40]}'")
            for word in l["widows"]:
                warnings.append(f"one word alone on the last line: '{word}' (reword to fix)")

        y = max(TOP_MARGIN // 2, (SLIDE_H - total) // 2)
        for i, (tweet, lay) in enumerate(zip(tweets, lays)):
            end = self.draw_tweet(canvas, draw, tweet, lay, PADDING_X, y)
            if i < len(tweets) - 1:
                div_y = end + TWEET_GAP // 2
                draw.line([(PADDING_X, div_y), (SLIDE_W - PADDING_X, div_y)],
                          fill=self.t["divider"], width=2)
                y = end + TWEET_GAP
        canvas.save(out_path, "PNG")
        return warnings


# ---------------------------------------------------------------------------
# Config, profile, captions, PDF
# ---------------------------------------------------------------------------
def _resolve(path, base):
    if not path:
        return path
    p = Path(os.path.expanduser(path))
    return str(p if p.is_absolute() else (base / p).resolve())


def load_profile(config, config_dir, profile_arg):
    sources = []
    if profile_arg:
        sources.append(Path(profile_arg))
    if os.environ.get("CAROUSEL_PROFILE"):
        sources.append(Path(os.environ["CAROUSEL_PROFILE"]))
    sources.append(DEFAULT_PROFILE)

    profile = {}
    for src in reversed(sources):  # later sources lose to earlier ones
        if src.exists():
            data = json.loads(src.read_text())
            data = data.get("profile", data)
            if data.get("headshot"):
                data["headshot"] = _resolve(data["headshot"], src.parent)
            profile.update({k: v for k, v in data.items() if v not in (None, "")})
    cfg_profile = dict(config.get("profile") or {})
    if cfg_profile.get("headshot"):
        cfg_profile["headshot"] = _resolve(cfg_profile["headshot"], config_dir)
    profile.update({k: v for k, v in cfg_profile.items() if v not in (None, "")})
    profile.setdefault("verified", False)
    return profile


def write_captions(captions, out_dir):
    """captions: {"Instagram": "...", "LinkedIn": "...", "TikTok (photo mode)": "..."}"""
    parts = []
    for platform, text in captions.items():
        if isinstance(text, list):
            text = "\n".join(text)
        parts.append(f"== {platform} ==\n{text.strip()}\n")
    path = out_dir / "captions.txt"
    path.write_text("\n".join(parts))
    return path


def safe_name(title):
    bad = '/\\:*?"<>|'
    return "".join("-" if c in bad else c for c in title).strip() or "carousel"


def main():
    ap = argparse.ArgumentParser(description="Render a tweet-style carousel from a config JSON.")
    ap.add_argument("config")
    ap.add_argument("out_dir")
    ap.add_argument("--profile", help="JSON file with name, handle, verified, headshot")
    ap.add_argument("--theme", choices=sorted(THEMES), help="override the config theme")
    ap.add_argument("--no-pdf", action="store_true", help="skip the LinkedIn PDF")
    ap.add_argument("--no-captions", action="store_true", help="skip captions.txt")
    args = ap.parse_args()

    config_path = Path(args.config).resolve()
    config_dir = config_path.parent
    config = json.loads(config_path.read_text())
    out_dir = Path(args.out_dir).resolve()
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    theme_name = args.theme or config.get("theme", "light")
    if theme_name not in THEMES:
        print(f"  Warning: unknown theme '{theme_name}', using light")
        theme_name = "light"

    profile = load_profile(config, config_dir, args.profile)
    if not profile.get("name") or not profile.get("handle"):
        print("  Warning: profile name or handle is missing. Run /onboard or add "
              "\"profile\" to the config.")
    if not profile.get("headshot") or not os.path.exists(profile["headshot"]):
        print("  Warning: no headshot found; drawing a gray circle instead.")

    slides = config.get("slides") or []
    if not slides:
        sys.exit("Config has no slides.")

    # Resolve and check every image before drawing anything.
    errors = []
    for i, slide in enumerate(slides, 1):
        tweets = slide.get("tweets") or []
        if not 1 <= len(tweets) <= 2:
            errors.append(f"slide {i}: needs 1 or 2 tweets, has {len(tweets)}")
        for t in tweets:
            if t.get("image"):
                t["image"] = _resolve(t["image"], config_dir)
                err = check_image(t["image"])
                if err:
                    errors.append(f"slide {i}: {err}")
    if errors:
        sys.exit("Config problems:\n  " + "\n  ".join(errors))
    if not any(t.get("image") for t in slides[0]["tweets"]):
        print("  Note: slide 1 has no image. A strong first image stops the scroll.")

    renderer = Renderer(profile, THEMES[theme_name], load_fonts())
    for old in slides_dir.glob("[0-9][0-9].png"):
        old.unlink()  # drop slides from an earlier, longer render

    pages, all_ok = [], True
    for i, slide in enumerate(slides, 1):
        path = slides_dir / f"{i:02d}.png"
        warnings = renderer.render_slide(slide["tweets"], path)
        pages.append(path)
        status = "ok" if not warnings else "; ".join(warnings)
        if any("cut off" in w or "wider" in w for w in warnings):
            all_ok = False
        print(f"  [{i}/{len(slides)}] {path.relative_to(out_dir)}  {status}")

    title = config.get("title") or out_dir.name
    if not args.no_pdf:
        imgs = [Image.open(p).convert("RGB") for p in pages]
        pdf = out_dir / f"{safe_name(title)} - LinkedIn.pdf"
        imgs[0].save(pdf, save_all=True, append_images=imgs[1:], resolution=150)
        print(f"  PDF: {pdf.name} ({len(imgs)} pages)")

    if not args.no_captions:
        if config.get("captions"):
            print(f"  Captions: {write_captions(config['captions'], out_dir).name}")
        else:
            print("  Captions: none in config (add a \"captions\" object to write captions.txt)")

    dest_cfg = out_dir / "config.json"
    if dest_cfg.resolve() != config_path:
        # Keep a copy next to the slides. Images inside out_dir get relative
        # paths so the folder can move; others stay absolute.
        for slide in slides:
            for t in slide["tweets"]:
                img = t.get("image")
                if img and Path(img).resolve().is_relative_to(out_dir):
                    t["image"] = os.path.relpath(Path(img).resolve(), out_dir)
        dest_cfg.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")

    print(f"\nDone: {len(pages)} slides in {out_dir}")
    if not all_ok:
        print("Some slides overflow. Fix them before posting.")
        sys.exit(2)


if __name__ == "__main__":
    main()
