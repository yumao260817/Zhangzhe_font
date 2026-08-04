import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ssim(a, b):
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    mu_a, mu_b = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    return ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a**2 + mu_b**2 + c1) * (va + vb + c2))


def load(path):
    im = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    return cv2.resize(im, (128, 128))


gen = Path("data/generated")
hand = Path("data/processed")
src = Path("data/stdsrc")

chars = ["一", "上", "不", "看", "翼", "敢", "发", "言"]
print("=== 已知字: 生成 vs 手写 vs 标准 (SSIM) ===")
for ch in chars:
    g = load(gen / f"{ch}.png")
    h = load(hand / f"{ch}.png") if (hand / f"{ch}.png").exists() else None
    s = load(src / f"{ch}.png")
    gh = ssim(g, h) if h is not None else float("nan")
    gs = ssim(g, s)
    hs = ssim(h, s) if h is not None else float("nan")
    print(f"{ch}: gen-vs-hand={gh:.3f} gen-vs-std={gs:.3f} hand-vs-std={hs:.3f}")

print("\n=== 生成图之间互相似度 (判断塌缩) ===")
glist = [load(gen / f"{c}.png") for c in ["一", "上", "不", "看", "翼", "敢", "发", "言"]]
m = np.zeros((len(glist), len(glist)))
for i in range(len(glist)):
    for j in range(len(glist)):
        if i < j:
            m[i, j] = m[j, i] = ssim(glist[i], glist[j])
np.fill_diagonal(m, 1)
print("生成图互相似度矩阵:")
print(np.round(m, 3))

print("\n=== 手写之间互相似度 (对照) ===")
hlist = [load(hand / f"{c}.png") for c in ["一", "上", "不", "看", "翼", "敢", "发", "言"]]
hmat = np.ones((8, 8))
for i in range(8):
    for j in range(i + 1, 8):
        hmat[i, j] = hmat[j, i] = ssim(hlist[i], hlist[j])
print(np.round(hmat, 3))