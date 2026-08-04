import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np

from .gb2312 import level1_chars
from .paths import TARGET, PROCESSED, REPORTS
from .store import connect

GRID = 256
EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}

_extra = re.compile(r"^[\u4e00-\u9fff]$")


def _char_from_name(name: str) -> str | None:
    stem = Path(name).stem
    stem = re.sub(r"[\s\-_()（）\[\]【】]+$", "", stem)
    if _extra.match(stem):
        return stem
    return None


def _imread_gray(path: Path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def _load_char(path: Path):
    img = _imread_gray(path)
    if img is None:
        raise ValueError("无法读取")
    h, w = img.shape
    total = h * w
    dark = int(np.count_nonzero(img < 128))
    if dark / total > 0.5:
        img = 255 - img
        dark = total - dark
    if dark < max(2, int(total * 0.0005)):
        raise ValueError("无墨迹像素")
    blur = cv2.GaussianBlur(img, (5, 5), 0)
    _, binimg = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binimg = cv2.morphologyEx(binimg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.where(binimg < 128)
    if len(ys) == 0:
        raise ValueError("无墨迹像素")
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    margin = max(1, int((y1 - y0) * 0.06))
    y0, y1 = max(0, y0 - margin), min(h - 1, y1 + margin)
    x0, x1 = max(0, x0 - margin), min(w - 1, x1 + margin)
    crop = img[y0 : y1 + 1, x0 : x1 + 1]
    side = max(crop.shape)
    square = np.full((side, side), 255, np.uint8)
    oy, ox = (side - crop.shape[0]) // 2, (side - crop.shape[1]) // 2
    square[oy : oy + crop.shape[0], ox : ox + crop.shape[1]] = crop
    out = cv2.resize(square, (GRID, GRID), interpolation=cv2.INTER_AREA)
    ratio = int(np.count_nonzero(out < 128)) / (GRID * GRID)
    if not (0.005 <= ratio <= 0.55):
        raise ValueError(f"墨迹占比异常: {ratio:.3f}")
    return out, ratio


def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    files = [p for p in TARGET.rglob("*") if p.suffix.lower() in EXTS]
    ok, bad = [], []
    conn = connect()
    stats = {"total": len(files), "ok": 0, "bad": 0, "uniq_chars": 0}
    for p in files:
        ch = _char_from_name(p.name)
        if ch is None:
            bad.append({"file": str(p), "reason": "文件名非单个汉字"})
            continue
        try:
            out, ratio = _load_char(p)
        except Exception as e:
            bad.append({"file": str(p), "reason": str(e)})
            continue
        PROCESSED.joinpath(f"{ch}.png").write_bytes(
            cv2.imencode(".png", out)[1].tobytes()
        )
        conn.execute(
            "UPDATE glyphs SET stage='source', candidate_path=?, scores=? "
            "WHERE char=?",
            (str(p), json.dumps({"ink_ratio": round(ratio, 3)}), ch),
        )
        ok.append(ch)
        stats["ok"] += 1

    ok_set = set(ok)
    stats["bad"] = len(bad)
    covered = [c for c in level1_chars() if c in ok_set]
    gap = [c for c in level1_chars() if c not in ok_set]
    stats["uniq_chars"] = len(ok_set)
    stats["covered"] = len(covered)
    stats["gap"] = len(gap)
    conn.commit()
    conn.close()

    report = {"stats": stats, "covered_chars": covered, "gap_chars": gap, "rejected": bad}
    outfile = REPORTS / "coverage.json"
    outfile.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    gapfile = REPORTS / "gap.txt"
    gapfile.write_text("\n".join(gap), encoding="utf-8")

    print(f"预处理完成: 成功 {stats['ok']} 张 / 失败 {stats['bad']} 张")
    print(f"去重后覆盖 {stats['uniq_chars']} 字 / 3755 目标, 缺口 {stats['gap']} 字")
    print(f"失败明细与缺口列表: {REPORTS}")
    render_contact_sheets(covered)


def render_contact_sheets(chars: list[str]) -> list[str]:
    cols, cell, pad = 20, 32, 2
    per_page = 500
    pages = []
    sheets_dir = REPORTS / "contact"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(chars), per_page):
        batch = chars[start : start + per_page]
        rows = (len(batch) + cols - 1) // cols
        w = cols * (cell + pad) + pad
        h = rows * (cell + pad) + pad
        sheet = np.full((h, w), 255, np.uint8)
        for i, ch in enumerate(batch):
            p = PROCESSED / f"{ch}.png"
            if not p.exists():
                continue
            img = _imread_gray(p)
            if img is None:
                continue
            r, c = divmod(i, cols)
            y, x = pad + r * (cell + pad), pad + c * (cell + pad)
            sheet[y : y + cell, x : x + cell] = cv2.resize(img, (cell, cell))
        fname = sheets_dir / f"contact_{start // per_page:03d}.png"
        cv2.imencode(".png", sheet)[1].tofile(str(fname))
        pages.append(str(fname))
    if pages:
        print(f"接触表拼版: {len(pages)} 页, 查看 {sheets_dir}")
    return pages
