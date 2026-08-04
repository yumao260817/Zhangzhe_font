import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
src = Path("data/stdsrc")
hand = Path("data/processed")
gen = Path("data/generated")

from src.gb2312 import level1_chars

gap = [c for c in level1_chars() if not (hand / f"{c}.png").exists()]
print("未见字总数:", len(gap))
sample = [c for c in gap if c in "禾示主异家场话夜象狮榆阁麻魔灶倔谕蝎谕尼西亚藏哀"]
sample = gap[:40] if not sample else sample

# 每字两列: 标准字形 | 生成
cols, cell, pad = 2, 128, 6
rows = len(sample)
w = cols * (cell + pad) + pad
h = rows * (cell + pad) + pad
img = np.full((h, w), 255, np.uint8)

def load(p):
    im = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    return cv2.resize(im, (cell, cell)) if im is not None else np.full((cell, cell), 255, np.uint8)

def paste(im, r, c):
    y0 = pad + r * (cell + pad)
    x0 = pad + c * (cell + pad)
    img[y0 : y0 + cell, x0 : x0 + cell] = im

for r, ch in enumerate(sample):
    paste(load(src / f"{ch}.png"), r, 0)
    paste(load(gen / f"{ch}.png"), r, 1)

out = Path("output/reports/gap_preview.png")
cv2.imencode(".png", img)[1].tofile(str(out))
print("未见字对比生成:", out, "| 列: 标准 | 生成")
print("字例:", "".join(sample[:20]))