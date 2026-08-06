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
MAX_PIECE_BYTES = 2 * 1024 * 1024  # 单部件 2MB 上限
MAX_PIECES_PER_USER_PER_HOUR = 100  # 单用户上传频率上限


def _imread_bytes(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data)).convert("RGBA")


def validate_piece(data: bytes) -> tuple[bool, str]:
    """校验上传数据：大小上限 + 可解码 PNG"""
    if len(data) > MAX_PIECE_BYTES:
        return False, f"图片超过大小上限 {MAX_PIECE_BYTES // (1024 * 1024)}MB"
    try:
        img = _imread_bytes(data)
        if img.width < 4 or img.height < 4:
            return False, "图片尺寸过小"
    except Exception:
        return False, "不是有效 PNG 图片"
    return True, ""


def save_piece(data: bytes) -> dict:
    """保存上传的透明 PNG 部件，返回元信息"""
    ok, msg = validate_piece(data)
    if not ok:
        raise ValueError(msg)
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


def save_candidate(char: str, pieces: list[dict], author: str, note: str = "", png_data: bytes = b"") -> dict:
    """校验 + 存项目与成品，入库 pending。png_data 为前端所见即所得渲染的合并图（必填）。"""
    if char not in LEVEL1:
        raise ValueError(f"目标字不在一级字集: {char}")
    if len(pieces) > 64:
        raise ValueError("图层数量无效（最多 64）")
    if not png_data:
        raise ValueError("缺少合并后的 PNG 数据")
    if len(png_data) > MAX_PIECE_BYTES:
        raise ValueError("PNG 超过大小上限")
    try:
        img = _imread_bytes(png_data)
    except Exception:
        raise ValueError("PNG 数据不是有效图片")
    if img.size != (GRID, GRID):
        raise ValueError(f"PNG 尺寸必须为 {GRID}×{GRID}")
    uid = uuid.uuid4().hex[:12]
    cand_dir = PUZZLE_CANDIDATES / char
    cand_dir.mkdir(parents=True, exist_ok=True)

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
                "png_source": "frontend",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with store.db() as conn:
        conn.execute(
            "INSERT INTO candidates (char, uid, author, status, png_path, svg_path, project_path, note) "
            "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)",
            (char, uid, author, str(png_p), str(svg_p), str(proj_p), note),
        )
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
    """根据 uid 从 DB 查候选文件路径（O(1)）；只返回实际存在的文件"""
    conn = store.connect()
    try:
        row = conn.execute(
            "SELECT png_path, svg_path, project_path FROM candidates WHERE uid = ?", (uid,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    paths = tuple(Path(p) for p in (row["png_path"], row["svg_path"], row["project_path"]))
    if not paths[0].exists():
        return None
    return paths  # 类型: (Path, Path, Path)


def set_status(uid: str, status: str, reviewer: str = "") -> bool:
    conn = store.connect()
    try:
        cur = conn.execute(
            "UPDATE candidates SET status = ?, reviewed_at = datetime('now','localtime') WHERE uid = ?",
            (status, uid),
        )
        row = conn.execute("SELECT char FROM candidates WHERE uid = ?", (uid,)).fetchone()
        if cur.rowcount > 0 and row:
            conn.execute(
                "INSERT INTO review_log (char, action, reviewer) VALUES (?, ?, ?)",
                (row["char"], f"{status}:{uid}", reviewer),
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def char_status(char: str) -> dict:
    conn = store.connect()
    row = conn.execute(
        "SELECT char, stage, status, candidate_path FROM glyphs WHERE char = ?",
        (char,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {"char": char, "stage": "pending", "status": "todo"}


def has_handwritten(char: str) -> bool:
    return char in handwritten_set()


_HAND_CACHE: tuple = (0.0, frozenset())


def handwritten_set(max_age: float = 60) -> frozenset[str]:
    """data/processed 中已有手写字的集合（60s 缓存，避免 3755 次磁盘 stat）"""
    import time as _time

    global _HAND_CACHE
    ts, s = _HAND_CACHE
    now = _time.time()
    if now - ts > max_age:
        from .paths import PROCESSED

        s = frozenset(p.stem for p in PROCESSED.glob("*.png"))
        _HAND_CACHE = (now, s)
    return s