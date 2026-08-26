"""字体元数据规范化与生成后自检（独立模块，供 stage_export 调用）。

职责：
- OS/2：version 4、fsType=0（Installable Embedding）、fsSelection=Regular、
  typo 度量、PANOSE、Unicode Range / Code Page Range 按实际 cmap 自动重算
- name 表：Family/Subfamily/Full Name/PostScript Name/Typographic Family，
  以及版权/许可证（nameID 0/13/14，OFL 1.1 条款 2 要求字体文件内携带授权信息）
- validate_font：重新加载 TTF 后执行兼容性自检
"""

from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.O_S_2f_2 import Panose

FAMILY = "Zhangzhe"
STYLE = "Regular"
FULL_NAME = f"{FAMILY} {STYLE}"
PS_NAME = f"{FAMILY}-{STYLE}"

# 版权与许可证（与 output/fonts/OFL.txt 保持一致；OFL 1.1）
COPYRIGHT = "Copyright (c) 2026, Zhangzhe Font Project, with Reserved Font Name Zhangzhe."
LICENSE_NAME = "This Font Software is licensed under the SIL Open Font License, Version 1.1."
LICENSE_URL = "https://openfontlicense.org"

# PANOSE（手写字体 → Script 类）
PANOSE = dict(
    bFamilyType=4,  # Script
    bSerifStyle=3,  # Informal Script
    bWeight=5,      # Medium
    bProportion=0,
    bContrast=0,
    bStrokeVariation=0,
    bArmStyle=0,
    bLetterForm=0,
    bMidline=0,
    bXHeight=0,
)


def setup_os2(fb: FontBuilder, upem: int) -> None:
    """OS/2 规范化：v4 + Installable Embedding + Regular + typo 度量 + PANOSE。"""
    fb.setupOS2(
        version=4,
        usWeightClass=400,
        usWidthClass=5,
        fsSelection=0x40,  # REGULAR
        sTypoAscender=int(upem * 0.8),
        sTypoDescender=-(upem // 5),
        sTypoLineGap=upem // 10,
        usWinAscent=upem,
        usWinDescent=upem // 5,
    )
    os2 = fb.font["OS/2"]
    os2.fsType = 0  # Installable Embedding（个人/项目字体默认；有授权策略再改）
    os2.panose = Panose(**PANOSE)
    # 按实际 cmap 自动重算，禁止固定 0 或手写死值
    os2.recalcUnicodeRanges(fb.font, pruneOnly=False)
    os2.recalcCodePageRanges(fb.font, pruneOnly=False)
    # 修正 Code Page Range：fontTools 的 calcCodePageRanges 用「ㄅ」触发 bit 18（简体
    # GB2312/GBK）、用「央」触发 bit 20（繁体 Big5）。本字体是简体字库（GB2312 一级，
    # 无注音符号），会被误判为仅支持繁体——Windows/Word 据此在 IME 合成时回退宋体。
    # 与系统字体对齐：SimSun/雅黑均为 bit 18。显式去掉繁体位、补上简体位。
    bits = os2.getCodePageRanges()
    bits.discard(20)  # Big5 繁体：本字体不含繁体字
    bits.add(18)      # GB2312/GBK 简体中文
    os2.setCodePageRanges(bits)


def setup_names(fb: FontBuilder) -> None:
    """name 表：Family/Subfamily/Full Name/PS Name/Typographic Family + 版权/许可证。"""
    fb.setupNameTable(
        {
            "familyName": FAMILY,
            "styleName": STYLE,
            "uniqueFontIdentifier": PS_NAME,
            "fullName": FULL_NAME,
            "psName": PS_NAME,
            "copyright": COPYRIGHT,
            "licenseDescription": LICENSE_NAME,
            "licenseInfoURL": LICENSE_URL,
        }
    )
    name = fb.font["name"]
    for nid, val in ((16, FAMILY), (17, STYLE)):  # Typographic Family / Subfamily
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)


REQUIRED_TABLES = ("cmap", "name", "OS/2", "head", "hhea", "maxp", "glyf", "hmtx", "post")


def validate_font(path: str, expected_chars=None) -> list:
    """重新加载 TTF 并自检，返回错误列表（空 = 通过）。"""
    font = TTFont(path)
    errors = []

    for t in REQUIRED_TABLES:
        if t not in font:
            errors.append(f"缺少表 {t}")

    cmap = font.getBestCmap()
    if not cmap:
        errors.append("getBestCmap() 为空")
    else:
        if expected_chars:
            missing = [c for c in expected_chars if ord(c) not in cmap]
            if missing:
                errors.append(f"cmap 缺字 {len(missing)} 个: {''.join(missing[:20])}")
        if not errors and font.getGlyphOrder() and ".notdef" not in font.getGlyphOrder():
            errors.append("缺少 .notdef")
        if font.getGlyphOrder() and not all(
            g.startswith("uni") or g == "zz_missing" for g in font.getGlyphOrder()[1:]
        ):
            bad = [g for g in font.getGlyphOrder()[1:] if not (g.startswith("uni") or g == "zz_missing")][:10]
            errors.append(f"glyph 命名不规范（应 uniXXXX）: {bad}")

    # 结构一致性（Word 实例化字体的硬性校验）
    maxp = font["maxp"]
    order = font.getGlyphOrder()
    if maxp.numGlyphs != len(order):
        errors.append(f"maxp.numGlyphs={maxp.numGlyphs} != glyphOrder {len(order)}")
    hmtx = font["hmtx"]
    hhea = font["hhea"]
    if len(hmtx.metrics) != maxp.numGlyphs:
        errors.append(f"hmtx 条目 {len(hmtx.metrics)} != numGlyphs {maxp.numGlyphs}")
    if hhea.numberOfHMetrics != maxp.numGlyphs:
        errors.append(f"hhea.numberOfHMetrics={hhea.numberOfHMetrics} != numGlyphs（Word 兼容需全量）")
    loca = font["loca"]
    if len(loca.locations) != maxp.numGlyphs + 1:
        errors.append(f"loca 条目 {len(loca.locations)} != numGlyphs+1")
    glyf = font["glyf"]
    nd = glyf[".notdef"] if ".notdef" in glyf else None
    if nd is None or nd.numberOfContours == 0:
        errors.append(".notdef 为空轮廓（应含简单方块轮廓）")
    try:
        for gn in order:
            glyf[gn].getCoordinates(glyf)  # 逐个 glyph 读取，异常即视为生成失败
    except Exception as e:
        errors.append(f"glyf 读取异常: {e}")

    os2 = font["OS/2"]
    if os2.fsType != 0:
        errors.append(f"fsType={os2.fsType}，应为 0 (Installable Embedding)")
    if os2.sTypoAscender == 0 or os2.sTypoDescender == 0:
        errors.append("typoAscender/typoDescender 为 0，Word 将拒绝")
    if os2.usWinAscent == 0 or os2.usWinDescent == 0:
        errors.append("usWinAscent/usWinDescent 为 0")
    if not (os2.fsSelection & 0x40):
        errors.append("fsSelection 缺少 REGULAR 位")
    ranges = os2.getUnicodeRanges()
    if not any(r in ranges for r in (59, 47, 74)):  # CJK 相关位
        errors.append(f"Unicode Range 未声明 CJK: {sorted(ranges)}")
    cpr = os2.getCodePageRanges()
    if 18 not in cpr:  # bit 18 = GB2312/GBK 简体中文（Word/IME 判定简体中文支持的关键位）
        errors.append(f"Code Page Range 未声明简体中文(bit18): {sorted(cpr)}")
    if 20 in cpr:  # bit 20 = Big5 繁体，本字体为简体字库不应声明
        errors.append(f"Code Page Range 误声明繁体(bit20): {sorted(cpr)}")

    name = font["name"]
    if name.getDebugName(1) != FAMILY:
        errors.append(f"Family='{name.getDebugName(1)}' 应为 {FAMILY}")
    if name.getDebugName(2) != STYLE:
        errors.append(f"Subfamily='{name.getDebugName(2)}' 应为 {STYLE}")
    if name.getDebugName(4) != FULL_NAME:
        errors.append(f"FullName='{name.getDebugName(4)}' 应为 {FULL_NAME}")
    if name.getDebugName(6) != PS_NAME:
        errors.append(f"PostScriptName='{name.getDebugName(6)}' 应为 {PS_NAME}")
    if name.getDebugName(16) != FAMILY:
        errors.append("缺少 Typographic Family (nameID 16)")
    if name.getDebugName(17) != STYLE:
        errors.append("缺少 Typographic Subfamily (nameID 17)")
    if not name.getDebugName(0) or "Copyright" not in name.getDebugName(0):
        errors.append("缺少版权声明 (nameID 0)")
    if name.getDebugName(13) != LICENSE_NAME:
        errors.append("许可证声明 (nameID 13) 与 OFL 1.1 不一致")
    if name.getDebugName(14) != LICENSE_URL:
        errors.append("许可证 URL (nameID 14) 与 OFL 1.1 不一致")

    return errors