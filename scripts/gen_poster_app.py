# -*- coding: utf-8 -*-
"""
Generate a self-contained web app (index.html) that renders the artistic
ink-wash poster (couplet "苟利国家生死以 / 岂因祸福避趋之") built from the
14 handwritten character PNGs, used as a full-screen webpage background.

Design spec (restored exactly):
  Layout : 1920x1080 reference, landscape. Traditional vertical couplet,
           right column read first (右→左): 苟利国家生死以 | 岂因祸福避趋之.
  Palette : rice-paper #F2E9D8 (dominant) / ink #2A2622 (secondary) /
            cinnabar #B23A2E (accent seal).
  Details : ink-wash atmosphere, paper grain, cinnabar name seal (则徐),
            attribution line 林则徐《赴戍登程口占示家人》.
"""
import base64
import os

SRC_DIR = r"F:\code\python\zhangzhe_font\data\target"
OUT_DIR = r"F:\code\python\zhangzhe_font\webapp"
OUT_FILE = os.path.join(OUT_DIR, "index.html")

# Right-to-left reading: right column is read first.
RIGHT_COL = ["苟", "利", "国", "家", "生", "死", "以"]   # placed on the right
LEFT_COL = ["岂", "因", "祸", "福", "避", "趋", "之"]    # placed on the left


def b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


# Build data-URI map for the 14 characters.
chars = {}
for ch in RIGHT_COL + LEFT_COL:
    p = os.path.join(SRC_DIR, f"{ch}.png")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    chars[ch] = "data:image/png;base64," + b64(p)


def col_html(column_chars):
    imgs = "\n".join(
        f'        <img src="{chars[c]}" alt="{c}">' for c in column_chars
    )
    return f'      <div class="col">\n{imgs}\n      </div>'


# DOM order: left column first, right column second (flex row puts right on the right).
left_html = col_html(LEFT_COL)
right_html = col_html(RIGHT_COL)

# Subtle paper grain via inline SVG turbulence (data URI, low opacity).
grain = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence "
    "type='fractalNoise' baseFrequency='0.9' numOctaves='2' "
    "stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' "
    "height='100%25' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E"
)

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>苟利国家生死以 · 岂因祸福避趋之</title>
<style>
  :root {{
    --paper: #F2E9D8;
    --paper-light: #F6EFE0;
    --paper-dark: #E4D8BE;
    --ink: #2A2622;
    --cinnabar: #B23A2E;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: "Noto Serif SC", "Source Han Serif SC", "Songti SC",
               "STSong", "SimSun", serif;
    color: var(--ink);
    min-height: 100vh;
    overflow-x: hidden;
  }}

  /* ===== The poster, fixed full-screen, used as the webpage background ===== */
  .poster-bg {{
    position: fixed;
    inset: 0;
    z-index: 0;
    background:
      radial-gradient(58% 48% at 80% 28%, rgba(120,140,162,0.10), transparent 70%),
      radial-gradient(52% 60% at 16% 82%, rgba(92,112,132,0.09), transparent 72%),
      radial-gradient(120% 120% at 50% 50%, var(--paper-light) 0%, var(--paper) 62%, var(--paper-dark) 100%);
    overflow: hidden;
  }}
  /* paper grain overlay */
  .poster-bg::after {{
    content: "";
    position: absolute;
    inset: 0;
    background-image: url("{grain}");
    background-size: 180px 180px;
    opacity: 0.05;
    mix-blend-mode: multiply;
    pointer-events: none;
  }}

  /* traditional vertical couplet, left-of-centre, leaving the right for content */
  .couplet {{
    position: absolute;
    top: 50%;
    left: clamp(36px, 11vw, 248px);
    transform: translateY(-50%);
    display: flex;
    flex-direction: row;            /* left column first, right column second */
    gap: clamp(16px, 2.6vw, 52px);
  }}
  .col {{
    display: flex;
    flex-direction: column;
    gap: clamp(4px, 1vh, 14px);
  }}
  .col img {{
    height: clamp(62px, 9.4vh, 130px);
    width: auto;
    display: block;
    filter: drop-shadow(0 1px 1px rgba(42,38,34,0.16));
  }}

  /* cinnabar name seal (则徐), lower-left of the couplet */
  .seal {{
    position: absolute;
    left: clamp(36px, 11vw, 248px);
    bottom: clamp(36px, 9vh, 110px);
    width: clamp(42px, 6.2vh, 92px);
    height: clamp(42px, 6.2vh, 92px);
    background: var(--cinnabar);
    color: var(--paper-light);
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    box-shadow: 0 2px 10px rgba(140,40,30,0.28);
    writing-mode: vertical-rl;
    text-orientation: upright;
    font-size: clamp(18px, 3vh, 40px);
    font-weight: 700;
    letter-spacing: 4px;
    line-height: 1.05;
  }}

  /* attribution line, balanced on the right */
  .attribution {{
    position: absolute;
    right: clamp(36px, 6vw, 120px);
    bottom: clamp(30px, 5.5vh, 76px);
    text-align: right;
    font-size: clamp(15px, 1.7vw, 28px);
    letter-spacing: 1px;
    opacity: 0.82;
  }}

  /* ===== Sample foreground content (replace with your own site content) ===== */
  .hero {{
    position: relative;
    z-index: 2;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-end;
    text-align: right;
    padding: 0 clamp(40px, 8vw, 170px);
    pointer-events: none;
  }}
  .hero .tag {{
    font-size: clamp(14px, 1.4vw, 22px);
    letter-spacing: 6px;
    color: var(--cinnabar);
    margin-bottom: clamp(10px, 1.6vh, 22px);
  }}
  .hero h1 {{
    margin: 0;
    font-size: clamp(40px, 6.2vw, 104px);
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: 2px;
    text-shadow: 0 2px 18px rgba(242,233,216,0.55);
  }}
  .hero p {{
    margin: clamp(16px, 2.4vh, 30px) 0 0;
    max-width: 30em;
    font-size: clamp(15px, 1.5vw, 24px);
    line-height: 1.7;
    opacity: 0.9;
  }}
  .hero .btn {{
    pointer-events: auto;
    margin-top: clamp(22px, 3vh, 40px);
    display: inline-block;
    padding: clamp(12px,1.4vh,16px) clamp(26px,3vw,40px);
    background: var(--ink);
    color: var(--paper-light);
    text-decoration: none;
    font-size: clamp(15px, 1.4vw, 20px);
    letter-spacing: 3px;
    border-radius: 2px;
    transition: transform .18s ease, box-shadow .18s ease;
  }}
  .hero .btn:hover {{
    transform: translateY(-2px);
    box-shadow: 0 10px 26px rgba(42,38,34,0.25);
  }}
</style>
</head>
<body>
  <!-- The poster layer = reusable webpage background -->
  <div class="poster-bg" aria-hidden="true">
    <div class="couplet">
{left_html}
{right_html}
    </div>
    <div class="seal">则徐</div>
    <div class="attribution">林则徐《赴戍登程口占示家人》</div>
  </div>

  <!-- Sample foreground content demonstrating legibility over the background -->
  <main class="hero">
    <div class="tag">丹 心 报 国</div>
    <h1>苟利国家<br>生死以之</h1>
    <p>以十四帧手书墨迹为引，铺陈一纸宣纸长卷。愿这方背景，托得起你网页上的每一句文字。</p>
    <a class="btn" href="#">了 解 更 多</a>
  </main>
</body>
</html>
"""

os.makedirs(OUT_DIR, exist_ok=True)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print("WROTE", OUT_FILE, "bytes=", len(html))
