import sys
from pathlib import Path
import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

hand_dir = Path("data/processed")
ass_dir = Path("data/assembled")
std_dir = Path("data/stdsrc")
out_dir = Path("output/reports/contact")
out_dir.mkdir(parents=True, exist_ok=True)

GRID = 128
ROW = 20

def imread_gray(path):
    data = path.read_bytes()
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

need = sorted(set(p.stem for p in ass_dir.glob("*.png")))
print(f"拼装字: {len(need)}")

# 分块渲染接触表
for batch_idx in range(0, len(need), 500):
    batch = need[batch_idx:batch_idx+500]
    n = len(batch)
    cols = min(ROW, n)
    rows = (n + cols - 1) // cols
    canvas = np.full((rows * GRID, cols * GRID * 3 + 4), 255, dtype=np.uint8)

    for i, ch in enumerate(batch):
        r, c = i // cols, i % cols
        x = c * (GRID * 3 + 4) + 2
        y = r * GRID
        std = imread_gray(std_dir / f"{ch}.png")
        if std is not None:
            canvas[y:y+GRID, x:x+GRID] = std
        ass = imread_gray(ass_dir / f"{ch}.png")
        if ass is not None:
            canvas[y:y+GRID, x+GRID+2:x+GRID*2+2] = ass
        hp = hand_dir / f"{ch}.png"
        if hp.exists():
            hand = imread_gray(hp)
            if hand is not None:
                canvas[y:y+GRID, x+GRID*2+4:x+GRID*3+4] = hand

    fp = out_dir / f"assemble_batch{batch_idx//500}.png"
    cv2.imencode(".png", canvas)[1].tofile(str(fp))
    print(f"  接触表: {fp} ({n} 字)")

print("全部接触表生成完成")