import sqlite3
from contextlib import contextmanager

from .paths import DB_FILE

SCHEMA = """
CREATE TABLE IF NOT EXISTS glyphs (
  char TEXT PRIMARY KEY,
  stage TEXT NOT NULL DEFAULT 'pending',
  status TEXT NOT NULL DEFAULT 'todo',
  attempts INTEGER NOT NULL DEFAULT 0,
  candidate_path TEXT,
  scores TEXT,
  note TEXT
);

CREATE TABLE IF NOT EXISTS review_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  char TEXT NOT NULL,
  action TEXT NOT NULL,
  reviewer TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  char TEXT NOT NULL,
  uid TEXT NOT NULL UNIQUE,
  author TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  note TEXT,
  png_path TEXT,
  svg_path TEXT,
  project_path TEXT,
  source TEXT NOT NULL DEFAULT 'composed',
  source_path TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  pass_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  name TEXT,
  temp_pw_expire TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS captchas (
  cid TEXT PRIMARY KEY,
  answer TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_fails (
  email TEXT PRIMARY KEY,
  fail_count INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def connect() -> sqlite3.Connection:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db():
    """连接 + 自动提交/回滚 + 必然关闭"""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    conn = connect()
    conn.executescript(SCHEMA)
    # 轻量迁移：老库补列
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(review_log)").fetchall()]
    if "reviewer" not in cols:
        conn.execute("ALTER TABLE review_log ADD COLUMN reviewer TEXT")
    if "note" not in cols:
        conn.execute("ALTER TABLE review_log ADD COLUMN note TEXT")
    cand_cols = [r["name"] for r in conn.execute("PRAGMA table_info(candidates)").fetchall()]
    if "source" not in cand_cols:
        conn.execute("ALTER TABLE candidates ADD COLUMN source TEXT NOT NULL DEFAULT 'composed'")
    if "source_path" not in cand_cols:
        conn.execute("ALTER TABLE candidates ADD COLUMN source_path TEXT")
    user_cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "temp_pw_expire" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN temp_pw_expire TEXT")
    # 查询索引（P2-2）
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cand_char ON candidates(char)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cand_status ON candidates(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    conn.commit()
    conn.close()
