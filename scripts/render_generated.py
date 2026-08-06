import random
import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
gen = Path("data/generated")
hand = Path("data/processed")
out = Path("output/reports/generated_preview.png")

random.seed(7)
chars = sorted(p.stem for p in gen.glob("*.png"))
sample = random.sample(chars, 100)
cols = 10
cell = 96
pad = 4
rows = (len(sample) + cols - 1) // cols
w = cols * (cell + pad) + pad
h = rows * (cell + pad) + pad
img = np.full((h, w), 255, np.uint8)
for i, ch in enumerate(sample):
    src = hand / f"{ch}.png" if (hand / f"{ch}.png").exists() else gen / f"{ch}.png"
    im = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if im is None:
        continue
    im = cv2.resize(im, (cell, cell))
    r, c = divmod(i, cols)
    y0 = pad + r * (cell + pad)
    x0 = pad + c * (cell + pad)
    img[y0 : y0 + cell, x0 : x0 + cell] = im
# 用边框颜色区分来源: 绿=手写, 红=生成
out_arr = np.stack([img, img, img], -1)
for i, ch in enumerate(sample):
    src = hand / f"{ch}.png" if (hand / f"{ch}.png").exists() else gen / f"{ch}.png"
    r, c = divmod(i, cols)
    y0 = pad + r * (cell + pad)
    x0 = pad + c * (cell + pad)
    color = (0, 200, 0) if src.parent == hand else (0, 0, 220)
    out_arr[y0, x0 : x0 + cell, :] = color
    out_arr[y0 + cell - 1, x0 : x0 + cell, :] = color
    out_arr[y0 : y0 + cell, x0, :] = color
    out_arr[y0 : y0 + cell, x0 + cell - 1, :] = color
cv2.imencode(".png", out_arr)[1].tofile(str(out))
print("预览生成:", out)