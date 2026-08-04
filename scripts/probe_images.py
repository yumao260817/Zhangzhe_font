import sys
from collections import Counter
from pathlib import Path

from PIL import Image

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/target")
exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
files = [p for p in root.rglob("*") if p.suffix.lower() in exts]

sizes = Counter()
modes = Counter()
examples = []
errs = []
for p in files:
    try:
        with Image.open(p) as im:
            im = im.convert("L")
            w, h = im.size
            sizes[(w, h)] += 1
            modes[im.mode] += 1
            hist = im.histogram()
            total = w * h
            dark = sum(hist[:128]) / total
            light = sum(hist[129:]) / total
            denom = dark + light
            ratio = dark / denom if denom else 0.5
            examples.append((p.name, w, h, round(dark, 3), round(ratio, 3)))
    except Exception as e:
        errs.append((p.name, str(e)))

print(f"文件总数: {len(files)}")
print("尺寸分布(前 12):", sizes.most_common(12))
print("模式分布:", modes)
print("读取失败:", len(errs), errs[:5])
print("正墨比例示例(前 30):")
for name, w, h, darkpix, ratio in examples[:30]:
    print(f"  {name}: {w}x{h} dark_ratio={ratio}")
if examples:
    drs = sorted(x[4] for x in examples)
    print("ink ratio min/max/median:", drs[0], drs[-1], drs[len(drs) // 2])
