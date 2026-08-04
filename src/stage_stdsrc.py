import sys
from pathlib import Path

import cv2
import numpy as np

from .gb2312 import level1_chars
from .paths import PROCESSED, STDSRC

GRID = 128


_FONT = None


def _font_picker():
    global _FONT
    if _FONT is not None:
        return _FONT
    candidates = [
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    for c in candidates:
        if Path(c).exists():
            _FONT = c
            return c
    raise RuntimeError("未找到系统标准中文字体")


def _render(ch: str, font_path: str, size: int = 400) -> np.ndarray:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("L", (size, size), 255)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(font_path, int(size * 0.78))
    bbox = d.textbbox((0, 0), ch, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    ox = (size - tw) // 2 - bbox[0]
    oy = (size - th) // 2 - bbox[1]
    d.text((ox, oy), ch, font=f, fill=0)
    return np.array(img)


def render_char(ch: str, size: int = 128) -> np.ndarray:
    font_path = _font_picker()
    arr = _render(ch, font_path, size=size * 3)
    arr = cv2.resize(arr, (size, size), interpolation=cv2.INTER_AREA)
    return arr


def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    STDSRC.mkdir(parents=True, exist_ok=True)
    from PIL import Image

    missing = 0
    for ch in level1_chars():
        arr = render_char(ch, GRID)
        Image.fromarray(arr).save(STDSRC / f"{ch}.png")
        if not (PROCESSED / f"{ch}.png").exists():
            missing += 1
    print(f"标准字形渲染完成: {len(level1_chars())} 字 -> {STDSRC}")
    print(f"其中缺手写样本(供生成)的字: {missing} 字")
