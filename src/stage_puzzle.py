import hashlib
import json
import uuid
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from .paths import PUZZLE_PIECES, PUZZLE_CANDIDATES
from .gb2312 import level1_chars
from . import store

LEVEL1 = set(level1_chars())
GRID = 512


def _imread_bytes(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data)).convert("RGBA")


def save_piece(data: bytes) -> dict:
    """保存上传的透明 PNG 部件，返回元信息"""
    img = _imread_bytes(data)
    h, w = img.height, img.width

    def _rgb(_c):
        return "".join(f"{x:02x}" for x in (_c if isinstance(_c, tuple) else (_c,)))

    digest = hashlib.sha256(data).hexdigest()[:16]
    PUZZLE_PIECES.mkdir(parents=True, exist_ok=True)
    fn = PUZZLE_PIECES / f"{digest}.png"
    if not fn.exists():
        fn.write_bytes(data)
    return {
        "id": digest,
        "url": f"/api/pieces/{digest}/img",
        "w": w,
        "h": h,
    }


def piece_url(pid: str) -> str:
    return f"/api/pieces/{pid}/img"


def _compose_rgba(pieces: list[dict]) -> np.ndarray:
    """按 layering 顺序合成 RGBA 画布（GRID×GRID，透明底）"""
    canvas = np.zeros((GRID, GRID, 4), dtype=np.uint8)
    for layer in pieces:
        pid = layer["piece_id"]
        x, y = int(layer.get("x", 0)), int(layer.get("y", 0))
        w, h = int(layer.get("scale_w", 0)), int(layer.get("scale_h", 0))
        angle = float(layer.get("angle", 0))
        flip = bool(layer.get("flip", False))
        fp = PUZZLE_PIECES / f"{pid}.png"
        if not fp.exists():
            continue
        img = _imread_bytes(fp.read_bytes())
        if w > 0 and h > 0:
            img = img.resize((w, h), Image.LANCZOS)
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if angle:
            img = img.rotate(-angle, expand=True, resample=Image.BICUBIC)
        arr = np.array(img, dtype=np.uint8)
        ah, aw = arr.shape[:2]
        sx = max(0, x)
        sy = max(0, y)
        ex = min(GRID, x + aw)
        ey = min(GRID, y + ah)
        if sx >= ex or sy >= ey:
            continue
        src = arr[sy - y : ey - y, sx - x : ex - x]
        dst = canvas[
            sy:ey,
            sx:ex,
        ]
        alpha = (src[:, :, 3:4].astype(np.float32)) / 255.0
        dst[:] = (dst.astype(np.float32) * (1 - alpha) + src[:, :, :4].astype(np.float32) * alpha).astype(
            np.uint8
        )
    return canvas


def render_png(pieces: list[dict]) -> bytes:
    canvas = _compose_rgba(pieces)
    out = Image.fromarray(canvas, "RGBA")
    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _svg_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_svg(pieces: list[dict], png_b64: str) -> str:
    """生成 SVG：白底 + 各部件 <image> 图层 + 合成结果图层，保持拼装位置"""
    parts = []
    for layer in pieces:
        pid = layer["piece_id"]
        x = int(layer.get("x", 0))
        y = int(layer.get("y", 0))
        w = int(layer.get("scale_w", 0))
        h = int(layer.get("scale_h", 0))
        angle = float(layer.get("angle", 0))
        flip = bool(layer.get("flip", False))
        fp = PUZZLE_PIECES / f"{pid}.png"
        if not fp.exists() or w <= 0 or h <= 0:
            continue
        import base64

        b64 = base64.b64encode(fp.read_bytes()).decode()
        tr = []
        cx, cy = w / 2.0, h / 2.0
        if flip:
            tr.append(f"translate({x + w},{y}) scale(-1,1)")
            piece_img = _imread_bytes(fp.read_bytes())
            if angle:
                # 翻转后绕自身中心旋转（与 PNG 合成近似一致）
                tr = [f"translate({x + cx},{y + cy}) rotate({-angle}) translate({-cx + w},{cy})"]
        elif angle:
            tr.append(f"translate({x + cx},{y + cy}) rotate({-angle}) translate({-cx},{-cy})")
        else:
            tr.append(f"translate({x},{y})")
        parts.append(
            f'  <image href="data:image/png;base64,{b64}" x="0" y="0" '
            f'width="{w}" height="{h}" transform="{_svg_escape(" ".join(tr))}" preserveAspectRatio="none"/>'
        )
    parts.append(
        f'  <image href="data:image/png;base64,{png_b64}" x="0" y="0" '
        f'width="{GRID}" height="{GRID}" opacity="0.6"/>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{GRID}" height="{GRID}" viewBox="0 0 {GRID} {GRID}">'
        f'\n  <rect width="{GRID}" height="{GRID}" fill="white"/>\n'
        + "\n".join(parts)
        + "\n</svg>"
    )


def save_candidate(char: str, pieces: list[dict], author: str, note: str = "", png_data: bytes | None = None) -> dict:
    """校验 + 存项目与成品，入库 pending。png_data 来自前端所见即所得渲染；None 时后端合成。"""
    if char not in LEVEL1:
        raise ValueError(f"目标字不在一级字集: {char}")
    uid = uuid.uuid4().hex[:12]
    cand_dir = PUZZLE_CANDIDATES / char
    cand_dir.mkdir(parents=True, exist_ok=True)

    if png_data is None:
        png = render_png(pieces)
    else:
        png = png_data
    import base64

    png_b64 = base64.b64encode(png).decode()
    svg = render_svg(pieces, png_b64)

    png_p = cand_dir / f"{uid}.png"
    svg_p = cand_dir / f"{uid}.svg"
    proj_p = cand_dir / f"{uid}.json"
    png_p.write_bytes(png)
    svg_p.write_text(svg, encoding="utf-8")
    proj_p.write_text(
        json.dumps(
            {
                "char": char,
                "pieces": pieces,
                "author": author,
                "note": note,
                "png_source": "frontend" if png_data is not None else "backend",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    conn = store.connect()
    conn.execute(
        "INSERT INTO candidates (char, uid, author, status, png_path, svg_path, project_path, note) "
        "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)",
        (char, uid, author, str(png_p), str(svg_p), str(proj_p), note),
    )
    conn.commit()
    conn.close()
    return {"id": uid, "char": char, "status": "pending"}


def list_candidates(char: str, status: str | None = None) -> list[dict]:
    conn = store.connect()
    if status:
        rows = conn.execute(
            "SELECT id, char, uid, author, status, note, created_at FROM candidates WHERE char = ? AND status = ? ORDER BY id",
            (char, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, char, uid, author, status, note, created_at FROM candidates WHERE char = ? ORDER BY id",
            (char,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def all_candidates(status: str | None = None, limit: int = 200) -> list[dict]:
    conn = store.connect()
    if status:
        rows = conn.execute(
            "SELECT id, char, uid, author, status, note, created_at FROM candidates WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, char, uid, author, status, note, created_at FROM candidates ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cand_files(uid: str) -> tuple[Path, Path, Path] | None:
    """根据 uid（uuid）查找候选文件；uid 即文件名前缀"""
    for char_dir in PUZZLE_CANDIDATES.iterdir():
        if not char_dir.is_dir():
            continue
        png = char_dir / f"{uid}.png"
        svg = char_dir / f"{uid}.svg"
        proj = char_dir / f"{uid}.json"
        if png.exists():
            return png, svg, proj
    return None


def set_status(uid: str, status: str, reviewer: str = "") -> bool:
    conn = store.connect()
    cur = conn.execute(
        "UPDATE candidates SET status = ?, reviewed_at = datetime('now','localtime') WHERE uid = ?",
        (status, uid),
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def char_status(char: str) -> dict:
    conn = store.connect()
    row = conn.execute(
        "SELECT char, stage, status, candidate_path FROM glyphs WHERE char = ?",
        (char,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {"char": char, "stage": "pending", "status": "todo"}


def has_handwritten(char: str) -> bool:
    from .paths import PROCESSED

    return (PROCESSED / f"{char}.png").exists()