def ensure_db() -> None:
    from .store import init_db

    init_db()
    print("数据库初始化完成")

    from .gb2312 import level1_chars
    from .store import connect

    conn = connect()
    cur = conn.execute("SELECT COUNT(*) FROM glyphs")
    n = cur.fetchone()[0]
    if n == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO glyphs (char, stage, status) VALUES (?, 'pending', 'todo')",
            [(ch,) for ch in level1_chars()],
        )
        conn.commit()
        print(f"已写入 GB2312 一级 3755 字到待办队列")
    else:
        print(f"队列已有 {n} 字，跳过初始化")
    conn.close()