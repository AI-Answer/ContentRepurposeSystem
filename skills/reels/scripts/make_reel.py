#!/usr/bin/env python3
"""
make_reel.py - turn ranges of an edited long-form video into 9:16 reels.

Each reel is ``[hook] + segments`` (see ``CONTRACT.md`` for the plan schema).
The frame is split in two:

* TOP (1080x810): the visuals/proof panel, cropped from the edited 16:9 video.
* BOTTOM (1080x1110): the speaker, cropped from the *raw* camera file of the
  take, so the face is sharp instead of an upscaled picture-in-picture tile.

Lip sync comes from audio: the edited video's (mastered) audio is
cross-correlated against every raw ``* - microphone.wav`` (camera and mic of a
take share a timeline). This is done in short overlapping windows so jump cuts
inside a segment are found, then a small dynamic program assigns every 0.1 s
block of the segment to one constant-offset "run" (or to a fallback that uses
the edited video's own camera tile, when nothing matches well).

Captions are burned in from the edited video's word timings (2-4 word chunks,
current word in the accent colour) and the hook's ``on_screen_text`` is shown
over the top for the first ~2.5 s. Filmed hooks (``hooks-filmed/<reel>-<hook>.*``)
get a generated title card on top and their own camera at the bottom.

Requirements: Python 3.9+, numpy, Pillow, and ffmpeg/ffprobe on PATH.
whisper-cli (whisper.cpp) is optional and only used to time captions of filmed
hooks.

Usage::

    python3 tools/make_reel.py --plan work/reels.json --reel R1 --hook H1 --out out/R1-H1.mp4
    python3 tools/make_reel.py --plan work/reels.json --all
    python3 tools/make_reel.py ... --debug     # + <out>.align.json and <out>.contact.jpg
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - environment problem
    sys.exit(f"make_reel.py needs numpy and Pillow ({exc}). "
             "Install them with: python3 -m pip install --user numpy Pillow")

# --------------------------------------------------------------------------
# Defaults and layout
# --------------------------------------------------------------------------

# Working folder of one video (holds work/, out/, hooks-filmed/). Set in main()
# from the plan's location: <BASE>/work/reels.json -> <BASE>.
BASE = Path.cwd()


def base_for_plan(plan_path: Path) -> Path:
    """<BASE>/work/reels.json -> <BASE>; a plan anywhere else -> its own folder."""
    return plan_path.parent.parent if plan_path.parent.name == "work" else plan_path.parent

OUT_W, OUT_H = 1080, 1920
TOP_H = 810                      # visuals panel height
BOT_H = OUT_H - TOP_H            # camera height (1110)
FPS = 30

# Visual panel of the edited 1920x1080 video (x, y, w, h).
PANEL_BOUNDS = (20, 20, 1474, 1040)
# Widest crop used: the panel's centre at exactly 4:3, so it fills 1080x810
# without letterboxing (the trimmed margins are the card's empty dark border).
DEFAULT_PANEL_CROP = (65, 21, 1384, 1038)
# Smart crop zooms in on the visual inside the panel, but never tighter than this
# width (keeps the upscale <= ~1.25x from a 1080p source).
PANEL_MIN_W = 880
# Small camera tile of the edited video, only used as a fallback when the raw
# camera cannot be aligned.
EDITED_CAM_TILE = (1530, 230, 354, 620)

CAM_ZOOM = 1.1                   # 1.0 = full source height in the bottom panel

ACCENT = (0xE8, 0x77, 0x4A)
INK = (0x14, 0x12, 0x10)
WHITE = (255, 255, 255)

CAPTION_CENTER_Y = 850           # captions sit on the top/bottom seam
CAPTION_FONT_SIZE = 76
CAPTION_MAX_W = 980
HOOK_TEXT_SECONDS = 2.5
HOOK_FADE_SECONDS = 0.25

TARGET_LUFS = -14.0
TARGET_TP = -1.0

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

# Alignment parameters (8 kHz mono).
SR = 8000
WIN_S = 2.0            # correlation window
HOP_S = 1.0            # window hop
BLOCK_S = 0.1          # assignment resolution of the dynamic program
WIN_ACCEPT = 0.35      # min normalised peak for a window to define a run
FALLBACK_NCC = 0.25    # a block must beat this to prefer raw camera over fallback
SWITCH_PENALTY = 1.0   # DP cost of switching runs (~ a few voiced blocks)
RUN_MIN_CONF = 0.30    # runs below this use the edited camera tile instead
MIN_RUN_FRAMES = 3     # shorter runs are merged into a neighbour

LOG_VERBOSE = True

# Whisper word times tend to run a little late, so captions are shown this much
# earlier than the transcript says (seconds). Override with --caption-lead.
CAPTION_LEAD = 0.25
# Cut points that land in speech are moved to the quietest spot within this
# distance (seconds), so a cut never clips a word. Off with --no-snap-cuts.
SNAP_CUT_S = 0.3


def log(msg: str) -> None:
    if LOG_VERBOSE:
        print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# Small ffmpeg helpers
# --------------------------------------------------------------------------

def run(cmd: list, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command, raising with its stderr on failure."""
    res = subprocess.run([str(c) for c in cmd], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", "replace")[-3000:]
        raise RuntimeError(f"command failed: {' '.join(map(str, cmd[:6]))} ...\n{err}")
    return res


def ffprobe_json(path: Path) -> dict:
    res = run(["ffprobe", "-v", "error", "-print_format", "json",
               "-show_format", "-show_streams", path])
    return json.loads(res.stdout)


def media_duration(path: Path) -> float:
    return float(ffprobe_json(path)["format"]["duration"])


def video_size(path: Path) -> tuple[int, int]:
    """Display size of the first video stream (rotation applied)."""
    for s in ffprobe_json(path)["streams"]:
        if s.get("codec_type") == "video":
            w, h = int(s["width"]), int(s["height"])
            rot = 0
            for sd in s.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rot = int(float(sd["rotation"]))
            rot = int(float(s.get("tags", {}).get("rotate", rot)))
            return (h, w) if abs(rot) % 180 == 90 else (w, h)
    raise RuntimeError(f"no video stream in {path}")


def has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in ffprobe_json(path)["streams"])


def decode_mono(path: Path, sr: int, start: float = 0.0,
                dur: Optional[float] = None) -> np.ndarray:
    """Decode audio to a mono float32 array at ``sr``."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if start > 0:
        cmd += ["-ss", f"{start:.6f}"]
    cmd += ["-i", path]
    if dur is not None:
        cmd += ["-t", f"{dur:.6f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(run(cmd).stdout, dtype=np.float32).copy()


def write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def frames(seconds: float) -> int:
    return int(round(seconds * FPS))


# --------------------------------------------------------------------------
# Plan, words and paths
# --------------------------------------------------------------------------

@dataclass
class Word:
    start: float
    end: float
    text: str


def load_words(path: Path) -> list[Word]:
    """Merge whisper tokens into words (a token starting with a space opens a word)."""
    words: list[Word] = []
    for tok in json.loads(path.read_text()):
        t = tok["w"]
        if not t.strip():
            continue
        if t.startswith(" ") or not words:
            words.append(Word(float(tok["start"]), float(tok["end"]), t.strip()))
        else:
            words[-1].text += t.strip()
            words[-1].end = max(words[-1].end, float(tok["end"]))
    return words


def fix_caption_words(words: list[Word], fixes: Optional[dict]) -> list[Word]:
    """Apply a reel's optional "caption_fixes" {"heard words": "right words"} to caption words.
    Keys match whole words (case-insensitive, trailing punctuation kept). A replacement with the
    same word count maps 1:1; otherwise the matched words merge into one caption word."""
    if not fixes:
        return words
    pats = sorted(((k.split(), v.split()) for k, v in fixes.items() if k.split()),
                  key=lambda kv: -len(kv[0]))
    def bare(t: str) -> str:
        return t.rstrip(".,!?;:").lower()
    out: list[Word] = []
    i = 0
    while i < len(words):
        for src, dst in pats:
            seg = words[i:i + len(src)]
            if len(seg) == len(src) and all(bare(w.text) == s.lower() for w, s in zip(seg, src)):
                tail = seg[-1].text[len(seg[-1].text.rstrip(".,!?;:")):]
                if len(dst) == len(src):
                    out += [Word(w.start, w.end, d) for w, d in zip(seg, dst)]
                    out[-1].text += tail
                else:
                    out.append(Word(seg[0].start, seg[-1].end, " ".join(dst) + tail))
                i += len(src)
                break
        else:
            out.append(words[i])
            i += 1
    return out


def resolve_path(value: Optional[str], default: Path) -> Path:
    if not value:
        return default
    p = Path(os.path.expanduser(value))
    return p if p.is_absolute() else (BASE / p)


def find_filmed_hook(hooks_dir: Path, reel_id: str, hook_id: str) -> Optional[Path]:
    for ext in (".mov", ".mp4", ".m4v", ".MOV", ".MP4"):
        p = hooks_dir / f"{reel_id}-{hook_id}{ext}"
        if p.exists():
            return p
    return None


# --------------------------------------------------------------------------
# Audio alignment against the raw microphones
# --------------------------------------------------------------------------

@dataclass
class Take:
    name: str          # e.g. "02 Tip 1 ELI5"
    mic: Path
    camera: Path
    unused: bool


@dataclass
class Run:
    """A stretch of the reel timeline with one source for the bottom camera."""
    ed_start: float               # edited-video seconds
    ed_end: float
    take: Optional[Take]          # None = fallback to the edited camera tile
    offset: float = 0.0           # raw_time = edited_time + offset
    conf: float = 0.0
    note: str = ""

    @property
    def fallback(self) -> bool:
        return self.take is None


class MicBank:
    """Raw microphone tracks, decoded once to 8 kHz and cached as .npy."""

    def __init__(self, raw_dir: Path, cache_dir: Path):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.takes: list[Take] = []
        for mic in sorted(raw_dir.glob("*.wav")):
            if " - microphone" not in mic.name:
                continue
            cam = mic.with_name(mic.name.replace(" - microphone", " - camera")).with_suffix(".mov")
            if not cam.exists():
                alt = cam.with_suffix(".mp4")
                cam = alt if alt.exists() else cam
            if not cam.exists():
                log(f"  [align] no camera file for {mic.name}, skipping")
                continue
            name = mic.stem.replace(" - microphone", "")
            self.takes.append(Take(name, mic, cam, "unused take" in mic.name))
        self._audio: dict[Path, np.ndarray] = {}
        self._edited: dict[Path, np.ndarray] = {}

    def _cached_decode(self, path: Path) -> np.ndarray:
        st = path.stat()
        key = hashlib.sha1(f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:12]
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem)[:60]
        npy = self.cache_dir / f"{safe}.{key}.{SR}.npy"
        if npy.exists():
            return np.load(npy)
        log(f"  [align] decoding {path.name} at {SR} Hz (cached afterwards)")
        x = decode_mono(path, SR)
        np.save(npy, x)
        return x

    def audio(self, take: Take) -> np.ndarray:
        if take.mic not in self._audio:
            self._audio[take.mic] = self._cached_decode(take.mic)
        return self._audio[take.mic]

    def edited(self, path: Path) -> np.ndarray:
        if path not in self._edited:
            self._edited[path] = self._cached_decode(path)
        return self._edited[path]


def _ncc_search(win: np.ndarray, raw: np.ndarray) -> tuple[int, float]:
    """Best lag k (raw[k:k+n] ~ win) and its normalised cross-correlation peak."""
    n, m = len(win), len(raw)
    if m < n:
        return 0, 0.0
    nfft = 1 << (m + n - 1).bit_length()
    spec = np.fft.rfft(win[::-1].astype(np.float64), nfft) * np.fft.rfft(raw.astype(np.float64), nfft)
    corr = np.fft.irfft(spec, nfft)[n - 1:m]
    cs = np.concatenate([[0.0], np.cumsum(raw.astype(np.float64) ** 2)])
    energy = cs[n:m + 1] - cs[:m - n + 1]
    # Floor the energy so near-silent stretches of the raw track cannot win.
    floor = 0.05 * n * float(np.mean(raw.astype(np.float64) ** 2))
    ncc = corr / (np.linalg.norm(win) * np.sqrt(np.maximum(energy, floor)) + 1e-12)
    k = int(np.argmax(ncc))
    return k, float(ncc[k])


def _ncc_at(win: np.ndarray, raw: np.ndarray, k: int) -> float:
    if k < 0 or k + len(win) > len(raw):
        return 0.0
    seg = raw[k:k + len(win)]
    den = float(np.linalg.norm(win) * np.linalg.norm(seg))
    return float(np.dot(win, seg) / den) if den > 1e-9 else 0.0


class Aligner:
    """Maps ranges of the edited video onto (raw take, constant offset) runs."""

    def __init__(self, bank: MicBank, edited: Path):
        self.bank = bank
        self.edited_audio = bank.edited(edited)

    # -- window search -----------------------------------------------------
    def _search_window(self, win: np.ndarray, hint: Optional[tuple[Take, int]]):
        """Return (take, raw_sample, conf) for one window, trying the hint first."""
        if hint is not None:
            take, k = hint
            c = _ncc_at(win, self.bank.audio(take), k)
            if c >= 0.5:
                return take, k, c
            k2, c2 = _ncc_search(win, self.bank.audio(take))
            if c2 >= 0.5:
                return take, k2, c2
        best = (None, 0, 0.0)
        for unused_pass in (False, True):
            for take in self.bank.takes:
                if take.unused != unused_pass:
                    continue
                k, c = _ncc_search(win, self.bank.audio(take))
                if c > best[2]:
                    best = (take, k, c)
            if best[2] >= WIN_ACCEPT:
                break  # unused takes only when nothing else matched
        return best

    def align(self, ed_start: float, ed_end: float) -> tuple[list[Run], list[dict]]:
        e_all = self.edited_audio
        a, b = int(round(ed_start * SR)), int(round(ed_end * SR))
        e = e_all[a:b].astype(np.float64)
        n_win, n_hop = int(WIN_S * SR), int(HOP_S * SR)

        # 1) coarse: overlapping windows, each matched against the raw mics.
        rms_all = np.sqrt(np.mean(e ** 2)) + 1e-12
        windows, hint = [], None
        starts = list(range(0, max(1, len(e) - n_win + 1), n_hop))
        if len(e) > n_win and starts[-1] + n_win < len(e):
            starts.append(len(e) - n_win)
        for s in starts:
            win = e[s:s + n_win]
            rec = {"t": round(ed_start + s / SR, 3), "dur": round(len(win) / SR, 3)}
            if np.sqrt(np.mean(win ** 2)) < 0.15 * rms_all:
                rec["silent"] = True
                windows.append(rec)
                continue
            take, k, c = self._search_window(win, hint)
            rec.update({"take": take.name if take else None, "conf": round(c, 3)})
            if take is not None:
                rec["offset"] = round(k / SR - (ed_start + s / SR), 4)
                rec["_take"], rec["_lag"] = take, k - s  # raw index of piece sample 0
                if c >= WIN_ACCEPT:
                    hint = (take, k + n_hop)
            windows.append(rec)

        # 2) candidate runs = consecutive confident windows with the same lag.
        groups: list[tuple[Take, int]] = []
        for w in windows:
            if w.get("conf", 0) < WIN_ACCEPT or "_take" not in w:
                continue
            if groups and groups[-1][0] is w["_take"] and abs(groups[-1][1] - w["_lag"]) <= 4:
                continue
            groups.append((w["_take"], w["_lag"]))

        runs = self._assign_blocks(e, ed_start, groups)
        for w in windows:
            w.pop("_take", None)
            w.pop("_lag", None)
        return runs, windows

    # -- fine assignment ---------------------------------------------------
    def _assign_blocks(self, e: np.ndarray, ed_start: float,
                       groups: list[tuple[Take, int]]) -> list[Run]:
        nb_s = int(BLOCK_S * SR)
        nblocks = max(1, int(math.ceil(len(e) / nb_s)))
        dur = len(e) / SR
        if not groups:
            return [Run(ed_start, ed_start + dur, None, conf=0.0, note="no audio match")]

        blk = [e[i * nb_s:(i + 1) * nb_s] for i in range(nblocks)]
        rms = np.array([np.sqrt(np.mean(x ** 2)) if len(x) else 0.0 for x in blk])
        ref = 0.5 * (np.percentile(rms, 75) + 1e-12)
        weight = np.clip(rms / ref, 0.0, 1.0)

        # NCC of each block against each candidate run.
        ncc = np.zeros((nblocks, len(groups)))
        for g, (take, lag) in enumerate(groups):
            raw = self.bank.audio(take)
            for i, x in enumerate(blk):
                ncc[i, g] = _ncc_at(x, raw, i * nb_s + lag)

        # States: F0, G0, F1, G1, ..., G_{n-1}, F_n (F = fallback). Monotonic.
        n_states = 2 * len(groups) + 1
        score = np.empty((nblocks, n_states))
        score[:, 0::2] = (FALLBACK_NCC * weight)[:, None]
        score[:, 1::2] = ncc * weight[:, None]
        dp = score[0].copy()
        back = np.zeros((nblocks, n_states), dtype=np.int32)
        idx = np.arange(n_states)
        for i in range(1, nblocks):
            # best strictly-earlier state for every k (prefix max, shifted by one)
            pm_val = np.maximum.accumulate(dp)
            pm_arg = np.zeros(n_states, dtype=np.int64)
            cur = 0
            for k in range(n_states):
                if dp[k] >= dp[cur]:
                    cur = k
                pm_arg[k] = cur
            prev_val = np.concatenate([[-np.inf], pm_val[:-1]]) - SWITCH_PENALTY
            prev_arg = np.concatenate([[0], pm_arg[:-1]])
            stay = dp >= prev_val
            back[i] = np.where(stay, idx, prev_arg)
            dp = score[i] + np.where(stay, dp, prev_val)
        state = np.empty(nblocks, dtype=np.int64)
        state[-1] = int(np.argmax(dp))
        for i in range(nblocks - 1, 0, -1):
            state[i - 1] = back[i, state[i]]

        # Collapse to block runs, merging neighbours with the same take/lag.
        spans: list[list] = []   # [first_block, last_block_excl, group or None]
        for i, s in enumerate(state):
            g = (s - 1) // 2 if s % 2 == 1 else None
            if spans and (spans[-1][2] == g or (
                    g is not None and spans[-1][2] is not None
                    and groups[spans[-1][2]][0] is groups[g][0]
                    and abs(groups[spans[-1][2]][1] - groups[g][1]) <= 4)):
                spans[-1][1] = i + 1
            else:
                spans.append([i, i + 1, g])

        # Refine boundaries between two raw runs to 10 ms.
        bounds = [sp[0] * nb_s for sp in spans] + [len(e)]
        for j in range(1, len(spans)):
            ga, gb = spans[j - 1][2], spans[j][2]
            if ga is None or gb is None:
                continue
            bounds[j] = self._refine_cut(e, bounds[j], groups[ga], groups[gb])

        runs: list[Run] = []
        for j, sp in enumerate(spans):
            s0, s1 = bounds[j], bounds[j + 1]
            if s1 <= s0:
                continue
            t0, t1 = ed_start + s0 / SR, ed_start + s1 / SR
            b0, b1 = sp[0], sp[1]
            if sp[2] is None:
                runs.append(Run(t0, t1, None, conf=0.0, note="low audio match"))
                continue
            take, lag = groups[sp[2]]
            wv = weight[b0:b1]
            voiced = wv > 0.3
            conf = float(np.sum(ncc[b0:b1, sp[2]][voiced] * wv[voiced]) / np.sum(wv[voiced])) \
                if voiced.any() else 1.0
            offset = lag / SR - ed_start
            runs.append(Run(t0, t1, take, offset=offset, conf=conf))
        for r in runs:
            if r.take is not None and r.conf < RUN_MIN_CONF:
                r.note = f"conf {r.conf:.2f} < {RUN_MIN_CONF}: fallback to edited camera tile"
                r.take = None
        return runs

    def _refine_cut(self, e: np.ndarray, guess: int, ga: tuple[Take, int],
                    gb: tuple[Take, int]) -> int:
        """Move a run boundary to the 10 ms step that best explains both sides."""
        step, span = int(0.01 * SR), int(0.2 * SR)
        lo, hi = max(0, guess - span), min(len(e), guess + span)
        n = (hi - lo) // step
        if n < 2:
            return guess

        def contrib(group):
            take, lag = group
            raw = self.bank.audio(take)
            out = np.zeros(n)
            for i in range(n):
                s = lo + i * step
                k = s + lag
                if 0 <= k and k + step <= len(raw):
                    x = e[s:s + step]
                    out[i] = -float(np.sum((x - raw[k:k + step] * self._gain(e, raw, s, k)) ** 2))
            return out

        ca, cb = contrib(ga), contrib(gb)
        # total(split at i) = sum(ca[:i]) + sum(cb[i:])
        tot = np.concatenate([[0], np.cumsum(ca)]) + (np.sum(cb) - np.concatenate([[0], np.cumsum(cb)]))
        return lo + int(np.argmax(tot)) * step

    @staticmethod
    def _gain(e: np.ndarray, raw: np.ndarray, s: int, k: int) -> float:
        """Least-squares gain mapping raw to edited around one position (0.5 s)."""
        h = int(0.25 * SR)
        a0, a1 = max(0, s - h), min(len(e), s + h)
        r0 = k - (s - a0)
        if r0 < 0 or r0 + (a1 - a0) > len(raw):
            return 1.0
        x, y = e[a0:a1], raw[r0:r0 + (a1 - a0)]
        den = float(np.dot(y, y))
        return float(np.dot(x, y) / den) if den > 1e-12 else 1.0


# --------------------------------------------------------------------------
# Camera framing
# --------------------------------------------------------------------------

_center_cache: dict[tuple, float] = {}


def detect_subject_center(path: Path, t0: float = 0.0, t1: Optional[float] = None) -> float:
    """Rough horizontal centre (0..1) of the speaker, from dark hair/shirt mass.

    The talking-head shots are a person in dark clothes against a light wall,
    so the column centroid of dark pixels in the upper-middle band of the frame
    is a cheap, dependable subject estimate. Override with --cam-center.
    """
    key = (str(path), round(t0, 1), round(t1 or -1, 1))
    if key in _center_cache:
        return _center_cache[key]
    if t1 is None:
        t1 = media_duration(path)
    xs = []
    for f in (0.2, 0.5, 0.8):
        t = t0 + (t1 - t0) * f
        res = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", str(path),
                              "-frames:v", "1", "-vf", "scale=192:-2,format=gray",
                              "-f", "rawvideo", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        buf = np.frombuffer(res.stdout, dtype=np.uint8)
        if buf.size < 192 * 10:
            continue
        img = buf.reshape(-1, 192).astype(np.float32)
        h = img.shape[0]
        band = img[int(0.12 * h):int(0.62 * h)]
        dark = (band < 55).astype(np.float32)
        col = dark.sum(axis=0)
        if col.sum() < 20:
            continue
        xs.append(float((col * np.arange(192)).sum() / col.sum() / 191.0))
    cx = float(np.median(xs)) if xs else 0.5
    _center_cache[key] = cx
    return cx


def smart_panel_crop(edited: Path, t0: float, t1: float) -> tuple[int, int, int, int]:
    """4:3 crop of the visuals panel that frames what is actually shown in it.

    Samples ~1 frame/s of the range, downsamples the panel 8x (which averages
    the drifting dot grid into a flat background) and takes the union bounding
    box of cells that differ from the background. Small visuals (a tweet, a
    card) get enlarged; full-panel screen recordings keep the full crop.
    """
    px, py, pw, ph = PANEL_BOUNDS
    sw, sh = pw // 8, ph // 8
    step = max(0.5, min(1.0, (t1 - t0) / 6))
    res = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t0:.3f}", "-i", str(edited),
                          "-t", f"{t1 - t0:.3f}", "-vf",
                          f"fps={1 / step:.4f},crop={pw}:{ph}:{px}:{py},scale={sw}:{sh}:flags=area,format=gray",
                          "-f", "rawvideo", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buf = np.frombuffer(res.stdout, dtype=np.uint8)
    n = buf.size // (sw * sh)
    if n == 0:
        return DEFAULT_PANEL_CROP
    imgs = buf[:n * sw * sh].reshape(n, sh, sw).astype(np.float32)
    mask = np.zeros((sh, sw), dtype=bool)
    for img in imgs:
        border = np.concatenate([img[:3].ravel(), img[-3:].ravel(), img[:, :3].ravel(), img[:, -3:].ravel()])
        bg = float(np.median(border))
        mask |= np.abs(img - bg) > 10
    # drop the rounded-corner/edge cells, then require rows/cols with real content
    mask[:2], mask[-2:], mask[:, :2], mask[:, -2:] = False, False, False, False
    cols = np.where(mask.sum(axis=0) >= 2)[0]
    rows = np.where(mask.sum(axis=1) >= 2)[0]
    if cols.size == 0 or rows.size == 0:
        return DEFAULT_PANEL_CROP
    x0, x1 = px + cols[0] * 8 - 36, px + (cols[-1] + 1) * 8 + 36
    y0, y1 = py + rows[0] * 8 - 36, py + (rows[-1] + 1) * 8 + 36
    _, _, dw, dh = DEFAULT_PANEL_CROP
    w = max(x1 - x0, (y1 - y0) * 4 / 3, PANEL_MIN_W)
    w = min(w, dw)
    h = w * 3 / 4
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    inset = 24   # keep the card's rounded corners and border out of frame
    x = int(round(min(max(cx - w / 2, px + inset), px + pw - inset - w)))
    y = int(round(min(max(cy - h / 2, py + 1), py + ph - 1 - h)))
    return x, y, int(w) // 2 * 2, int(h) // 2 * 2


def camera_crop(src_w: int, src_h: int, cx: float, zoom: float = CAM_ZOOM) -> tuple[int, int, int, int]:
    """Crop (x, y, w, h) of the source that fills the 1080x1110 bottom panel.

    Top-anchored: talking-head framing keeps the head near the top of the
    frame, and the seam captions only cover hair, never the face.
    """
    aspect = OUT_W / BOT_H
    ch = src_h / max(zoom, 1.0)
    cw = ch * aspect
    if cw > src_w:
        cw = src_w
        ch = cw / aspect
    cw, ch = int(cw) // 2 * 2, int(ch) // 2 * 2
    x = int(round(cx * src_w - cw / 2))
    x = max(0, min(src_w - cw, x))
    # Portrait sources (phone hooks): start a little below the top.
    y = 0 if src_h <= src_w else int(min(src_h - ch, 0.08 * src_h))
    return x, y, cw, ch


# --------------------------------------------------------------------------
# Text rendering (captions, hook text, title card)
# --------------------------------------------------------------------------

def find_font(override: Optional[str]) -> Optional[str]:
    if override:
        return override
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


class TextKit:
    def __init__(self, font_path: Optional[str]):
        self.font_path = font_path
        self._fonts: dict[int, ImageFont.FreeTypeFont] = {}

    def font(self, size: int):
        if size not in self._fonts:
            if self.font_path:
                self._fonts[size] = ImageFont.truetype(self.font_path, size)
            else:
                self._fonts[size] = ImageFont.load_default(size=size)
        return self._fonts[size]

    def width(self, text: str, size: int, stroke: int = 0) -> int:
        l, _, r, _ = self.font(size).getbbox(text, stroke_width=stroke)
        return r - l

    def draw_words(self, draw: ImageDraw.ImageDraw, words: list[str], colors: list,
                   cx: int, cy: int, size: int, stroke: int, stroke_fill) -> None:
        """Draw one line of words centred on (cx, cy), each with its own colour."""
        font = self.font(size)
        space = self.width(" ", size)
        widths = [self.width(w, size, stroke) - 2 * stroke for w in words]
        total = sum(widths) + space * (len(words) - 1)
        x = cx - total / 2
        for w, wd, col in zip(words, widths, colors):
            draw.text((x, cy), w, font=font, fill=col, anchor="lm",
                      stroke_width=stroke, stroke_fill=stroke_fill)
            x += wd + space

    def wrap(self, words: list[str], size: int, max_w: int) -> list[list[int]]:
        """Wrap into as few lines as fit ``max_w``, then balance the line widths
        (so a title never ends on one orphaned word). Returns word indices."""
        n = len(words)
        greedy, cur = 1, []
        for i in range(n):
            if cur and self.width(" ".join(words[j] for j in cur + [i]), size) > max_w:
                greedy += 1
                cur = []
            cur.append(i)
        n_lines = min(greedy, n)

        def splits(start: int, k: int):
            if k == 1:
                yield [list(range(start, n))]
                return
            for cut in range(start + 1, n - k + 2):
                for rest in splits(cut, k - 1):
                    yield [list(range(start, cut))] + rest

        best, best_w = None, float("inf")
        if n <= 12:
            for lines in splits(0, n_lines):
                w = max(self.width(" ".join(words[i] for i in ln), size) for ln in lines)
                if w < best_w:
                    best, best_w = lines, w
        return best or [list(range(n))]


def pick_key_word(text: str, explicit: Optional[str] = None) -> int:
    """Index of the word to colour in the accent: explicit, a number, else the longest."""
    words = text.split()
    if not words:
        return -1
    clean = [re.sub(r"[^\w%$]", "", w).lower() for w in words]
    if explicit:
        target = re.sub(r"[^\w%$]", "", explicit).lower()
        for i, c in enumerate(clean):
            if c == target:
                return i
    for i, w in enumerate(words):
        if re.search(r"\d", w):
            return i
    return max(range(len(words)), key=lambda i: len(clean[i]))


def render_caption(kit: TextKit, img: Image.Image, words: list[str], active: int) -> None:
    size = CAPTION_FONT_SIZE
    stroke = 8
    while size > 40 and kit.width(" ".join(words), size, stroke) > CAPTION_MAX_W:
        size -= 4
    draw = ImageDraw.Draw(img)
    colors = [ACCENT if i == active else WHITE for i in range(len(words))]
    # soft drop shadow for separation from busy backgrounds
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    kit.draw_words(sd, words, [(0, 0, 0, 150)] * len(words), OUT_W // 2 + 3, CAPTION_CENTER_Y + 5,
                   size, stroke + 2, (0, 0, 0, 150))
    img.alpha_composite(shadow)
    kit.draw_words(draw, words, colors, OUT_W // 2, CAPTION_CENTER_Y, size, stroke, INK + (255,))


def render_hook_banner(kit: TextKit, img: Image.Image, text: str, key: Optional[str],
                       alpha: float) -> None:
    """Hook text in a dark rounded card near the top of the frame."""
    words = text.split()
    if not words or alpha <= 0:
        return
    key_i = pick_key_word(text, key)
    size = 88
    lines = kit.wrap(words, size, 920)
    while len(lines) > 2 and size > 48:
        size -= 6
        lines = kit.wrap(words, size, 920)
    line_h = int(size * 1.18)
    box_w = max(kit.width(" ".join(words[i] for i in ln), size) for ln in lines) + 96
    box_h = line_h * len(lines) + 70
    x0 = (OUT_W - box_w) // 2
    y0 = 96
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=28, fill=INK + (235,),
                        outline=ACCENT + (255,), width=4)
    for li, ln in enumerate(lines):
        cy = y0 + 35 + line_h * li + line_h // 2
        kit.draw_words(d, [words[i] for i in ln],
                       [ACCENT if i == key_i else WHITE for i in ln],
                       OUT_W // 2, cy, size, 0, None)
    if alpha < 1:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer.putalpha(a)
    img.alpha_composite(layer)


def render_title_card(kit: TextKit, text: str, key: Optional[str], path: Path) -> None:
    """1080x810 top card for filmed hooks: dark dot grid, big white text, accent word."""
    img = Image.new("RGB", (OUT_W, TOP_H), INK)
    d = ImageDraw.Draw(img)
    for y in range(18, TOP_H, 36):
        for x in range(18, OUT_W, 36):
            d.ellipse([x - 1.6, y - 1.6, x + 1.6, y + 1.6], fill=(0x2E, 0x2A, 0x26))
    # vignette-ish soft centre glow so the text sits on a calmer area
    glow = Image.new("L", (OUT_W, TOP_H), 0)
    ImageDraw.Draw(glow).ellipse([90, 120, OUT_W - 90, TOP_H - 120], fill=255)
    glow = glow.resize((OUT_W // 8, TOP_H // 8)).resize((OUT_W, TOP_H), Image.BILINEAR)
    img = Image.composite(Image.new("RGB", img.size, INK), img, glow.point(lambda v: int(v * 0.6)))
    d = ImageDraw.Draw(img)
    words = text.split()
    key_i = pick_key_word(text, key)
    size = 118
    lines = kit.wrap(words, size, 940)
    while (len(lines) > 3 or len(lines) * size * 1.15 > TOP_H - 220) and size > 56:
        size -= 6
        lines = kit.wrap(words, size, 940)
    line_h = int(size * 1.15)
    top = (TOP_H - line_h * len(lines)) // 2 + 10
    for li, ln in enumerate(lines):
        kit.draw_words(d, [words[i] for i in ln], [ACCENT if i == key_i else WHITE for i in ln],
                       OUT_W // 2, top + line_h * li + line_h // 2, size, 0, None)
    # small accent rule under the text
    rule_y = top + line_h * len(lines) + 28
    d.rounded_rectangle([OUT_W // 2 - 60, rule_y, OUT_W // 2 + 60, rule_y + 8], radius=4, fill=ACCENT)
    img.save(path)


# --------------------------------------------------------------------------
# Captions: chunking + overlay track
# --------------------------------------------------------------------------

def chunk_words(words: list[Word], max_words: int = 4, max_chars: int = 22,
                gap: float = 0.45) -> list[list[Word]]:
    chunks: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur and (len(cur) >= max_words or w.start - cur[-1].end > gap
                    or len(" ".join(x.text for x in cur + [w])) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w.text[-1] in ".?!" and len(cur) >= 2:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    # fold a lone trailing word back into the previous chunk when it fits
    out: list[list[Word]] = []
    for c in chunks:
        if (len(c) == 1 and out and len(out[-1]) < max_words
                and c[0].start - out[-1][-1].end < gap
                and len(" ".join(x.text for x in out[-1] + c)) <= max_chars + 4):
            out[-1] = out[-1] + c
        else:
            out.append(c)
    return out


def build_overlay_track(kit: TextKit, words: list[Word], total: float, hook_text: Optional[str],
                        hook_key: Optional[str], tmp: Path) -> Path:
    """Render caption/hook states as PNGs and return an ffconcat list for them."""
    chunks = chunk_words(words)
    events: list[tuple[float, float, int, int]] = []   # start, end, chunk, word
    for ci, ch in enumerate(chunks):
        nxt = chunks[ci + 1][0].start if ci + 1 < len(chunks) else total
        end = min(nxt, ch[-1].end + 0.6) if nxt - ch[-1].end > 0.6 else nxt
        end = min(end, total)
        for wi, w in enumerate(ch):
            ws = w.start if wi else w.start
            we = ch[wi + 1].start if wi + 1 < len(ch) else end
            if we > ws:
                events.append((ws, we, ci, wi))

    hook_steps: list[tuple[float, float, float]] = []   # start, end, alpha
    if hook_text:
        hook_steps.append((0.0, HOOK_TEXT_SECONDS, 1.0))
        n = 5
        for i in range(n):
            a = HOOK_TEXT_SECONDS + HOOK_FADE_SECONDS * i / n
            b = HOOK_TEXT_SECONDS + HOOK_FADE_SECONDS * (i + 1) / n
            hook_steps.append((a, b, 1.0 - (i + 1) / (n + 1)))

    def q(t: float) -> float:
        return round(max(0.0, min(total, t)) * FPS) / FPS

    cuts = {0.0, q(total)}
    for s, e, *_ in events:
        cuts.update((q(s), q(e)))
    for s, e, _ in hook_steps:
        cuts.update((q(s), q(e)))
    cuts = sorted(cuts)

    cache: dict[tuple, Path] = {}
    lines = ["ffconcat version 1.0"]
    last = None
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 1e-6:
            continue
        mid = (a + b) / 2
        cap = next(((c, w) for s, e, c, w in events if q(s) <= mid < q(e)), None)
        alpha = next((al for s, e, al in hook_steps if q(s) <= mid < q(e)), 0.0)
        key = (cap, round(alpha, 3))
        if key not in cache:
            img = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
            if alpha > 0:
                render_hook_banner(kit, img, hook_text, hook_key, alpha)
            if cap is not None:
                ch = chunks[cap[0]]
                render_caption(kit, img, [w.text for w in ch], cap[1])
            p = tmp / f"ov_{len(cache):04d}.png"
            img.save(p, optimize=False, compress_level=1)
            cache[key] = p
        lines += [f"file '{cache[key].name}'", f"duration {b - a:.6f}"]
        last = cache[key]
    if last is not None:
        lines.append(f"file '{last.name}'")
    lst = tmp / "overlay.ffconcat"
    lst.write_text("\n".join(lines) + "\n")
    return lst


# --------------------------------------------------------------------------
# Whisper (filmed hooks only)
# --------------------------------------------------------------------------

def whisper_words(audio16k: Path, model: Path, tmp: Path) -> list[Word]:
    """Word timings from whisper.cpp's CLI; empty list if unavailable or it fails."""
    exe = shutil.which("whisper-cli") or shutil.which("whisper-cpp")
    if not exe or not model.exists():
        log("  [hook] whisper-cli or model not found; captions will be timed evenly")
        return []
    out = tmp / "whisper"
    res = subprocess.run([exe, "-m", str(model), "-f", str(audio16k), "-oj", "-of", str(out),
                          "-ml", "1", "-sow", "-np"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    jp = out.with_suffix(".json")
    if res.returncode != 0 or not jp.exists():
        log("  [hook] whisper failed; captions will be timed evenly")
        return []
    data = json.loads(jp.read_text(errors="replace"))
    words = []
    for seg in data.get("transcription", []):
        t = seg.get("text", "").strip()
        if not t or t.startswith("[") or t.startswith("("):
            continue
        a, b = seg["offsets"]["from"] / 1000.0, seg["offsets"]["to"] / 1000.0
        if words and not re.match(r"^[\w$#@]", t):   # punctuation glued to previous word
            words[-1].text += t
            continue
        words.append(Word(a, b, t))
    return words


def even_words(text: str, t0: float, t1: float) -> list[Word]:
    toks = text.split()
    if not toks:
        return []
    weights = [len(t) + 2 for t in toks]
    total = sum(weights)
    out, t = [], t0
    for tok, wgt in zip(toks, weights):
        d = (t1 - t0) * wgt / total
        out.append(Word(t, t + d, tok))
        t += d
    return out


# --------------------------------------------------------------------------
# Loudness
# --------------------------------------------------------------------------

def loudnorm(src: Path, dst: Path, sr: int = 48000) -> dict:
    """Two-pass EBU R128 normalisation to TARGET_LUFS; returns measured stats."""
    spec = f"I={TARGET_LUFS}:TP={TARGET_TP}:LRA=11"
    res = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-af",
                          f"loudnorm={spec}:print_format=json", "-f", "null", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    txt = res.stderr.decode("utf-8", "replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", txt, re.S)
    if not m:
        raise RuntimeError("loudnorm measurement failed")
    st = json.loads(m.group(0))
    if float(st["input_i"]) < -60:  # silence: nothing to normalise
        shutil.copy(src, dst)
        return st
    af = (f"loudnorm={spec}:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
          f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:"
          f"offset={st['target_offset']}:linear=true")
    run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", src, "-af", af, "-ar", str(sr),
         "-ac", "1", "-c:a", "pcm_s16le", dst])
    return st


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        data = wf.readframes(wf.getnframes())
        ch = wf.getnchannels()
    x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    return x.reshape(-1, ch).mean(axis=1) if ch > 1 else x


# --------------------------------------------------------------------------
# Reel assembly
# --------------------------------------------------------------------------

@dataclass
class Piece:
    kind: str                       # "footage" | "film"
    label: str
    src_start: float                # edited seconds (footage) / clip seconds (film)
    src_end: float
    reel_start: float = 0.0         # on the reel timeline (frame aligned)
    n_frames: int = 0
    clip: Optional[Path] = None     # film hooks
    panel: tuple = DEFAULT_PANEL_CROP   # crop of the visuals panel (footage)
    runs: list = field(default_factory=list)
    windows: list = field(default_factory=list)
    words: list = field(default_factory=list)   # reel-timed captions


@dataclass
class Settings:
    edited: Path
    raw_dir: Path
    hooks_dir: Path
    words_path: Path
    cache_dir: Path
    panel_crop: Optional[tuple]     # None = smart crop per piece
    cam_center: Optional[float]
    cam_zoom: float
    font: Optional[str]
    whisper_model: Path
    debug: bool
    keep_temp: bool
    caption_lead: float = CAPTION_LEAD
    snap_cuts: bool = True


class ReelBuilder:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.kit = TextKit(find_font(cfg.font))
        self.words = load_words(cfg.words_path) if cfg.words_path.exists() else []
        self._bank: Optional[MicBank] = None
        self._aligner: Optional[Aligner] = None
        self.edited_size = video_size(cfg.edited)

    @property
    def aligner(self) -> Aligner:
        if self._aligner is None:
            self._bank = MicBank(self.cfg.raw_dir, self.cfg.cache_dir)
            self._aligner = Aligner(self._bank, self.cfg.edited)
        return self._aligner

    # -- planning ----------------------------------------------------------
    def plan_pieces(self, reel: dict, hook: Optional[dict], tmp: Path) -> list[Piece]:
        segs = reel["segments"]
        pieces: list[Piece] = []
        if hook is not None:
            if hook.get("type") == "film":
                clip = find_filmed_hook(self.cfg.hooks_dir, reel["id"], hook["id"])
                if clip is None:
                    raise FileNotFoundError(
                        f"film hook {reel['id']}-{hook['id']} not recorded yet "
                        f"(expected in {self.cfg.hooks_dir})")
                pieces.append(self._film_piece(clip, hook, tmp))
            else:
                rng = hook["range"]
                first = segs[0]["start"]
                if rng["start"] <= first < rng["end"] or rng["start"] <= first <= rng["start"] + 0.05:
                    log(f"  hook {hook['id']} overlaps the first segment; the segment opens on it")
                else:
                    pieces.append(Piece("footage", f"hook {hook['id']}", rng["start"], rng["end"]))
        for i, s in enumerate(segs):
            pieces.append(Piece("footage", s.get("note") or f"segment {i + 1}", s["start"], s["end"]))
        if self.cfg.snap_cuts:
            self._snap_cuts_to_silence(pieces)
        t = 0.0
        for p in pieces:
            p.n_frames = frames(p.src_end - p.src_start)
            p.src_end = p.src_start + p.n_frames / FPS
            p.reel_start = t
            t += p.n_frames / FPS
        return pieces

    def _snap_cuts_to_silence(self, pieces: list[Piece]) -> None:
        """Move footage cut points that land in speech to the quietest nearby spot.

        Word times from a transcript can be off by a few hundred ms, so a cut
        snapped to a word start can clip its first sound or catch the next word.
        A cut that is already quiet stays where it is. Two pieces that touch on
        the edited timeline keep their shared boundary (that join is seamless).
        """
        self.aligner  # creates the mic bank on first use
        ed = self._bank.edited(self.cfg.edited)
        hop = int(SR * 0.01)
        n = len(ed) // hop
        if n == 0:
            return
        rms = np.sqrt(np.mean(ed[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
        db = 20 * np.log10(rms)

        def snap(t: float, lo: float, hi: float, floor: float = 0.0, ceil: float = 1e9) -> float:
            i = int(round(t * 100))
            a = max(0, int((t - lo) * 100), int(np.ceil(floor * 100)))
            b = min(n, int((t + hi) * 100) + 1, int(ceil * 100) + 1)
            if not (0 <= i < n) or b - a < 3:
                return t
            win = db[a:b]
            quiet = win.min() + 6.0
            if db[max(0, i - 2):i + 3].max() <= quiet + 4.0:
                return t                          # already in a pause
            cand = np.where(win <= quiet)[0] + a
            j = int(cand[np.argmin(np.abs(cand - i))])
            return j / 100.0

        foot = [p for p in pieces if p.kind == "footage"]
        spans = [(p.src_start, p.src_end) for p in foot]
        for k, p in enumerate(foot):
            # never grow into source time another piece of this reel already plays
            others = spans[:k] + spans[k + 1:]
            floor = max([e for s_, e in others if e <= p.src_start + 0.02], default=0.0)
            ceil = min([s_ for s_, e in others if s_ >= p.src_end - 0.02], default=1e9)
            prev_end = foot[k - 1].src_end if k else None
            nxt_start = foot[k + 1].src_start if k + 1 < len(foot) else None
            old = (p.src_start, p.src_end)
            if prev_end is None or abs(prev_end - p.src_start) > 0.02:
                p.src_start = snap(p.src_start, SNAP_CUT_S, 0.1, floor=floor)   # prefer earlier: keep the onset
            if nxt_start is None or abs(nxt_start - p.src_end) > 0.02:
                p.src_end = snap(p.src_end, 0.1, SNAP_CUT_S, ceil=ceil)         # prefer later: keep the tail
            if p.src_end - p.src_start < 0.2:
                p.src_start, p.src_end = old
            if (p.src_start, p.src_end) != old:
                log(f"  snapped {p.label}: {old[0]:.2f}-{old[1]:.2f} -> {p.src_start:.2f}-{p.src_end:.2f}")

    def _film_piece(self, clip: Path, hook: dict, tmp: Path) -> Piece:
        dur = media_duration(clip)
        words: list[Word] = []
        if has_audio(clip):
            wav16 = tmp / "hook16k.wav"
            run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", clip, "-vn", "-ac", "1",
                 "-ar", "16000", "-c:a", "pcm_s16le", wav16])
            x = read_wav(wav16)
            loud = 20 * math.log10(float(np.sqrt(np.mean(x ** 2))) + 1e-9) if x.size else -120
            if loud > -50:
                words = whisper_words(wav16, self.cfg.whisper_model, tmp)
            else:
                log(f"  [hook] {clip.name} audio is silent ({loud:.0f} dBFS); timing captions evenly")
        else:
            log(f"  [hook] {clip.name} has no audio track; timing captions evenly")
        start, end = 0.0, dur
        if words:
            # trim dead air around the line
            start = max(0.0, words[0].start - 0.2)
            end = min(dur, words[-1].end + 0.35)
            words = [Word(w.start - start, w.end - start, w.text) for w in words]
        else:
            words = even_words(hook.get("spoken", ""), 0.15, max(0.3, dur - 0.25))
        p = Piece("film", f"filmed hook {hook['id']}", start, end, clip=clip)
        p.words = words   # clip-relative for now, shifted in build()
        return p

    # -- rendering ---------------------------------------------------------
    def _panel_filter(self, crop: tuple, label_in: str, label_out: str) -> str:
        x, y, w, h = crop
        return (f"[{label_in}]crop={w}:{h}:{x}:{y},scale={OUT_W}:{TOP_H}:force_original_aspect_ratio=increase"
                f":flags=lanczos,crop={OUT_W}:{TOP_H},setsar=1,fps={FPS}[{label_out}]")

    def _cam_filter(self, src: Path, label_in: str, label_out: str, t0: float, t1: float) -> str:
        sw, sh = video_size(src)
        cx = self.cfg.cam_center if self.cfg.cam_center is not None else detect_subject_center(src, t0, t1)
        x, y, w, h = camera_crop(sw, sh, cx, self.cfg.cam_zoom)
        return (f"[{label_in}]crop={w}:{h}:{x}:{y},scale={OUT_W}:{BOT_H}:flags=lanczos,"
                f"setsar=1,fps={FPS}[{label_out}]")

    def _encode_tmp(self, inputs: list, graph: str, n_frames: int, out: Path) -> None:
        cmd = ["ffmpeg", "-v", "error", "-nostdin", "-y"] + inputs + [
            "-filter_complex", graph, "-map", "[v]", "-frames:v", str(n_frames), "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-video_track_timescale", "15360", out]
        run(cmd)

    def render_run(self, run_: Run, panel: tuple, n_frames: int, out: Path) -> None:
        ed = self.cfg.edited
        t0 = run_.ed_start
        if run_.fallback:
            tx, ty, tw, th = EDITED_CAM_TILE
            # tile is portrait 354x620; take a 1080:1110 window from its upper part
            ch = int(tw * BOT_H / OUT_W) // 2 * 2
            cy = ty + int(th * 0.06)
            graph = (f"[0:v]split[a][b];" + self._panel_filter(panel, "a", "top") + ";"
                     f"[b]crop={tw}:{ch}:{tx}:{cy},scale={OUT_W}:{BOT_H}:flags=lanczos,setsar=1,fps={FPS}[bot];"
                     f"[top][bot]vstack,format=yuv420p[v]")
            self._encode_tmp(["-ss", f"{t0:.4f}", "-i", ed], graph, n_frames, out)
            return
        cam = run_.take.camera
        cam_t = t0 + run_.offset
        if cam_t < 0:
            log(f"  [warn] camera time {cam_t:.2f}s < 0 for {run_.take.name}; clamped")
            cam_t = 0.0
        graph = (self._panel_filter(panel, "0:v", "top") + ";" +
                 self._cam_filter(cam, "1:v", "bot", cam_t, cam_t + n_frames / FPS) + ";"
                 "[top][bot]vstack,format=yuv420p[v]")
        self._encode_tmp(["-ss", f"{t0:.4f}", "-i", ed, "-ss", f"{cam_t:.4f}", "-i", cam],
                         graph, n_frames, out)

    def render_film(self, p: Piece, hook: dict, tmp: Path, out: Path) -> None:
        card = tmp / "title_card.png"
        render_title_card(self.kit, hook.get("on_screen_text") or hook.get("spoken", ""),
                          hook.get("accent_word"), card)
        graph = (f"[0:v]scale={OUT_W}:{TOP_H},setsar=1,fps={FPS}[top];" +
                 self._cam_filter(p.clip, "1:v", "bot", p.src_start, p.src_end) + ";"
                 "[top][bot]vstack,format=yuv420p[v]")
        self._encode_tmp(["-loop", "1", "-framerate", str(FPS), "-i", card,
                          "-ss", f"{p.src_start:.4f}", "-i", p.clip], graph, p.n_frames, out)

    def piece_audio(self, p: Piece, tmp: Path, idx: int) -> np.ndarray:
        n = int(round(p.n_frames / FPS * 48000))
        src = p.clip if p.kind == "film" else self.cfg.edited
        if p.kind == "film" and not has_audio(src):
            return np.zeros(n, dtype=np.float32)
        raw = tmp / f"a{idx:02d}_raw.wav"
        run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{p.src_start:.6f}", "-i", src,
             "-t", f"{p.n_frames / FPS + 0.05:.6f}", "-vn", "-ac", "1", "-ar", "48000",
             "-c:a", "pcm_s16le", raw])
        if p.kind == "film":   # filmed hooks are loudness-matched on their own first
            norm = tmp / f"a{idx:02d}_norm.wav"
            loudnorm(raw, norm)
            raw = norm
        x = read_wav(raw)
        x = np.pad(x, (0, max(0, n - len(x))))[:n]
        f = min(len(x) // 2, 240)       # 5 ms fades: no clicks at the joins
        if f:
            ramp = np.linspace(0, 1, f, dtype=np.float32)
            x[:f] *= ramp
            x[-f:] *= ramp[::-1]
        return x

    def build(self, plan: dict, reel: dict, hook: Optional[dict], out: Path) -> dict:
        out.parent.mkdir(parents=True, exist_ok=True)
        (BASE / "work").mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=f"reel_{reel['id']}_", dir=str(BASE / "work")))
        try:
            return self._build(reel, hook, out, tmp)
        finally:
            if self.cfg.keep_temp:
                log(f"  temp kept: {tmp}")
            else:
                shutil.rmtree(tmp, ignore_errors=True)

    def _build(self, reel: dict, hook: Optional[dict], out: Path, tmp: Path) -> dict:
        name = out.stem
        log(f"== {name}: {reel.get('title', '')}")
        pieces = self.plan_pieces(reel, hook, tmp)
        total_frames = sum(p.n_frames for p in pieces)
        total = total_frames / FPS

        # 1) alignment + per-run clips
        clips: list[Path] = []
        for pi, p in enumerate(pieces):
            if p.kind == "film":
                c = tmp / f"v{pi:02d}_00.mp4"
                self.render_film(p, hook, tmp, c)
                clips.append(c)
                p.words = [Word(w.start + p.reel_start, w.end + p.reel_start, w.text) for w in p.words]
                continue
            p.panel = self.cfg.panel_crop or smart_panel_crop(self.cfg.edited, p.src_start, p.src_end)
            log(f"  {p.label} [{p.src_start:.2f}-{p.src_end:.2f}] panel crop {p.panel}")
            runs, windows = self.aligner.align(p.src_start, p.src_end)
            runs = self._snap_runs(runs, p)
            p.runs, p.windows = runs, windows
            done = 0
            for ri, r in enumerate(runs):
                nf = frames(r.ed_end - p.src_start) - frames(r.ed_start - p.src_start)
                if ri == len(runs) - 1:
                    nf = p.n_frames - done
                c = tmp / f"v{pi:02d}_{ri:02d}.mp4"
                src = "edited tile (fallback)" if r.fallback else f"{r.take.name} {r.offset:+.3f}s"
                log(f"    run {r.ed_start:7.2f}-{r.ed_end:7.2f}  {src}  conf {r.conf:.2f} {r.note}")
                self.render_run(r, p.panel, nf, c)
                clips.append(c)
                done += nf
            # captions from the edited transcript, re-timed onto the reel
            for w in self.words:
                if p.src_start - 0.05 <= w.start < p.src_end - 0.05:
                    lead = self.cfg.caption_lead
                    s = p.reel_start + max(0.0, w.start - lead - p.src_start)
                    e = p.reel_start + max(0.0, min(p.src_end, w.end) - lead - p.src_start)
                    p.words.append(Word(s, max(e, s + 0.05), w.text))

        # 2) audio
        audio = np.concatenate([self.piece_audio(p, tmp, i) for i, p in enumerate(pieces)])
        body = tmp / "audio_body.wav"
        write_wav(body, audio, 48000)
        final_audio = tmp / "audio_final.wav"
        stats = loudnorm(body, final_audio)

        # 3) overlays
        words = fix_caption_words([w for p in pieces for w in p.words], reel.get("caption_fixes"))
        hook_text = (hook or {}).get("on_screen_text") or reel.get("on_screen_text")
        film_first = bool(pieces and pieces[0].kind == "film")
        overlay = build_overlay_track(self.kit, words, total, None if film_first else hook_text,
                                      (hook or {}).get("accent_word"), tmp)

        # 4) final encode
        lst = tmp / "clips.ffconcat"
        lst.write_text("ffconcat version 1.0\n" + "".join(f"file '{c.name}'\n" for c in clips))
        run(["ffmpeg", "-v", "error", "-nostdin", "-y",
             "-f", "concat", "-safe", "0", "-i", lst,
             "-f", "concat", "-safe", "0", "-i", overlay,
             "-i", final_audio,
             "-filter_complex", "[1:v]format=rgba[ov];[0:v][ov]overlay=0:0:eof_action=repeat,"
                                f"fps={FPS},format=yuv420p[v]",
             "-map", "[v]", "-map", "2:a", "-frames:v", str(total_frames),
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
             "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
             "-movflags", "+faststart", "-t", f"{total:.4f}", out])
        log(f"  wrote {out} ({total:.2f}s)")

        report = self._report(reel, hook, pieces, total, stats)
        if self.cfg.debug:
            out.with_suffix(".align.json").write_text(json.dumps(report, indent=2))
            contact_sheet(out, total, out.with_suffix(".contact.jpg"))
            log(f"  debug: {out.with_suffix('.align.json').name}, {out.with_suffix('.contact.jpg').name}")
        return report

    def _snap_runs(self, runs: list[Run], p: Piece) -> list[Run]:
        """Snap run boundaries to the reel's frame grid and drop sliver runs."""
        for r in runs:
            r.ed_start = p.src_start + frames(r.ed_start - p.src_start) / FPS
            r.ed_end = p.src_start + frames(r.ed_end - p.src_start) / FPS
        runs[0].ed_start = p.src_start
        runs[-1].ed_end = p.src_end
        out: list[Run] = []
        for r in runs:
            if out and frames(r.ed_end - r.ed_start) < MIN_RUN_FRAMES:
                out[-1].ed_end = r.ed_end
                continue
            if out and frames(out[-1].ed_end - out[-1].ed_start) < MIN_RUN_FRAMES:
                r.ed_start = out[-1].ed_start
                out[-1] = r
                continue
            out.append(r)
        return [r for r in out if r.ed_end > r.ed_start]

    def _report(self, reel, hook, pieces, total, stats) -> dict:
        rep = {"reel": reel["id"], "hook": (hook or {}).get("id"), "duration": round(total, 3),
               "loudness_in": {k: stats.get(k) for k in ("input_i", "input_tp", "input_lra")},
               "pieces": []}
        confs, fb = [], 0.0
        for p in pieces:
            d = {"kind": p.kind, "label": p.label, "src_start": round(p.src_start, 3),
                 "src_end": round(p.src_end, 3), "reel_start": round(p.reel_start, 3)}
            if p.kind == "film":
                d["clip"] = str(p.clip)
            else:
                d["panel_crop"] = list(p.panel)
                d["runs"] = [{"ed_start": round(r.ed_start, 3), "ed_end": round(r.ed_end, 3),
                              "take": r.take.name if r.take else None,
                              "camera": str(r.take.camera) if r.take else None,
                              "offset": round(r.offset, 4), "conf": round(r.conf, 3),
                              "fallback": r.fallback, "note": r.note} for r in p.runs]
                d["windows"] = p.windows
                for r in p.runs:
                    if r.fallback:
                        fb += r.ed_end - r.ed_start
                    else:
                        confs.append((r.conf, r.ed_end - r.ed_start))
            rep["pieces"].append(d)
        if confs:
            w = sum(d for _, d in confs)
            rep["summary"] = {"weighted_conf": round(sum(c * d for c, d in confs) / w, 3),
                              "min_run_conf": round(min(c for c, _ in confs), 3),
                              "fallback_seconds": round(fb, 2)}
        return rep


def contact_sheet(video: Path, total: float, out: Path, n: int = 6) -> None:
    """Tile n frames (3 x 2) with their timestamps for a quick visual check."""
    tw, th = 360, 640
    times = [min(total - 0.1, 0.6)] + [total * (i + 0.5) / (n - 1) for i in range(n - 1)]
    sheet = Image.new("RGB", (tw * 3, (th + 40) * ((n + 2) // 3)), (30, 30, 30))
    kit = TextKit(find_font(None))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(times):
        res = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", str(video),
                              "-frames:v", "1", "-vf", f"scale={tw}:{th}", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if len(res.stdout) != tw * th * 3:
            continue
        fr = Image.frombytes("RGB", (tw, th), res.stdout)
        x, y = (i % 3) * tw, (i // 3) * (th + 40)
        sheet.paste(fr, (x, y + 40))
        d.text((x + 10, y + 20), f"t={t:.2f}s", font=kit.font(26), fill=(230, 230, 230), anchor="lm")
    sheet.save(out, quality=88)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def renderable_hooks(reel: dict, hooks_dir: Path) -> list[dict]:
    out = []
    for h in reel.get("hooks", []):
        if h.get("type") == "film" and not find_filmed_hook(hooks_dir, reel["id"], h["id"]):
            continue
        out.append(h)
    return out


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, help="reels.json")
    ap.add_argument("--reel", help="reel id, e.g. R1")
    ap.add_argument("--hook", help="hook id, e.g. H1 (default: first renderable hook)")
    ap.add_argument("--all", action="store_true", help="every reel x every renderable hook")
    ap.add_argument("--out", help="output .mp4 (default: <BASE>/out/<reel>-<hook>.mp4)")
    ap.add_argument("--out-dir", help="output folder for --all (default: <BASE>/out)")
    ap.add_argument("--edited", help="edited long-form video (default: plan source.edited)")
    ap.add_argument("--raw-dir", help="raw recordings folder (default: plan source.raw_dir)")
    ap.add_argument("--hooks-dir", help="filmed hooks folder (default: <BASE>/hooks-filmed)")
    ap.add_argument("--words", help="words.json of the edited video (default: <BASE>/work/words.json)")
    ap.add_argument("--panel-crop", help="fixed x,y,w,h crop of the edited video for the top "
                    "(default: smart 4:3 crop around the visual, per segment)")
    ap.add_argument("--cam-center", type=float, help="horizontal subject centre 0..1 (default: auto)")
    ap.add_argument("--cam-zoom", type=float, default=CAM_ZOOM, help=f"camera zoom (default {CAM_ZOOM})")
    ap.add_argument("--font", help="TTF/OTF font for captions and titles")
    ap.add_argument("--whisper-model", default=os.path.expanduser("~/.cache/whisper/ggml-small.bin"))
    ap.add_argument("--caption-lead", type=float, default=CAPTION_LEAD,
                    help=f"show captions this many seconds earlier than the transcript (default {CAPTION_LEAD})")
    ap.add_argument("--no-snap-cuts", action="store_true",
                    help="keep cut points exactly as planned (default: move cuts in speech to nearby silence)")
    ap.add_argument("--debug", action="store_true", help="also write <out>.align.json and <out>.contact.jpg")
    ap.add_argument("--keep-temp", action="store_true", help="keep intermediate files")
    args = ap.parse_args(argv)

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            ap.error(f"{tool} not found on PATH")

    plan_path = Path(args.plan).expanduser().resolve()
    plan = json.loads(plan_path.read_text())
    global BASE
    BASE = base_for_plan(plan_path)
    src = plan.get("source", {})
    cfg = Settings(
        edited=resolve_path(args.edited or src.get("edited"), BASE / "edited.mp4"),
        raw_dir=resolve_path(args.raw_dir or src.get("raw_dir"), BASE / "raw"),
        hooks_dir=resolve_path(args.hooks_dir, BASE / "hooks-filmed"),
        words_path=resolve_path(args.words, BASE / "work" / "words.json"),
        cache_dir=BASE / "work" / "cache",
        panel_crop=tuple(int(v) for v in args.panel_crop.split(",")) if args.panel_crop else None,
        cam_center=args.cam_center,
        cam_zoom=args.cam_zoom,
        font=args.font,
        whisper_model=Path(args.whisper_model).expanduser(),
        debug=args.debug,
        keep_temp=args.keep_temp,
        caption_lead=args.caption_lead,
        snap_cuts=not args.no_snap_cuts,
    )
    if not cfg.edited.exists():
        ap.error(f"edited video not found: {cfg.edited}")
    builder = ReelBuilder(cfg)
    reels = {r["id"]: r for r in plan["reels"]}

    jobs: list[tuple[dict, Optional[dict], Path]] = []
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else BASE / "out"
    if args.all:
        for r in plan["reels"]:
            hooks = renderable_hooks(r, cfg.hooks_dir)
            if not hooks:
                jobs.append((r, None, out_dir / f"{r['id']}.mp4"))
            for h in hooks:
                jobs.append((r, h, out_dir / f"{r['id']}-{h['id']}.mp4"))
    else:
        if not args.reel or args.reel not in reels:
            ap.error(f"--reel must be one of {', '.join(reels)} (or use --all)")
        r = reels[args.reel]
        if args.hook:
            h = next((x for x in r.get("hooks", []) if x["id"] == args.hook), None)
            if h is None:
                ap.error(f"reel {r['id']} has no hook {args.hook}")
        else:
            hs = renderable_hooks(r, cfg.hooks_dir)
            h = hs[0] if hs else None
        default = out_dir / (f"{r['id']}-{h['id']}.mp4" if h else f"{r['id']}.mp4")
        jobs.append((r, h, Path(args.out).expanduser() if args.out else default))

    failures = 0
    for r, h, out in jobs:
        try:
            rep = builder.build(plan, r, h, out.resolve())
            s = rep.get("summary")
            if s:
                log(f"  alignment: weighted conf {s['weighted_conf']}, min {s['min_run_conf']}, "
                    f"fallback {s['fallback_seconds']}s")
        except Exception as exc:  # keep going in --all mode
            failures += 1
            log(f"!! {out.name}: {exc}")
            if not args.all:
                raise
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
