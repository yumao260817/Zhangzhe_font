import hashlib
import hmac
import secrets
import random
from datetime import datetime, timedelta

from . import store

TOKEN_TTL_DAYS = 30
CAPTCHA_TTL_SECONDS = 300
LOGIN_MAX_FAIL = 5
LOGIN_LOCK_MINUTES = 15
TEMP_PW_TTL_HOURS = 24
MIN_PASSWORD_LEN = 8


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_captcha() -> dict:
    a = random.randint(10, 99)
    b = random.randint(1, 9)
    cid = secrets.token_urlsafe(10)
    expires = (datetime.now() + timedelta(seconds=CAPTCHA_TTL_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    with store.db() as conn:
        conn.execute(
            "INSERT INTO captchas (cid, answer, expires_at) VALUES (?, ?, ?)",
            (cid, str(a + b), expires),
        )
        conn.execute("DELETE FROM captchas WHERE expires_at < ?", (_now_str(),))
    return {"captcha_id": cid, "question": f"{a} + {b} = ?"}


def check_captcha(cid: str, answer) -> bool:
    if not cid or answer is None:
        return False
    try:
        answer_int = int(str(answer).strip())
    except (TypeError, ValueError):
        return False
    with store.db() as conn:
        row = conn.execute(
            "SELECT answer FROM captchas WHERE cid = ? AND expires_at > ?",
            (cid, _now_str()),
        ).fetchone()
        if row is not None and row["answer"] == str(answer_int):
            # 仅答案正确时消费（一次性）；答错可重试，到期自动失效
            conn.execute("DELETE FROM captchas WHERE cid = ?", (cid,))
    return bool(row) and row["answer"] == str(answer_int)


def login_locked(email: str) -> bool:
    """登录失败锁定：累计 5 次失败锁 15 分钟"""
    with store.db() as conn:
        row = conn.execute(
            "SELECT fail_count, locked_until FROM login_fails WHERE email = ?", (email,)
        ).fetchone()
    if not row:
        return False
    if row["locked_until"]:
        return row["locked_until"] > _now_str()
    return row["fail_count"] >= LOGIN_MAX_FAIL


def record_login_fail(email: str) -> None:
    now = _now_str()
    with store.db() as conn:
        row = conn.execute("SELECT fail_count, locked_until FROM login_fails WHERE email = ?", (email,)).fetchone()
        if row and row["locked_until"] and row["locked_until"] > now:
            return  # 已锁定期间不再累计
        count = (row["fail_count"] if row else 0) + 1
        locked_until = None
        if count >= LOGIN_MAX_FAIL:
            locked_until = (
                datetime.now() + timedelta(minutes=LOGIN_LOCK_MINUTES)
            ).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO login_fails (email, fail_count, locked_until) VALUES (?, ?, ?) "
            "ON CONFLICT(email) DO UPDATE SET fail_count = ?, locked_until = ?, updated_at = datetime('now','localtime')",
            (email, count, locked_until, count, locked_until),
        )


def clear_login_fail(email: str) -> None:
    with store.db() as conn:
        conn.execute("DELETE FROM login_fails WHERE email = ?", (email,))


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


def set_temp_password(email: str, temp: str) -> bool:
    """管理员重置：写入临时密码 + 24h 时效。返回用户是否存在。"""
    with store.db() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row is None:
            return False
        conn.execute(
            "UPDATE users SET pass_hash = ?, temp_pw_expire = ? WHERE id = ?",
            (hash_password(temp), _now_str(), row["id"]),
        )
    return True


def change_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    """修改密码：验证旧密码，更新并清除临时密码标记（保留当前会话，清其它会话）"""
    if not new_password or len(new_password) < MIN_PASSWORD_LEN:
        return False, f"新密码至少 {MIN_PASSWORD_LEN} 位"
    if old_password == new_password:
        return False, "新密码不能与旧密码相同"
    with store.db() as conn:
        row = conn.execute("SELECT pass_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row or not verify_password(old_password, row["pass_hash"]):
            return False, "旧密码不正确"
        conn.execute(
            "UPDATE users SET pass_hash = ?, temp_pw_expire = NULL WHERE id = ?",
            (hash_password(new_password), user_id),
        )
    return True, "密码已修改"


def register(email: str, password: str, name: str = "", cfg: dict | None = None) -> tuple[bool, str, dict | None]:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return False, "邮箱格式不正确", None
    if not password or len(password) < MIN_PASSWORD_LEN:
        return False, f"密码至少 {MIN_PASSWORD_LEN} 位", None
    conn = store.connect()
    try:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            # 模糊提示：不区分「已注册」与其他错误，防邮箱枚举
            return False, "注册失败，请检查邮箱后重试", None
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
        # 临时密码时效：过期则拒绝（需管理员重新重置）
        if row["temp_pw_expire"] and row["temp_pw_expire"] < _now_str():
            return False, "临时密码已过期，请联系管理员重新重置", None
        token = secrets.token_urlsafe(32)
        expires = (datetime.now() + timedelta(days=TOKEN_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, row["id"], expires),
        )
        conn.commit()
        must_change = bool(row["temp_pw_expire"])
        return True, "登录成功", {"token": token, "user": _user_dict(row), "must_change": must_change}
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