"""GB2312 一级字的拼音索引（同音字查询）。

用 pypinyin 生成 {拼音: [字...]} 映射，模块级懒加载缓存。
"""

from pypinyin import Style, lazy_pinyin

from .gb2312 import level1_chars

_cache: dict[str, list[str]] | None = None


def pinyin_map() -> dict[str, list[str]]:
    global _cache
    if _cache is None:
        m: dict[str, list[str]] = {}
        for ch in level1_chars():
            py = lazy_pinyin(ch, style=Style.NORMAL)[0]
            m.setdefault(py, []).append(ch)
        _cache = m
    return _cache


def homophones(pinyin: str) -> list[str]:
    """按拼音查同音字；不区分大小写，返回按一级字序排列的列表"""
    py = (pinyin or "").strip().lower()
    if not py or not py.isascii():
        return []
    m = pinyin_map()
    return list(m.get(py, []))
