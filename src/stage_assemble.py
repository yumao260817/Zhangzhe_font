import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

from .gb2312 import level1_chars
from .paths import COMPONENTS, ASSEMBLED, STDSRC
from .stage_components import parse_ids
from .stage_parts import _split_box, GRID, imread_gray, std_bbox

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _pix2pix_infer(part_img: np.ndarray, model: torch.nn.Module) -> np.ndarray:
    img = cv2.resize(part_img, (128, 128)).astype(np.float32) / 255.0
    t = torch.from_numpy(img).unsqueeze(0).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        out = model(t).squeeze().cpu().numpy()
    out = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    _, out = cv2.threshold(out, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, kernel)
    return out


def _load_model():
    model_path = Path("models/pix2pix_final.pt")
    if not model_path.exists():
        return None
    from .stage_train import GeneratorUNet

    model = GeneratorUNet(1, 1).to(DEVICE)
    ck = torch.load(model_path, map_location=DEVICE, weights_only=True)
    model.load_state_dict(ck["G"])
    model.eval()
    return model


def _load_part(part: str, parts_dir: Path, meta: dict):
    """加载部件真件图 + 其标准 bbox"""
    fp = parts_dir / f"U{ord(part):04X}.png"
    if fp.exists():
        img = imread_gray(fp)
        if img is not None:
            info = meta.get(part, {})
            return img, info
    return None, None


def _place(canvas: np.ndarray, part_img: np.ndarray, box, std_bb, pad=0.10):
    """按标准 bbox 精确放置: 保持部件纵横比缩放到标准大小, 放在标准位置"""
    x, y, w, h = box
    if std_bb:
        sx0, sy0, sx1, sy1 = std_bb
        tw, th = sx1 - sx0 + 1, sy1 - sy0 + 1
        tx, ty = sx0, sy0
    else:
        tw, th = w, h
        tx, ty = x, y
    # 缩放: 保持纵横比, 长边适配目标
    ph, pw = part_img.shape
    scale = min(tw / pw, th / ph)
    nw, nh = max(1, int(pw * scale)), max(1, int(ph * scale))
    nw, nh = min(nw, tw), min(nh, th)
    resized = cv2.resize(part_img, (nw, nh), interpolation=cv2.INTER_AREA)
    # 按目标 bbox 中心放置, 轻微内缩避免溢出
    cx, cy = tx + tw // 2, ty + th // 2
    px, py = cx - nw // 2, cy - nh // 2
    px = max(0, min(px, GRID - nw))
    py = max(0, min(py, GRID - nh))
    canvas[py : py + nh, px : px + nw] = resized


def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    decomp = json.loads((COMPONENTS / "decomp.json").read_text(encoding="utf-8"))
    meta = json.loads((COMPONENTS / "parts_meta.json").read_text(encoding="utf-8"))
    hand_set = {c for c in level1_chars() if (Path("data/processed") / f"{c}.png").exists()}
    need = [c for c in level1_chars() if c not in hand_set]
    parts_dir = COMPONENTS / "parts"
    ASSEMBLED.mkdir(parents=True, exist_ok=True)
    model = _load_model()
    if model is None:
        print("pix2pix 模型未加载，缺失部件将使用标准字形兜底")
    part_cache = {}

    stats = {"total": 0, "hand": 0, "pix2pix": 0, "std": 0, "missing": 0}
    for ch in need:
        entry = decomp.get(ch)
        if not entry:
            continue
        std_img = imread_gray(STDSRC / f"{ch}.png")
        if std_img is None:
            continue
        node = parse_ids(entry["ids"])
        boxes = []
        _split_box(node, 0, 0, GRID, GRID, boxes)
        canvas = np.full((GRID, GRID), 255, dtype=np.uint8)
        for part, box in boxes:
            std_bb = std_bbox(std_img, box)
            key = (part, tuple(box))
            cached = part_cache.get(key)
            if cached is None:
                img, info = _load_part(part, parts_dir, meta)
                if img is not None:
                    src = "hand"
                else:
                    # 兜底: 标准部件渲染 + pix2pix
                    from .stage_stdsrc import render_char

                    std_part = render_char(part, 128)
                    if model is not None:
                        img = _pix2pix_infer(std_part, model)
                        src = "pix2pix"
                    else:
                        img = std_part
                        src = "std"
                part_cache[key] = (img, src)
            else:
                img, src = cached
            stats[src] = stats.get(src, 0) + 1
            _place(canvas, img, box, std_bb)
        cv2.imencode(".png", canvas)[1].tofile(str(ASSEMBLED / f"{ch}.png"))
        stats["total"] += 1
        if stats["total"] % 200 == 0:
            print(f"  拼装进度: {stats['total']}/{len(need)}")

    print(f"拼装完成: {stats['total']} 字")
    print(
        f"  真件部件: {stats['hand']}, pix2pix: {stats.get('pix2pix', 0)}, 标准: {stats.get('std', 0)}"
    )
    (COMPONENTS / "assemble_stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")