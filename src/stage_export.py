import shutil
from datetime import datetime

import cv2
import numpy as np

from .font_metadata import setup_names, setup_os2, validate_font
from .gb2312 import level1_chars
from .paths import FONTS, PROCESSED

UPEM = 2048
GRID = 256


def imread_gray(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def polys_for(bin_img, scale=UPEM / GRID):
    mask = np.uint8(bin_img > 0) * 255
    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for ci, cnt in enumerate(cnts):
        raw = cv2.approxPolyDP(cnt, 0.7, True).reshape(-1, 2)
        if len(raw) < 3:
            continue
        h = bin_img.shape[0]
        pts = [[float(x) * scale, (h - float(y)) * scale] for x, y in raw]
        area = 0.0
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            area += x0 * y1 - x1 * y0
        if hier[0][ci][3] == -1 and area < 0.0:
            pts.reverse()
        polys.append(pts)
    return polys


def _approved_pngs() -> dict:
    """char -> 最新 approved 候选的 png_path"""
    from . import store

    with store.db() as conn:
        rows = conn.execute(
            "SELECT c.char AS char, c.png_path AS path FROM candidates c "
            "JOIN (SELECT char, MAX(id) AS mid FROM candidates WHERE status='approved' GROUP BY char) m "
            "ON c.id = m.mid"
        ).fetchall()
    return {r["char"]: r["path"] for r in rows if r["path"]}


def run(fmt="ttf"):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    FONTS.mkdir(parents=True, exist_ok=True)
    approved = _approved_pngs()

    def add_glyph(ch: str, gray, size: int):
        """按图像实际高度缩放轮廓到 UPEM 网格"""
        bin_img = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)[1]
        polys = polys_for(bin_img, scale=UPEM / size)
        if not polys:
            return False
        name = f"uni{ord(ch):04X}"
        pen = TTGlyphPen(None)
        for pts in polys:
            pen.moveTo(pts[0])
            for pt in pts[1:]:
                pen.lineTo(pt)
            pen.closePath()
        glyphs[name] = pen.glyph()
        glyph_order.append(name)
        cmap[ord(ch)] = name
        return True

    glyphs = {}
    glyph_order = [".notdef"]
    cmap = {}
    # .notdef 必须含简单轮廓（空 .notdef 可能导致 Word/OTS 校验失败）
    nd_pen = TTGlyphPen(None)
    nd_pen.moveTo((0, 0))
    nd_pen.lineTo((0, 128))
    nd_pen.lineTo((128, 128))
    nd_pen.lineTo((128, 0))
    nd_pen.closePath()
    glyphs[".notdef"] = nd_pen.glyph()
    hand_count = cand_count = 0
    for ch in level1_chars():
        p = PROCESSED / f"{ch}.png"
        if p.exists():
            im = imread_gray(p)
            if im is None:
                continue
            if add_glyph(ch, im, im.shape[0]):
                hand_count += 1
            continue
        # 缺手写：合并人工审核通过的候选（512 透明 PNG，取 alpha 通道）
        cand_p = approved.get(ch)
        if not cand_p:
            continue
        from PIL import Image as PILImage

        try:
            img = PILImage.open(cand_p).convert("RGBA")
        except Exception:
            continue
        alpha = np.asarray(img)[:, :, 3]
        if add_glyph(ch, 255 - alpha, alpha.shape[0]):
            cand_count += 1

    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    metrics = {g: (UPEM, 0) for g in glyph_order}
    fb.setupHorizontalMetrics(metrics)
    # 垂直度量：基线在字底，下方留 20% 降部空间，行高合理
    fb.setupHorizontalHeader(ascent=UPEM, descent=-UPEM // 5)
    setup_os2(fb, UPEM)
    setup_names(fb)
    fb.setupPost()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = FONTS / f"Zhangzhe_{ts}.ttf"
    fb.save(str(out))
    print(f"导出完成: 手写 {hand_count} 字 + 人工候选 {cand_count} 字, 共 {len(glyphs)} 字 -> {out}")

    # 二次处理：fontTools 编译 hmtx 时会把尾部相同 advance 合并为 numberOfHMetrics=1
    # （Word 对 numberOfHMetrics < numGlyphs 的字体有已知兼容 bug），展开为全量记录
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables.DefaultTable import DefaultTable
    import struct

    font = TTFont(str(out))
    num = len(font.getGlyphOrder())
    raw = struct.pack(">" + "Hh" * num, *[
        v for gn in font.getGlyphOrder() for v in (font["hmtx"].metrics[gn][0], 0)
    ])
    hmtx = DefaultTable("hmtx")
    hmtx.data = raw
    font["hmtx"] = hmtx
    font["hhea"].numberOfHMetrics = num
    font.save(str(out))
    print(f"hmtx 展开为全量: numberOfHMetrics={num}")

    # 生成后自检：重新加载并验证，失败即抛错
    chars = [chr(k) for k in cmap]
    errors = validate_font(str(out), expected_chars=chars)
    if errors:
        raise RuntimeError("字体自检失败:\n" + "\n".join(errors))
    print("字体自检通过: 表齐全, cmap/name/OS2 一致, fsType=0, CJK Range/CodePage 已声明")

    # 自检通过后同步最新副本为固定文件名（release/安装用）
    fixed = FONTS / "Zhangzhe.ttf"
    shutil.copy2(str(out), str(fixed))
    print(f"已同步固定副本 -> {fixed}")