import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.paths import COMPONENTS, STDSRC, PROCESSED
from src.stage_components import parse_ids
from src.stage_parts import _split_box, GRID, imread_gray, std_bbox

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_model():
    from src.stage_train import GeneratorUNet
    model = GeneratorUNet(1, 1).to(DEVICE)
    ck = torch.load("models/pix2pix_final.pt", map_location=DEVICE, weights_only=True)
    model.load_state_dict(ck["G"])
    model.eval()
    return model


def infer(model, img128):
    if img128.max() > 1.5:
        img128 = img128.astype(np.float32) / 255.0
    t = torch.tensor(img128[None, None]).float().to(DEVICE)
    with torch.no_grad():
        out = model(t)[0, 0].clamp(0, 1).cpu().numpy()
    out = (out * 255).astype(np.uint8)
    _, out = cv2.threshold(out, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return out


def place(canvas, img, x0, y0, w, h):
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    canvas[y0 : y0 + h, x0 : x0 + w] = img


def main():
    decomp = json.loads((COMPONENTS / "decomp.json").read_text(encoding="utf-8"))
    model = load_model()
    test_chars = "众磊品想看听喝唱铜钉银翅望登融毅辩镶楚篮"

    out_dir = Path("output/reports/contact")
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(test_chars)
    canvas = np.full((n * GRID, GRID * 4 + 8), 255, dtype=np.uint8)
    pad = 8  # 部件裁剪 padding

    for i, ch in enumerate(test_chars):
        entry = decomp.get(ch)
        if not entry:
            print(f"{ch}: 无拆解")
            continue
        std = imread_gray(STDSRC / f"{ch}.png")
        if std is None:
            continue
        y = i * GRID
        canvas[y : y + GRID, 0:GRID] = std
        node = parse_ids(entry["ids"])
        boxes = []
        _split_box(node, 0, 0, GRID, GRID, boxes)
        assembled = np.full((GRID, GRID), 255, dtype=np.uint8)
        for part, box in boxes:
            bb = std_bbox(std, box)
            if bb is None:
                continue
            x0, y0, x1, y1 = bb
            pw, ph = x1 - x0 + 1, y1 - y0 + 1
            # 带 padding 裁剪标准部件
            cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
            cx1, cy1 = min(GRID - 1, x1 + pad), min(GRID - 1, y1 + pad)
            crop = std[cy0 : cy1 + 1, cx0 : cx1 + 1]
            # 居中放入 128x128
            big = np.full((GRID, GRID), 255, dtype=np.uint8)
            ox, oy = (GRID - crop.shape[1]) // 2, (GRID - crop.shape[0]) // 2
            big[oy : oy + crop.shape[0], ox : ox + crop.shape[1]] = crop
            gen = infer(model, big)
            # 裁出生成结果的有效区域(去白边)
            pts = np.where(gen < 128)
            if len(pts[0]) == 0:
                continue
            gy0, gy1 = pts[0].min(), pts[0].max()
            gx0, gx1 = pts[1].min(), pts[1].max()
            part_img = gen[gy0 : gy1 + 1, gx0 : gx1 + 1]
            # 缩放适配标准 bbox
            scale = min(pw / part_img.shape[1], ph / part_img.shape[0])
            nw, nh = int(part_img.shape[1] * scale), int(part_img.shape[0] * scale)
            nw, nh = max(1, nw), max(1, nh)
            resized = cv2.resize(part_img, (nw, nh), interpolation=cv2.INTER_AREA)
            px = x0 + (pw - nw) // 2
            py = y0 + (ph - nh) // 2
            assembled[py : py + nh, px : px + nw] = resized
        canvas[y : y + GRID, GRID + 2 : 2 * GRID + 2] = assembled
        # 标准字形整字过模型(整字直出对比)
        whole = infer(model, std.astype(np.float32) / 255.0)
        canvas[y : y + GRID, 2 * GRID + 4 : 3 * GRID + 4] = whole
        hand = PROCESSED / f"{ch}.png"
        if hand.exists():
            h = imread_gray(hand)
            if h is not None:
                canvas[y : y + GRID, 3 * GRID + 6 : 4 * GRID + 6] = cv2.resize(h, (GRID, GRID))

    fp = out_dir / "pix2pix_parts_exp.png"
    cv2.imencode(".png", canvas)[1].tofile(str(fp))
    print(f"实验接触表: {fp}  列: 标准 | 部件pix2pix拼装 | 整字pix2pix | 手写原版(如有)")


if __name__ == "__main__":
    main()