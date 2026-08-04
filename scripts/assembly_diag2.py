import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.paths import COMPONENTS, PROCESSED, STDSRC, ASSEMBLED
from src.stage_components import parse_ids
from src.stage_parts import _split_box, GRID, imread_gray, std_bbox
from src.stage_assemble import _load_part, _place


def ssim(a, b):
    a = a.astype(np.float64) / 255.0
    b = b.astype(np.float64) / 255.0
    C = 0.01 * 0.01
    mu_a, mu_b = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    return ((2 * mu_a * mu_b + C) * (2 * cov + C)) / ((mu_a**2 + mu_b**2 + C) * (va + vb + C))


decomp = json.loads((COMPONENTS / "decomp.json").read_text(encoding="utf-8"))
meta = json.loads((COMPONENTS / "parts_meta.json").read_text(encoding="utf-8"))
parts_dir = COMPONENTS / "parts"

# 用新管线对 1255 有手写字做"自身部件重拼"——评估新放置逻辑是否自洽
scores = []
for ch in sorted(set(p.stem for p in PROCESSED.glob("*.png"))):
    entry = decomp.get(ch)
    if not entry or not (STDSRC / f"{ch}.png").exists() or not (PROCESSED / f"{ch}.png").exists():
        continue
    hand = imread_gray(PROCESSED / f"{ch}.png")
    std_img = imread_gray(STDSRC / f"{ch}.png")
    if hand is None or std_img is None:
        continue
    hand = cv2.resize(hand, (GRID, GRID), interpolation=cv2.INTER_AREA)
    node = parse_ids(entry["ids"])
    boxes = []
    _split_box(node, 0, 0, GRID, GRID, boxes)
    canvas = np.full((GRID, GRID), 255, dtype=np.uint8)
    for part, box in boxes:
        bb = std_bbox(std_img, box)
        img, info = _load_part(part, parts_dir, meta)
        if img is None:
            continue
        _place(canvas, img, box, bb)
    scores.append((ch, ssim(canvas, hand)))

scores.sort(key=lambda t: t[1])
print(f"新管线自身重拼 SSIM: mean={np.mean([s for _, s in scores]):.3f}")
print("最差 10 字:", "".join(c for c, _ in scores[:10]))
print("最好 5 字:", "".join(c for c, _ in scores[-5:]))
print(f"SSIM>=0.5: {sum(1 for _, s in scores if s >= 0.5)}/{len(scores)}")