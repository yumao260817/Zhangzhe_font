import json
import sys
from pathlib import Path

import cv2
import numpy as np

from .gb2312 import level1_chars
from .paths import COMPONENTS, PROCESSED, STDSRC, GENERATED
from .stage_components import Node, parse_ids, is_leaf, IDC

GRID = 128
decomp = {}


def imread_gray(path: Path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def _split_box(node: Node, x, y, w, h, collect):
    if is_leaf(node):
        collect.append((node.idc, (x, y, w, h)))
        return
    if node.idc in ("⿰", "⿲"):  # 左右/左中右: 垂直切分
        n = len(node.kids)
        for i, k in enumerate(node.kids):
            if i == n - 1:
                kx, kw = x + int(w * i / n), w - int(w * i / n)
            else:
                kx, kw = x + int(w * i / n), int(w / n)
            _split_box(k, kx, y, kw, h, collect)
    elif node.idc in ("⿱", "⿳"):  # 上下/上中下: 水平切分
        n = len(node.kids)
        for i, k in enumerate(node.kids):
            if i == n - 1:
                ky, kh = y + int(h * i / n), h - int(h * i / n)
            else:
                ky, kh = y + int(h * i / n), int(h / n)
            _split_box(k, x, ky, w, kh, collect)
    elif node.idc == "⿹":  # 右上包围: 左低右高斜切—近似右上顶框
        k0, k1 = node.kids
        _split_box(k0, x, y, int(w * 0.7), int(h * 0.7), collect)
        _split_box(k1, x + int(w * 0.7), y, w - int(w * 0.7), h, collect)
    elif node.idc == "⿸":  # 左上包围
        k0, k1 = node.kids
        _split_box(k0, x, y, int(w * 0.7), h, collect)
        _split_box(k1, x + int(w * 0.6), y, w - int(w * 0.6), int(h * 0.7), collect)
    else:  # ⿻ 整体等: 不细分, 交合并
        for k in node.kids:
            _split_box(k, x, y, w, h, collect)


def parts_of(ch: str):
    node = parse_ids(decomp.get(ch, {}).get("ids", ""))
    boxes = []
    _split_box(node, 0, 0, GRID, GRID, boxes)
    return boxes


def crop_box(img, box, pad_ratio=0.04):
    x, y, w, h = box
    sub = img[max(0, y - 2) : min(GRID, y + h + 2), max(0, x - 2) : min(GRID, x + w + 2)]
    if sub.size == 0:
        return None
    pts = np.where(sub < 128)
    if len(pts[0]) == 0:
        return None
    y0, y1 = pts[0].min(), pts[0].max()
    x0, x1 = pts[1].min(), pts[1].max()
    pad = max(1, int((y1 - y0) * pad_ratio))
    y0, y1 = max(0, y0 - pad), min(sub.shape[0] - 1, y1 + pad)
    x0, x1 = max(0, x0 - pad), min(sub.shape[1] - 1, x1 + pad)
    return sub[y0 : y1 + 1, x0 : x1 + 1]


def _to_square(img):
    h, w = img.shape
    s = max(h, w)
    out = np.full((s, s), 255, np.uint8)
    y0, x0 = (s - h) // 2, (s - w) // 2
    out[y0 : y0 + h, x0 : x0 + w] = img
    return out


def _img_sim(img, ref):
    a = cv2.resize(img, (64, 64))
    b = cv2.resize(ref, (64, 64))
    a = a.astype(np.float64) / 255
    b = b.astype(np.float64) / 255
    return -float(np.abs(a - b).mean())


def fit_bbox_in_grid(box, ref_box, ref_bbox):
    """按标准字形中部件相对其粗格的偏移/比例, 把手写部件 bbox 校准到标准比例。

    ref_box: 标准字形中该部件的粗格 (x,y,w,h) 在 128 网格
    ref_bbox: 标准字形中该部件的实际笔迹 bbox (x0,y0,x1,y1) 相对全图
    返回手写粗格内对应的笔迹 bbox 偏移。
    """
    rx, ry, rw, rh = ref_box
    bx0, by0, bx1, by1 = ref_bbox
    # 部件实际范围相对粗格的归一化偏移与占比
    fx0 = (bx0 - rx) / rw
    fy0 = (by0 - ry) / rh
    fw = (bx1 - bx0 + 1) / rw
    fh = (by1 - by0 + 1) / rh
    return (rx, ry, int(rw * fw) + 1, int(rh * fh) + 1, fx0, fy0)


def std_bbox(img, box):
    """在 128 网格的粗格内求实际笔迹 bbox"""
    x, y, w, h = box
    sub = img[y : y + h, x : x + w]
    if sub.size == 0:
        return None
    pts = np.where(sub < 128)
    if len(pts[0]) == 0:
        return None
    y0, y1 = pts[0].min(), pts[0].max()
    x0, x1 = pts[1].min(), pts[1].max()
    return (x + x0, y + y0, x + x1, y + y1)


def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()


def build() -> None:
    global decomp
    decomp = json.loads((COMPONENTS / "decomp.json").read_text(encoding="utf-8"))
    parts_dir = COMPONENTS / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    meta = {}
    seen = {}
    for ch in level1_chars():
        hp = PROCESSED / f"{ch}.png"
        if not hp.exists():
            continue
        sp = STDSRC / f"{ch}.png"
        if not sp.exists():
            continue
        hand_img = imread_gray(hp)
        std_img = imread_gray(sp)
        if hand_img is None or std_img is None:
            continue
        if hand_img.shape[0] != GRID:
            hand_img = cv2.resize(hand_img, (GRID, GRID), interpolation=cv2.INTER_AREA)
        boxes = parts_of(ch)
        for part, box in boxes:
            if part not in decomp[ch]["leaves"]:
                continue
            key = part
            if key not in seen:
                seen[key] = []
            seen[key].append((hand_img, std_img, box, ch))

    parts_meta = {}
    for part, lst in seen.items():
        best = None
        best_key = None
        for hand_img, std_img, box, ch in lst:
            bb = std_bbox(std_img, box)
            if bb is None:
                continue
            x0, y0, x1, y1 = bb
            # 手写: 按标准 bbox 的偏移和粗格裁剪
            rx, ry, rw, rh = box
            fx0 = (x0 - rx) / rw
            fy0 = (y0 - ry) / rh
            fw = (x1 - x0 + 1) / rw
            fh = (y1 - y0 + 1) / rh
            hx0 = int(rx + fx0 * rw)
            hy0 = int(ry + fy0 * rh)
            hw = max(2, int(rw * fw))
            hh = max(2, int(rh * fh))
            hpart = hand_img[hy0 : hy0 + hh, hx0 : hx0 + hw]
            if hpart.size == 0:
                continue
            # 裁掉手写部件内部多余白边
            pts = np.where(hpart < 128)
            if len(pts[0]) == 0:
                continue
            py0, py1 = pts[0].min(), pts[0].max()
            px0, px1 = pts[1].min(), pts[1].max()
            hpart = hpart[py0 : py1 + 1, px0 : px1 + 1]
            if hpart.size == 0:
                continue
            spart = std_img[y0 : y1 + 1, x0 : x1 + 1]
            score = _img_sim(hpart, spart)
            if best is None or score > best[0]:
                best = (score, hpart, (hw, hh), x0, y0, x1, y1)
                best_key = (ch, box)
        if best is None:
            continue
        _, hpart, (hw, hh), x0, y0, x1, y1 = best
        fn = parts_dir / f"U{ord(part):04X}.png"
        cv2.imencode(".png", hpart)[1].tofile(str(fn))
        parts_meta[part] = {
            "src": best_key[0],
            "w": int(hpart.shape[1]),
            "h": int(hpart.shape[0]),
            "std_box": [int(x) for x in (x0, y0, x1, y1)],
            "sample": len(lst),
        }
    print(f"部件库构建完成: {len(parts_meta)} 个部件真件 -> {parts_dir}")
    (COMPONENTS / "parts_meta.json").write_text(
        json.dumps(parts_meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return parts_meta


