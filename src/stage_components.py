import json
import sys
from pathlib import Path

from .gb2312 import level1_chars
from .paths import COMPONENTS, DATA

IDC = {
    "⿰": "lr",   # 左右
    "⿱": "tb",   # 上下
    "⿲": "lrr",  # 左中右
    "⿳": "tbb",  # 上中下
    "⿹": "tr",   # 右上包围
    "⿸": "tl",   # 左上包围
    "⿺": "br",   # 左下包围
    "⿻": "ov",   # 整体
}


class Node:
    __slots__ = ("idc", "kids")

    def __init__(self, idc=""):
        self.idc = idc
        self.kids = []


def _parse(text: str, i: int = 0):
    ch = text[i]
    if ch in IDC:
        n = Node(ch)
        for _ in range(2 if ch not in ("⿲", "⿳") else 3):
            k, i = _parse(text, i + 1)
            n.kids.append(k)
        return n, i
    return Node(ch), i


def parse_ids(text: str):
    node, _ = _parse(text.strip())
    return node


def is_leaf(n: Node) -> bool:
    return not n.kids


def leaf_chars(n: Node) -> list[str]:
    if is_leaf(n):
        return [n.idc]
    out = []
    for k in n.kids:
        out += leaf_chars(k)
    return out


def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data_file = Path("third_party") / "GB2312-ids" / "GB2312-ids.txt"
    if not data_file.exists():
        print(f"缺少拆字数据: {data_file}")
        return
    table = {}
    for line in data_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue
        code, ch, ids = parts[0], parts[1], parts[2]
        if len(ch) != 1:
            continue
        try:
            node = parse_ids(ids)
            leaves = leaf_chars(node)
            if leaves:
                table[ch] = {"code": code, "ids": ids, "leaves": leaves, "count": len(leaves)}
        except Exception:
            continue

    covered = [c for c in level1_chars() if c in table]
    COMPONENTS.mkdir(parents=True, exist_ok=True)
    out = COMPONENTS / "decomp.json"
    out.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"拆字表构建完成: {len(table)} 字 (GB2312 一级覆盖 {len(covered)}/{len(level1_chars())})")
    uniq = sorted({c for v in table.values() for c in v["leaves"]})
    print(f"不重复部件数: {len(uniq)}")
    (COMPONENTS / "parts.txt").write_text("\n".join(uniq), encoding="utf-8")