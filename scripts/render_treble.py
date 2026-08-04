import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
src = Path("data/stdsrc")
hand = Path("data/processed")
gen = Path("data/generated")

known = ["一", "上", "不", "丁", "七"]
# 未见字: 从 gap 取简单结构
from src.gb2312 import level1_chars

gap = [c for c in level1_chars() if not (hand / f"{c}.png").exists()]
gaps = [c for c in gap if c in ["主", "示", "禾", "由", "且", "家", "场", "话"]]
chars = known + gaps

cell = 96
cols = 4  # 标准 | 手写 | 生成 | 生成(二值)
rows = len(chars)
pad = 8
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

for r, ch in enumerate(chars):
    s = load(src / f"{ch}.png")
    h_ = load(hand / f"{ch}.png") if (hand / f"{ch}.png").exists() else np.full((cell, cell), 200, np.uint8)
    g = load(gen / f"{ch}.png")
    gb = cv2.threshold(g, 127, 255, cv2.THRESH_BINARY)[1]
    paste(s, r, 0)
    paste(h_, r, 1)
    paste(g, r, 2)
    paste(gb, r, 3)

out = Path("output/reports/treble_preview.png")
cv2.imencode(".png", img)[1].tofile(str(out))
print("三列对比生成:", out, "| 列: 标准|手写|生成|生成二值")
print("未见字样本:", gaps)