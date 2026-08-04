import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.paths import COMPONENTS, PROCESSED, STDSRC
from src.stage_components import parse_ids
from src.stage_parts import _split_box, GRID, imread_gray


def find_by_codepoint(parts_dir: Path, part: str):
    fp = parts_dir / f"U{ord(part):04X}.png"
    return fp


def rebuild_same(part_imgs, boxes):
    canvas = np.full((GRID, GRID), 255, dtype=np.uint8)
    for part, (x, y, w, h) in boxes:
        img = part_imgs.get(part)
        if img is None:
            continue
        img = cv2.resize(img, (max(1, w), max(1, h)), interpolation=cv2.INTER_AREA)
        canvas[y : y + h, x : x + w] = img
    return canvas


def ssim(a, b):
    a = a.astype(np.float64) / 255.0
    b = b.astype(np.float64) / 255.0
    C = (0.01 * 255 / 255) ** 2
    mu_a, mu_b = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    return ((2 * mu_a * mu_b + C) * (2 * cov + C)) / ((mu_a**2 + mu_b**2 + C) * (va + vb + C))


decomp = json.loads((COMPONENTS / "decomp.json").read_text(encoding="utf-8"))
parts_dir = COMPONENTS / "parts"

# 从手写库里裁剪某字的各部件（模仿 build_parts 但按该字自身裁剪）
scores = []
for ch in sorted(set(p.stem for p in PROCESSED.glob("*.png"))):
    entry = decomp.get(ch)
    if not entry:
        continue
    hand = imread_gray(PROCESSED / f"{ch}.png")
    if hand is None:
        continue
    hand = cv2.resize(hand, (GRID, GRID), interpolation=cv2.INTER_AREA)
    node = parse_ids(entry["ids"])
    boxes = []
    _split_box(node, 0, 0, GRID, GRID, boxes)
    parts = {}
    for part, (x, y, w, h) in boxes:
        if part in parts:
            continue
        img = hand[y:y+h, x:x+w]
        # 裁剪多余白边
        img = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA)
        parts[part] = img
    rebuilt = rebuild_same(parts, boxes)
    sc = ssim(rebuilt, hand)
    scores.append((ch, sc))

scores.sort(key=lambda t: t[1])
bad = scores[:10]
mean = np.mean([s for _, s in scores])
print(f"用自身部件重拼的 SSIM: mean={mean:.3f}")
print("最差的 10 字:", "".join(c for c, _ in bad), [round(s, 3) for _, s in bad])
good = [s >= 0.5 for _, s in scores]
print(f"SSIM≥0.5 占比: {sum(good)}/{len(scores)} = {sum(good)/len(scores):.1%}")