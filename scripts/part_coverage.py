import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
decomp = json.loads(Path("data/components/decomp.json").read_text(encoding="utf-8"))

from src.gb2312 import level1_chars
from src.paths import PROCESSED

hand = [c for c in level1_chars() if (PROCESSED / f"{c}.png").exists()]
hand_set = set(hand)
print("手写样本数:", len(hand_set))

need = [c for c in level1_chars() if c not in hand_set]
print("缺失字:", len(need))

# 部件 -> 出现在多少手写字中
part_in_hand = Counter()
for ch in hand_set:
    for part in decomp[ch]["leaves"]:
        part_in_hand[part] += 1

# 缺失字用到的部件，哪些在手写里没有
missing_part = set()
need_parts = Counter()
for ch in need:
    for part in decomp[ch]["leaves"]:
        need_parts[part] += 1
        if part not in part_in_hand:
            missing_part.add(part)

print("缺失字用到的部件种类:", len(need_parts))
print("其中手写库内没有的部件:", len(missing_part))
miss = sorted(missing_part)
print("缺部件示例:", "".join(miss[:40]))