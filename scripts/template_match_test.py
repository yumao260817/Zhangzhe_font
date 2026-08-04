import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.paths import STDSRC
from src.stage_stdsrc import render_char

GRID = 128


def imread_gray(path: Path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def multi_scale_match(std_char, tpl):
    """多尺度模板匹配，返回 (x, y, w, h) 最佳框（128 网格）"""
    best = None
    for scale in np.arange(0.45, 1.05, 0.05):
        t = cv2.resize(tpl, (int(128 * scale), int(128 * scale)), interpolation=cv2.INTER_AREA)
        if t.shape[0] >= std_char.shape[0] or t.shape[1] >= std_char.shape[1]:
            continue
        res = cv2.matchTemplate(std_char, t, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        if best is None or maxv > best[0]:
            best = (maxv, maxloc[0], maxloc[1], t.shape[1], t.shape[0])
    return best


def bbox_of(img, pad=2):
    pts = np.where(img < 128)
    if len(pts[0]) == 0:
        return None
    y0, y1, x0, x1 = pts[0].min(), pts[0].max(), pts[1].min(), pts[1].max()
    return (max(0, x0 - pad), max(0, y0 - pad), min(GRID - 1, x1 + pad), min(GRID - 1, y1 + pad))


# 测试: 用单部件标准模板在整字标准图中定位, 对比投影/均匀切分
tests = [("们", "亻"), ("埋", "土"), ("森", "木"), ("羽", "习"), ("秘", "禾"), ("树", "又")]
for ch, part in tests:
    std = imread_gray(STDSRC / f"{ch}.png")
    tpl = render_char(part, 128)
    res = multi_scale_match(std, tpl)
    print(f"{ch}: 部件 {part} 匹配分数={res[0]:.3f} 框=({res[1]},{res[2]},{res[3]},{res[4]})")