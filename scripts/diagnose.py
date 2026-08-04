import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
gen = Path("data/generated")
hand = Path("data/processed")
src = Path("data/stdsrc")

stats = {"empty": 0, "black": 0, "lowink": 0, "normal": 0}
sample_empty = []
sample_normal = []
for p in gen.glob("*.png"):
    im = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if im is None:
        stats["empty"] += 1
        continue
    ink = (im < 128).mean()
    if ink < 0.001:
        stats["empty"] += 1
        if len(sample_empty) < 8:
            sample_empty.append(p.stem)
    elif ink > 0.9:
        stats["black"] += 1
    elif ink < 0.02:
        stats["lowink"] += 1
    else:
        stats["normal"] += 1
        if len(sample_normal) < 12:
            sample_normal.append(p.stem)
print("生成图统计:", stats)
print("空图示例:", sample_empty)
print("正常示例:", sample_normal)

print("\n=== 训练集内(有手写)字 逐字差异 ===")
pairs = [c for c in sample_normal if (hand / f"{c}.png").exists()][:6]
for ch in pairs:
    g = cv2.imdecode(np.fromfile(str(gen / f"{ch}.png"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    h = cv2.imdecode(np.fromfile(str(hand / f"{ch}.png"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    s = cv2.imdecode(np.fromfile(str(src / f"{ch}.png"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    print(f"{ch}: src_ink={(s<128).mean():.3f} hand_ink={(h<128).mean():.3f} gen_ink={(g<128).mean():.3f}"
          f" gen_mean={g.mean():.0f} hand_mean={h.mean():.0f}")

print("\n=== 输入输出域检查 ===")
im = cv2.imdecode(np.fromfile(str(src / "一.png"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
print("stdsrc 一.png: min/max", im.min(), im.max(), "ink%", (im < 128).mean())
im2 = cv2.imdecode(np.fromfile(str(hand / "一.png"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
print("processed 一.png: min/max", im2.min(), im2.max(), "ink%", (im2 < 128).mean())
im3 = cv2.imdecode(np.fromfile(str(gen / "一.png"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
print("generated 一.png: min/max", im3.min(), im3.max(), "unique", np.unique(im3)[:8])