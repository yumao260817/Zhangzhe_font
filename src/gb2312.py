def level1_chars() -> list[str]:
    chars = []
    for qh in range(0xB0, 0xD7 + 1):
        ql_max = 0xF9 if qh == 0xD7 else 0xFE
        for ql in range(0xA1, ql_max + 1):
            ch = bytes([qh, ql]).decode("gb2312", errors="ignore")
            if len(ch) == 1 and "\u4e00" <= ch <= "\u9fff":
                chars.append(ch)
    return chars


DEFAULT_SET = level1_chars()
