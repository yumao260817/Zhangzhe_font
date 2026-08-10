import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import store
from ..gb2312 import level1_chars
from ..paths import CONFIG_FILE, DB_FILE, QUEUE, PUZZLE_PIECES, ROOT
from .. import stage_puzzle as puzzle
from .. import auth


def _load_config(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        return {}


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return None


def _admin_ok(token: str, authorization: str | None, cfg: dict) -> bool:
    """仅认可登录的管理员账号会话；token 参数为 Bearer 的查询参数形式（图片访问兼容）"""
    user = auth.user_by_token(_bearer(authorization)) or auth.user_by_token(token)
    return auth.is_admin(user)


def _reviewer_name(authorization: str | None) -> str:
    """从 Bearer 会话取管理员邮箱作为审核人"""
    user = auth.user_by_token(_bearer(authorization))
    return user["email"] if user else ""


def make_app(config: str | None = None) -> FastAPI:
    cfg_path = Path(config) if config else CONFIG_FILE
    cfg = _load_config(cfg_path)

    app = FastAPI(title="zhangzhe-font 拼字工作台")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/api/charset")
    def charset():
        return {"level1_total": len(level1_chars())}

    @app.get("/api/status")
    def status():
        conn = store.connect()
        rows = conn.execute(
            "SELECT stage, status, COUNT(*) AS n FROM glyphs GROUP BY stage, status ORDER BY stage, status"
        ).fetchall()
        conn.close()
        return [{"stage": r["stage"], "status": r["status"], "count": r["n"]} for r in rows]

    @app.get("/api/queue")
    def queue(limit: int = 50, stage: str = "pending"):
        conn = store.connect()
        rows = conn.execute(
            "SELECT char, stage, status, attempts, scores FROM glyphs "
            "WHERE stage = ? AND status = 'todo' LIMIT ?",
            (stage, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---------------- 用户 / 会话 ----------------

    @app.get("/api/auth/captcha")
    def captcha():
        return auth.new_captcha()

    @app.post("/api/auth/register")
    async def register(
        email: str = Form(...),
        password: str = Form(...),
        name: str = Form(""),
        captcha_id: str = Form(""),
        captcha_answer: str = Form(""),
    ):
        if not auth.check_captcha(captcha_id, captcha_answer):
            raise HTTPException(status_code=400, detail="验证码错误或已过期，请刷新验证码")
        ok, msg, user = auth.register(email, password, name, cfg)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"ok": True, "message": msg, "user": user}

    @app.post("/api/auth/login")
    async def login(email: str = Form(...), password: str = Form(...)):
        ok, msg, data = auth.login(email, password)
        if not ok:
            raise HTTPException(status_code=401, detail=msg)
        return {"ok": True, "message": msg, **data}

    @app.post("/api/auth/logout")
    async def logout(authorization: str | None = Header(None)):
        auth.logout(_bearer(authorization))
        return {"ok": True}

    @app.get("/api/auth/me")
    def auth_me(authorization: str | None = Header(None)):
        user = auth.user_by_token(_bearer(authorization))
        if not user:
            raise HTTPException(status_code=401, detail="未登录")
        return {"user": user}

    @app.get("/api/auth/role")
    def auth_role(email: str = ""):
        """查询某邮箱是否为配置的管理员邮箱（注册前可用）"""
        return {"is_admin": email.strip().lower() in auth.admin_emails(cfg)}

    # ---------------- 拼字工作台 ----------------

    @app.get("/api/pieces/{pid}/img")
    def piece_img(pid: str):
        fp = PUZZLE_PIECES / f"{pid}.png"
        if not fp.exists():
            raise HTTPException(status_code=404, detail="部件不存在")
        return FileResponse(str(fp), media_type="image/png")

    @app.get("/api/char/{char}")
    def char_info(char: str, authorization: str | None = Header(None)):
        if char not in level1_chars():
            raise HTTPException(status_code=404, detail="目标字不在 GB2312 一级字集")
        from ..paths import PROCESSED, STDSRC

        admin = auth.is_admin(auth.user_by_token(_bearer(authorization)))
        return {
            "char": char,
            "handwritten": (PROCESSED / f"{char}.png").exists(),
            "std": (STDSRC / f"{char}.png").exists(),
            "approved": puzzle.list_candidates(char, "approved"),
            "pending": puzzle.list_candidates(char, "pending") if admin else [],
        }

    @app.get("/api/std/{char}/img")
    def std_img(char: str):
        from ..paths import STDSRC

        fp = STDSRC / f"{char}.png"
        if not fp.exists():
            raise HTTPException(status_code=404, detail="标准字形不存在")
        return FileResponse(str(fp), media_type="image/png")

    @app.get("/api/hand/{char}/img")
    def hand_img(char: str):
        from ..paths import PROCESSED

        fp = PROCESSED / f"{char}.png"
        if not fp.exists():
            raise HTTPException(status_code=404, detail="手写原迹不存在")
        return FileResponse(str(fp), media_type="image/png")

    @app.post("/api/char/{char}/submit")
    async def submit(
        char: str,
        note: str = Form(""),
        pieces: str = Form(""),
        file: UploadFile = File(...),
        source: UploadFile | None = File(None),
        authorization: str | None = Header(None),
    ):
        user = auth.user_by_token(_bearer(authorization))
        if not user:
            raise HTTPException(status_code=401, detail="请先登录")
        if char not in level1_chars():
            raise HTTPException(status_code=404, detail="目标字不在 GB2312 一级字集")
        if len(pieces) > 512 * 1024:
            raise HTTPException(status_code=413, detail="图层数据过大")
        layers: list = []
        if pieces:
            try:
                import json as _json

                layers = _json.loads(pieces)
                if not isinstance(layers, list):
                    raise ValueError("图层数据必须是数组")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"图层数据无效: {e}")
        png_data = await file.read()
        if not png_data:
            raise HTTPException(status_code=400, detail="PNG 文件为空")
        source_png = None
        if source is not None:
            source_png = await source.read()
            if not source_png:
                raise HTTPException(status_code=400, detail="出处图文件为空")
        try:
            # 署名强制使用登录用户，防止伪造
            author = user.get("name") or user["email"]
            return puzzle.save_candidate(char, layers, author=author, note=note, png_data=png_data, source_png=source_png)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/char/{char}/candidates")
    def char_candidates(
        char: str, status: str | None = None, token: str = "", authorization: str | None = Header(None)
    ):
        """公开只给 approved；管理员给全部"""
        if _admin_ok(token, authorization, cfg):
            return puzzle.list_candidates(char, status)
        return puzzle.list_candidates(char, "approved")

    @app.get("/api/candidates")
    def candidates(
        status: str | None = None, token: str = "", authorization: str | None = Header(None)
    ):
        if status and status != "approved":
            if not _admin_ok(token, authorization, cfg):
                raise HTTPException(status_code=403, detail="需要管理员权限")
        if _admin_ok(token, authorization, cfg):
            return puzzle.all_candidates(status)
        return puzzle.all_candidates("approved")

    @app.get("/api/my/candidates")
    def my_candidates(authorization: str | None = Header(None), token: str = ""):
        """当前登录用户提交的全部候选（含各审核状态）"""
        user = auth.user_by_token(_bearer(authorization)) or auth.user_by_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="需要登录")
        email = user["email"]
        name = user.get("name") or ""
        with store.db() as conn:
            rows = conn.execute(
                "SELECT uid, char, status, note, created_at, reviewed_at"
                " FROM candidates WHERE author = ? OR author = ?"
                " ORDER BY created_at DESC",
                (email, name),
            ).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/random-pending")
    def random_pending(n: int = 5, token: str = ""):
        from ..paths import STDSRC

        hand = puzzle.handwritten_set()
        need = [c for c in level1_chars() if c not in hand]
        with store.db() as conn:
            approved = {
                r["char"]
                for r in conn.execute("SELECT DISTINCT char FROM candidates WHERE status = 'approved'").fetchall()
            }
        pending = [c for c in need if c not in approved]
        import random

        random.shuffle(pending)
        picked = pending[: max(1, n)]
        return [
            {
                "char": c,
                "handwritten": c in hand,
                "approved": c in approved,
                "std": (STDSRC / f"{c}.png").exists(),
            }
            for c in picked
        ]

    @app.get("/api/pinyin/{py}")
    def pinyin_lookup(py: str):
        """拼音查同音字（GB2312 一级字集）"""
        from ..pinyin_map import homophones

        chars = homophones(py)
        hand = puzzle.handwritten_set()
        approved = _approved_uids()
        return {
            "pinyin": py.lower(),
            "count": len(chars),
            "chars": [
                {
                    "char": c,
                    "handwritten": c in hand,
                    "approved_uid": approved.get(c, {}).get("uid"),
                    "approved_source": approved.get(c, {}).get("source"),
                }
                for c in chars
            ],
        }

    def _approved_uids() -> dict:
        """char -> 最新 approved 候选信息 {uid, source}"""
        with store.db() as conn:
            rows = conn.execute(
                "SELECT c.char AS char, c.uid AS uid, c.source AS source FROM candidates c "
                "JOIN (SELECT char, MAX(id) AS mid FROM candidates WHERE status='approved' GROUP BY char) m "
                "ON c.id = m.mid"
            ).fetchall()
        return {r["char"]: {"uid": r["uid"], "source": r["source"]} for r in rows}

    @app.get("/api/gallery")
    def gallery():
        hand = puzzle.handwritten_set()
        approved = _approved_uids()
        out = []
        for c in level1_chars():
            info = approved.get(c, {})
            out.append(
                {
                    "char": c,
                    "handwritten": c in hand,
                    "approved_uid": info.get("uid"),
                    "approved_source": info.get("source"),
                }
            )
        return out

    @app.get("/api/candidates/{uid}/png")
    def cand_png(uid: str, token: str = "", authorization: str | None = Header(None)):
        files = puzzle.cand_files(uid)
        if not files:
            raise HTTPException(status_code=404, detail="候选不存在")
        png, svg, proj = files
        # 未审核的只有管理员可见；提交者本人可见自己的图
        from .. import store as _s

        conn = _s.connect()
        row = conn.execute("SELECT status, author FROM candidates WHERE uid = ?", (uid,)).fetchone()
        conn.close()
        if row is None:
            raise HTTPException(status_code=404, detail="候选不存在")
        status, author = row["status"], row["author"]
        if status != "approved" and not _admin_ok(token, authorization, cfg):
            user = auth.user_by_token(_bearer(authorization)) or auth.user_by_token(token)
            if not user or (user["email"] != author and (user.get("name") or "") != author):
                raise HTTPException(status_code=403, detail="需要管理员权限")
        return FileResponse(str(png), media_type="image/png")

    @app.get("/api/candidates/{uid}/svg")
    def cand_svg(uid: str, token: str = "", authorization: str | None = Header(None)):
        files = puzzle.cand_files(uid)
        if not files:
            raise HTTPException(status_code=404, detail="候选不存在")
        png, svg, proj = files
        from .. import store as _s

        conn = _s.connect()
        row = conn.execute("SELECT status, author FROM candidates WHERE uid = ?", (uid,)).fetchone()
        conn.close()
        if row is None:
            raise HTTPException(status_code=404, detail="候选不存在")
        status, author = row["status"], row["author"]
        if status != "approved" and not _admin_ok(token, authorization, cfg):
            user = auth.user_by_token(_bearer(authorization)) or auth.user_by_token(token)
            if not user or (user["email"] != author and (user.get("name") or "") != author):
                raise HTTPException(status_code=403, detail="需要管理员权限")
        return FileResponse(str(svg), media_type="image/svg+xml")

    @app.get("/api/candidates/{uid}/project")
    def cand_project(uid: str, token: str = "", authorization: str | None = Header(None)):
        if not _admin_ok(token, authorization, cfg):
            raise HTTPException(status_code=403, detail="需要管理员权限")
        files = puzzle.cand_files(uid)
        if not files:
            raise HTTPException(status_code=404, detail="候选不存在")
        png, svg, proj = files
        return FileResponse(str(proj), media_type="application/json")

    @app.post("/api/admin/approve")
    def approve(uid: str = Form(...), token: str = Form(""), authorization: str | None = Header(None)):
        if not _admin_ok(token, authorization, cfg):
            raise HTTPException(status_code=403, detail="需要管理员权限")
        reviewer = _reviewer_name(authorization)
        ok = puzzle.set_status(uid, "approved", reviewer=reviewer)
        if not ok:
            raise HTTPException(status_code=404, detail="候选不存在")
        return {"ok": True, "uid": uid, "status": "approved"}

    @app.post("/api/admin/reject")
    def reject(uid: str = Form(...), token: str = Form(""), authorization: str | None = Header(None)):
        if not _admin_ok(token, authorization, cfg):
            raise HTTPException(status_code=403, detail="需要管理员权限")
        reviewer = _reviewer_name(authorization)
        ok = puzzle.set_status(uid, "rejected", reviewer=reviewer)
        if not ok:
            raise HTTPException(status_code=404, detail="候选不存在")
        return {"ok": True, "uid": uid, "status": "rejected"}

    # ---- 前端静态资源 ----
    dist_dir = ROOT / "webui" / "dist"
    if dist_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

        @app.get("/")
        def index():
            return FileResponse(str(dist_dir / "index.html"), media_type="text/html")

    return app