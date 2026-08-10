import hashlib
import hmac
import secrets
import random
import threading
import time
from datetime import datetime, timedelta

from . import store

TOKEN_TTL_DAYS = 30
CAPTCHA_TTL_SECONDS = 300

_captchas: dict[str, tuple[int, float]] = {}
_captchas_lock = threading.Lock()


def new_captcha() -> dict:
    a = random.randint(10, 99)
    b = random.randint(1, 9)
    cid = secrets.token_urlsafe(10)
    with _captchas_lock:
        _prune_captchas()
        _captchas[cid] = (a + b, time.time())
    return {"captcha_id": cid, "question": f"{a} + {b} = ?"}


def check_captcha(cid: str, answer) -> bool:
    if not cid or answer is None:
        return False
    try:
        answer_int = int(str(answer).strip())
    except (TypeError, ValueError):
        return False
    with _captchas_lock:
        _prune_captchas()
        entry = _captchas.pop(cid, None)
    return bool(entry and entry[0] == answer_int)


def _prune_captchas() -> None:
    now = time.time()
    expired = [k for k, (_, ts) in _captchas.items() if now - ts > CAPTCHA_TTL_SECONDS]
    for k in expired:
        _captchas.pop(k, None)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def admin_emails(cfg: dict) -> set[str]:
    import os

    env = os.environ.get("ZZ_ADMIN_EMAILS")
    if env:
        return {e.strip().lower() for e in env.split(",") if e.strip()}
    server = cfg.get("server", {}) if isinstance(cfg.get("server"), dict) else {}
    raw = server.get("admin_emails") or cfg.get("admin_emails") or []
    if isinstance(raw, str):
        raw = [e.strip() for e in raw.split(",") if e.strip()]
    return {e.strip().lower() for e in raw if e}


def reviewer_emails(cfg: dict) -> set[str]:
    import os

    env = os.environ.get("ZZ_REVIEWER_EMAILS")
    if env:
        return {e.strip().lower() for e in env.split(",") if e.strip()}
    server = cfg.get("server", {}) if isinstance(cfg.get("server"), dict) else {}
    raw = server.get("reviewer_emails") or cfg.get("reviewer_emails") or []
    if isinstance(raw, str):
        raw = [e.strip() for e in raw.split(",") if e.strip()]
    return {e.strip().lower() for e in raw if e}


def _role_for_email(email: str, cfg: dict) -> str:
    if email.lower() in admin_emails(cfg):
        return "admin"
    if email.lower() in reviewer_emails(cfg):
        return "reviewer"
    return "user"


def register(email: str, password: str, name: str = "", cfg: dict | None = None) -> tuple[bool, str, dict | None]:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return False, "邮箱格式不正确", None
    if not password or len(password) < 6:
        return False, "密码至少 6 位", None
    conn = store.connect()
    try:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            return False, "该邮箱已注册", None
        role = _role_for_email(email, cfg or {})
        cur = conn.execute(
            "INSERT INTO users (email, pass_hash, role, name) VALUES (?, ?, ?, ?)",
            (email, hash_password(password), role, name),
        )
        conn.commit()
        uid = cur.lastrowid
    finally:
        conn.close()
    return True, "注册成功", {"id": uid, "email": email, "role": role, "name": name}


def login(email: str, password: str) -> tuple[bool, str, dict | None]:
    email = (email or "").strip().lower()
    conn = store.connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(password, row["pass_hash"]):
            return False, "邮箱或密码错误", None
        token = secrets.token_urlsafe(32)
        expires = (datetime.now() + timedelta(days=TOKEN_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, row["id"], expires),
        )
        conn.commit()
        return True, "登录成功", {"token": token, "user": _user_dict(row)}
    finally:
        conn.close()


def _user_dict(row) -> dict:
    return {"id": row["id"], "email": row["email"], "role": row["role"], "name": row["name"] or ""}


def user_by_token(token: str | None) -> dict | None:
    if not token:
        return None
    conn = store.connect()
    try:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token = ? AND s.expires_at > datetime('now', 'localtime')",
            (token,),
        ).fetchone()
        return _user_dict(row) if row else None
    finally:
        conn.close()


def logout(token: str | None) -> None:
    if not token:
        return
    conn = store.connect()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def is_admin(user: dict | None) -> bool:
    return bool(user and user.get("role") == "admin")


def is_reviewer(user: dict | None) -> bool:
    """审核员或管理员均可执行审核"""
    return bool(user and user.get("role") in ("admin", "reviewer"))