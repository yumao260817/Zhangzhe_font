import random
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ttf = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/fonts/Zhangzhe.ttf")
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/reports/font_preview.png")

cmap = TTFont(str(ttf)).getBestCmap()
chars = [chr(cp) for cp in cmap if 0x4E00 <= cp <= 0x9FFF]
random.seed(2026)
sample = random.sample(chars, 100)

cols, rows, cell = 10, 10, 64
img = Image.new("L", (cols * cell, rows * cell), 255)
d = ImageDraw.Draw(img)
fontc = ImageFont.truetype(str(ttf), 52)
for i, ch in enumerate(sample):
    x, y = (i % cols) * cell, (i // cols) * cell
    d.text((x + 6, y + 4), ch, font=fontc, fill=0)
img.save(str(out))
print(f"预览图已生成: {out} 使用 {len(sample)} 字")