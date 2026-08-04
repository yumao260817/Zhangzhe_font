def run() -> None:
    from .store import connect

    conn = connect()
    rows = conn.execute(
        "SELECT stage, status, COUNT(*) AS n FROM glyphs GROUP BY stage, status ORDER BY stage, status"
    ).fetchall()
    if not rows:
        print("数据库为空，请先执行 init")
    for r in rows:
        print(f"{r['stage']:12s} {r['status']:8s} {r['n']}")
    conn.close()