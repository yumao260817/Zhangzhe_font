import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

from .gb2312 import level1_chars
from .paths import GENERATED, MODELS, PROCESSED, STDSRC
from .stage_train import GeneratorUNet

GRID = 128


def imread_gray(path: Path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def run(model_path: str | None = None, chars: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ck_path = Path(model_path) if model_path else MODELS / "pix2pix_final.pt"
    if not ck_path.exists():
        print(f"模型不存在: {ck_path}，请先训练")
        return
    G = GeneratorUNet(1, 1).to(dev)
    ck = torch.load(ck_path, map_location=dev)
    G.load_state_dict(ck["G"])
    G.eval()
    print(f"模型加载: {ck_path}")

    targets = chars or level1_chars()
    GENERATED.mkdir(parents=True, exist_ok=True)
    n_src, n_hand = 0, 0
    with torch.no_grad():
        for ch in targets:
            sp = STDSRC / f"{ch}.png"
            if not sp.exists():
                continue
            src = cv2.resize(imread_gray(sp), (GRID, GRID)).astype(np.float32) / 255.0
            x = torch.tensor(src[None, None]).to(dev)
            out = G(x)[0, 0].clamp(0, 1).cpu().numpy()
            out_img = (out * 255).astype(np.uint8)
            _, out_img = cv2.threshold(out_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            out_img = cv2.morphologyEx(out_img, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
            GENERATED.joinpath(f"{ch}.png").write_bytes(
                cv2.imencode(".png", out_img)[1].tobytes()
            )
            n_src += 1
            if (PROCESSED / f"{ch}.png").exists():
                n_hand += 1
    print(f"生成完成: {n_src} 字 -> {GENERATED} (其中已有手写样本 {n_hand} 字已覆盖)")
