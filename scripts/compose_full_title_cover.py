#!/usr/bin/env python3
"""Compose a cover whose left-side title is the article title verbatim.

The cover skill allows two main-title lines plus two subtitle lines. A full
article title (22-45 chars) does not fit two lines, so this script packs the
exact title across all four slots, in order, and only then tries the article
subtitle in whatever space is left. Rendering is delegated to the cover
skill's compose_cover.py, so typography, palette and safe-field rules are
unchanged.

Usage:
  python compose_full_title_cover.py --input bg.png --output cover.png \
    --theme 12 --eyebrow "信使引擎 / CMC 工艺" \
    --title "<article title>" [--subtitle "<article subtitle>"] --footer ""
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

def find_cover_skill() -> Path:
    for base in (Path.home() / ".claude" / "skills",
                 Path.home() / ".config" / "magpie" / "library" / "skills"):
        candidate = base / "wechat-cover-design"
        if candidate.exists():
            return candidate
    raise SystemExit("wechat-cover-design skill not found")


SKILL = find_cover_skill()
sys.path.insert(0, str(SKILL / "scripts"))
from compose_cover import bilingual_width, load_font  # noqa: E402

MAX_WIDTH = 500
FONT_ZH = SKILL / "assets" / "fonts" / "Hanchan-Zhengkai-Big5.ttf"
FONT_EN = SKILL / "assets" / "fonts" / "PreTesto_it.ttf"
# (max width, size): title lines are set at their minimum permitted size so the
# renderer never has to reject a line; subtitle lines likewise.
SLOTS = [(MAX_WIDTH, 52), (MAX_WIDTH, 52), (MAX_WIDTH, 26), (MAX_WIDTH, 26)]
SCRATCH = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def measure(text: str, size: int) -> int:
    zh = load_font(FONT_ZH, size, 1.0)
    en = load_font(FONT_EN, size, 1.0)
    return bilingual_width(SCRATCH, text, zh, en)


PUNCT = "：，。；、,;:!?！？"
LEADING_BAD = "：，。；、,;:!?！？）)】」』"


def tokens(text: str) -> list[str]:
    """Atomic units: Latin/number runs stay whole; spaces and punctuation stick left."""
    raw = re.findall(r"[A-Za-z0-9%+./→\-:]+|\s+|.", text)
    out: list[str] = []
    for tk in raw:
        if (tk.isspace() or tk in PUNCT) and out:
            out[-1] += tk
        else:
            out.append(tk)
    units = ("个百分点", "小时", "mol%", "kDa", "nm", "mL", "mg", "µg", "°C", "℃",
             "倍", "个", "天", "点", "种", "项", "例", "名", "条", "批", "h")
    merged = list(out)
    i = 0
    while i < len(merged):
        if re.fullmatch(r"[0-9][0-9.,%→]*\s*", merged[i]):
            acc, j, hit, best_len = "", i + 1, None, 0
            while j < len(merged) and len(acc) < 6:
                acc += merged[j].lstrip()
                plain = acc.strip().rstrip(PUNCT)
                if plain in units and len(plain) > best_len:
                    best_len, hit = len(plain), j
                if not any(u.startswith(plain) for u in units):
                    break
                j += 1
            if hit is not None:
                merged[i] = merged[i] + "".join(merged[i + 1:hit + 1])
                del merged[i + 1:hit + 1]
        i += 1
    return [t for t in merged if t.strip()]


def width_of(text: str, size: int) -> int:
    return measure(text, size)


def best_split(text: str, slots: list[tuple[int, int]], start: int, k: int) -> list[str] | None:
    """DP split of text into exactly k lines, minimising raggedness."""
    toks = tokens(text)
    n = len(toks)
    if n == 0 or k <= 0 or start + k > len(slots):
        return None
    prefix = [""]
    for t in toks:
        prefix.append(prefix[-1] + t)
    INF = float("inf")
    dp = [[INF] * (n + 1) for _ in range(k + 1)]
    back = [[0] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0
    for line in range(1, k + 1):
        budget, size = slots[start + line - 1]
        for j in range(1, n + 1):
            for i in range(line - 1, j):
                if dp[line - 1][i] == INF:
                    continue
                seg = prefix[j][len(prefix[i]):]
                if seg[:1] in LEADING_BAD or seg[:1] in "）)】」』":
                    continue
                w = width_of(seg.rstrip(PUNCT), size)
                if w > budget:
                    continue
                slack = (budget - w) / budget
                cost = dp[line - 1][i] + slack * slack
                if i > 0:
                    prev = toks[i - 1]
                    pch = prev.strip()[-1:] if prev.strip() else ""
                    if pch in "第约近超达仅共":
                        continue
                    if prev[-1:].isspace() or prev[-1:] in PUNCT:
                        pass
                    elif prev[-1:] in "的和与或在为是把及而却不非未无可很更最较":
                        cost += 0.45
                    else:
                        cost += 0.10
                if j == n and slack > 0.62:  # orphan last line
                    cost += 2.0
                if cost < dp[line][j]:
                    dp[line][j] = cost
                    back[line][j] = i
    if dp[k][n] == INF:
        return None
    lines, j = [], n
    for line in range(k, 0, -1):
        i = back[line][j]
        lines.append(prefix[j][len(prefix[i]):].strip())
        j = i
    return list(reversed(lines)), dp[k][n]


def pack(text: str, slot_start: int, slots: list[tuple[int, int]]) -> list[str] | None:
    """Fit text into as few slots as possible, preferring 1 then 2 then 3 then 4 lines."""
    best = None
    for k in range(1, len(slots) - slot_start + 1):
        r = best_split(text, slots, slot_start, k)
        if not r:
            continue
        lines, cost = r
        total = cost + 0.30 * k
        if best is None or total < best[0]:
            best = (total, lines)
    return best[1] if best else None


def trim(text: str) -> str:
    return re.sub(r"[：，、,;；]+$", "", text.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--theme", required=True, type=int)
    ap.add_argument("--eyebrow", default="信使引擎")
    ap.add_argument("--title", required=True, help="article title, verbatim")
    ap.add_argument("--subtitle", default="", help="article subtitle, used only if space remains")
    ap.add_argument("--footer", default="")
    ap.add_argument("--lines", default="", help="explicit lines separated by | ; overrides auto-split")
    args = ap.parse_args()

    if args.lines:
        lines = [l.strip() for l in args.lines.split("|")]
        if len(lines) > 4:
            print("ERROR: at most four cover lines", file=sys.stderr)
            return 2
        for idx, line in enumerate(lines):
            budget, size = SLOTS[idx]
            if line and measure(line, size) > budget:
                print(f"ERROR: line {idx+1} too wide: {line}", file=sys.stderr)
                return 3
    else:
        lines = pack(args.title, 0, SLOTS)
        if not lines:
            print("ERROR: title cannot fit four cover lines", file=sys.stderr)
            return 2
        if len(lines) < 4 and args.subtitle:
            extra = pack(args.subtitle, len(lines), SLOTS)
            if extra:
                lines += extra

    lines = [trim(l) for l in lines]
    title1 = lines[0]
    title2 = lines[1] if len(lines) > 1 else ""
    sub1 = lines[2] if len(lines) > 2 else ""
    sub2 = lines[3] if len(lines) > 3 else ""

    cmd = [
        sys.executable, str(SKILL / "scripts" / "compose_cover.py"),
        "--input", args.input, "--output", args.output, "--theme", str(args.theme),
        "--eyebrow", args.eyebrow, "--title", title1,
        "--title-line2", title2, "--subtitle-line1", sub1,
        "--subtitle-line2", sub2, "--footer", args.footer,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout + r.stderr, file=sys.stderr)
        return r.returncode
    print(f"{title1} | {title2} | {sub1} | {sub2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
