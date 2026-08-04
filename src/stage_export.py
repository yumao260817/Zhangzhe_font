import cv2
import numpy as np

from .gb2312 import level1_chars
from .paths import FONTS, PROCESSED

UPEM = 2048
GRID = 256


def imread_gray(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def polys_for(bin_img):
    scale = UPEM / GRID
    mask = np.uint8(bin_img > 0) * 255
    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for ci, cnt in enumerate(cnts):
        raw = cv2.approxPolyDP(cnt, 0.7, True).reshape(-1, 2)
        if len(raw) < 3:
            continue
        pts = [[float(x) * scale, (GRID - float(y)) * scale] for x, y in raw]
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


def run(fmt="ttf"):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    FONTS.mkdir(parents=True, exist_ok=True)
    glyphs = {}
    glyph_order = [".notdef"]
    cmap = {}
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    glyphs[".notdef"] = TTGlyphPen(None).glyph()
    for ch in level1_chars():
        p = PROCESSED / f"{ch}.png"
        if not p.exists():
            continue
        im = imread_gray(p)
        if im is None:
            continue
        bin_img = cv2.threshold(im, 160, 255, cv2.THRESH_BINARY_INV)[1]
        polys = polys_for(bin_img)
        if not polys:
            continue
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

    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    metrics = {g: (UPEM, 0) for g in glyph_order}
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=UPEM, descent=0)
    fb.setupOS2(usWeightClass=400, usWidthClass=5, fsSelection=0x40, typoAscender=UPEM, typoDescender=0, sTypoLineGap=0, usWinAscent=UPEM, usWinDescent=0)
    fb.setupNameTable({
        "familyName": "Zhangzhe",
        "styleName": "Regular",
        "uniqueFontIdentifier": "Zhangzhe-Regular",
        "fullName": "Zhangzhe",
        "psName": "Zhangzhe-Regular",
    })
    fb.setupPost()
    out = FONTS / "Zhangzhe.ttf"
    fb.save(str(out))
    print(f"导出完成: {len(glyphs)} 字 -> {out}")