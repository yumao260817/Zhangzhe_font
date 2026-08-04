import sqlite3

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
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  pass_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  name TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  expires_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
