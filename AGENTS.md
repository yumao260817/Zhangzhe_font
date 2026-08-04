# AGENTS.md — zhangzhe_font 项目指南

本文件供其他 AI agent 快速接手本仓库使用。阅读顺序建议：目标 → 硬性结论（勿重蹈覆辙）→ 架构 → 代码约定 → 当前状态。

## 1. 项目目标

把已故作者的 1000+ 手写汉字（风格/粗细不统一）+ 数千备选图，补全为符合国标的常用字库（GB2312 一级 3755 字），最终导出 TTF。

**当前唯一可行路线：人工拼字**。用户在 Web 拼字工作台上传透明 PNG 部件、拖拽拼成目标字，导出后经管理员审核，审核通过的字才公开显示。

## 2. 硬性结论（已花费大量时间验证，禁止重蹈覆辙）

自动生成路线的全部实验均失败，**不要再尝试**：

1. **整字 Pix2Pix 不可行**：未见过的字生成结果不可辨认（模型文件保留：`models/pix2pix_final.pt`，但不再是主线）。
2. **手写部件跨字拼装不可行**：手写部件自拼 SSIM 0.965，但跨字复用崩到 0.295。诊断结论：手写体部件跨字复用必然崩坏。
3. **部件级 pix2pix 同样不可行**（用整字模型裁部件风格迁移）。
4. **混合字体（占位字体）方案已放弃**。
5. 因此：**拼装通道整体废弃**，`data/assembled/`（2500 字）、`data/generated/` 均为失效资产，保留但勿再引用为数据源。
6. 其余废弃/搁置资产：`models/pix2pix_final.pt`、`third_party/DG-Font`、`checkpoints/`、`others/`。

## 3. 技术栈与运行环境

- 后端：Python 3.14 + FastAPI + uvicorn + SQLite（`queue/font.db`，stdlib sqlite3，无 ORM）
- 前端：Vue 3 + Vite（`webui/`），**未使用 vue-router**（自研 hash 路由）
- 依赖：见 `requirements.txt`（numpy/opencv-python/Pillow/torch/scikit-learn/fastapi/uvicorn/pydantic/PyYAML/fonttools + python-multipart + httpx2(测试用)）
- 平台：Windows，shell 为 PowerShell 5.1

### 常用命令

```powershell
# 启动评审台（开发常用）— 项目根目录
python -m src.cli review            # http://127.0.0.1:8000
python -m src.cli init              # 初始化 DB（建表+队列）
python -m src.cli status            # 队列状态

# 前端构建（PowerShell 禁 npm.ps1，必须用 npm.cmd）
npm.cmd run build                   # 产物 webui/dist，FastAPI 托管，改动 vue 后必须重建
```

## 4. 目录结构

```
assets/                原始素材（labeled / candidates / radicals）
data/
  processed/           清洗后的手写图 256×256（已有一手写字）
  stdsrc/              标准字形（宋体渲染）
  components/          decomp.json（6763 字拆字表）+ parts/ 部件真件库 + parts_meta.json
  puzzle/              pieces/ 用户上传部件 | candidates/ 人工候选（png/svg/project）
  assembled/           失效资产（自动拼装结果）
  generated/           失效资产（pix2pix 生成）
models/                pix2pix_final.pt（保留非主线）
queue/font.db          SQLite（glyphs/review_log/candidates/users/sessions）
configs/default.yaml   配置（server.admin_token / server.admin_emails / 质检阈值）
webui/src/             Vue 3 源码；webui/dist/ 构建产物（后端托管）
output/                导出字体与报告
src/                   流水线各阶段 + FastAPI 后端 + auth
third_party/GB2312-ids 拆字数据源
```

关键路径常量集中在 `src/paths.py`：`PROCESSED`、`STDSRC`、`PUZZLE/PUZZLE_PIECES/PUZZLE_CANDIDATES`、`DB_FILE`、`CONFIG_FILE` 等。

## 5. 后端模块

### 5.1 SQLite schema（`src/store.py`，`init_db()` 建表）

- `glyphs`：流水线队列（char PK, stage, status, attempts, scores）—— 旧的自动流水线遗留，Web 系统基本不用
- `review_log`：评审日志
- `candidates`：人工拼字候选。字段：char / uid(唯一) / author / status(pending|approved|rejected) / note / png_path / svg_path / project_path / created_at / reviewed_at
- `users`：id / email(唯一) / pass_hash(PBKDF2，格式 `salt$hex`) / role(user|admin) / name / created_at
- `sessions`：token(PK) / user_id / created_at / expires_at(30 天)

`store.connect()` 返回 `sqlite3.Row`（支持 `row["col"]` 访问）。

### 5.2 拼字后端 `src/stage_puzzle.py`

- `save_piece(data)`：保存上传部件 → `data/puzzle/pieces/{pid}.png`
- `save_candidate(char, pieces, author, note, png_data=None)`：候选入库，返回 dict。**前端提交 png_data 时原样存储**（`png_source: "frontend"`，WYSIWYG 所见即所得）；否则后端合成。
- `render_png / render_svg`：后端合成（512 网格，`_compose_rgba` 用 GRID=512，与前端一致）
- `list_candidates(char, status)` / `all_candidates(status)` / `cand_files(uid)` / `set_status(uid, status)`

### 5.3 认证 `src/auth.py`

- 邮箱注册（必须过算术验证码）、登录（PBKDF2 + 30 天会话 token）
- `new_captcha()` / `check_captcha(cid, answer)`：**一次性**算术题（内存 dict，5 分钟过期，单进程）
- `register()`：admin 角色由 `server.admin_emails` 配置决定（小写匹配）
- `user_by_token(token)`：会话校验；`logout()`；`is_admin(user)`

### 5.4 API 一览（`src/server/app.py`，`make_app(config)` 工厂）

| 方法/路径 | 鉴权 | 说明 |
|---|---|---|
| GET `/health` | 无 | 健康检查（注意不是 /api/health） |
| GET `/api/auth/captcha` | 无 | 注册验证码 |
| POST `/api/auth/register` | 验证码 | 邮箱注册（captcha_id + captcha_answer 必填） |
| POST `/api/auth/login` | 无 | 登录，返回 token |
| POST `/api/auth/logout` | Bearer | 登出 |
| GET `/api/auth/me` | Bearer | 当前用户 |
| GET `/api/auth/role?email=` | 无 | 查询邮箱是否管理邮箱 |
| POST `/api/pieces` | 无 | 上传部件 PNG |
| GET `/api/char/{char}` | 可选 Bearer | 字详情（pending 列表仅管理员） |
| POST `/api/char/{char}/submit` | **必须登录** | 提交候选（char 是**路径参数**！） |
| GET `/api/char/{char}/candidates` | 管理员/公开 | 公开只给 approved |
| GET `/api/candidates?status=` | 管理员/公开 | status≠approved 需管理员 |
| GET `/api/random-pending?n=5` | 无 | 随机缺字（未批准） |
| GET `/api/gallery` | 无 | 全 3755 字（handwritten/approved_uid） |
| GET `/api/std/{char}/img`、`/api/hand/{char}/img` | 无 | 标准字形/手写参考图 |
| GET `/api/candidates/{uid}/png|svg` | approved 公开；pending 需管理员 | 支持 `?token=` 或 Bearer |
| GET `/api/candidates/{uid}/project` | 管理员 | 工程文件 |
| POST `/api/admin/approve|reject` | 管理员 | 审核 |
| GET `/` + `/assets/*` | 无 | SPA 静态托管 |

**管理员凭证双轨**：① 旧 `admin_token`（`?token=` 或表单字段，config `server.admin_token`）；② 新邮箱账号（`Authorization: Bearer <token>`，role=admin）。`_admin_ok()` 统一处理。

**鉴权规则摘要**：提交必须登录；pending 候选对非管理员隐藏；approve/reject 仅管理员；图片访问 approved 公开、pending 需管理员。

### 5.5 配置 `configs/default.yaml`

```yaml
server:
  admin_token: admin123        # 旧口令，正式使用前必改
  admin_emails:                # 邮箱注册自动成为管理员
    - admin@example.com
```

## 6. 前端结构（`webui/`）

```
src/main.js, App.vue            # 入口 + 自研 hash 路由
src/auth.js                     # token 存取(localStorage 'zz_auth_token') + api() 封装(Bearer)
src/views/
  GalleryView.vue               # 字库：3755 字网格，半透明宋体占位 data-URI，点击 emit open-char
  PuzzleWorkspace.vue           # 拼字台：上传多 PNG、拖拽/缩放/翻转/旋转/层序、标准字形参考、导出
  AdminView.vue                 # 审核页（仅 admin 角色可进，App.vue 拦截）
  AuthView.vue                  # 登录/注册页（注册带算术验证码）
src/components/LayerCanvas.vue  # 画布（rotate + scaleX(flip) 变换）
src/utils/paint.js              # renderCanvas(layers)：512px WYSIWYG 渲染，导出用
```

### 路由约定（无 vue-router，hash 驱动）

- `#/gallery` 字库 / `#/workspace` 拼字 / `#/workspace/<char>` 指定字 / `#/admin` 管理 / `#/login` 登录
- 刷新停留在当前页面（hash 天然保持）；默认无 hash → gallery
- 画廊点字 → `navigate('workspace', ch)` → `PuzzleWorkspace` 的 `initial-char` prop

### 前端关键约定

- **修改 vue/js 后必须 `npm.cmd run build`**（PowerShell 下 `npm run build` 会因禁 npm.ps1 失败）
- 导出即 WYSIWYG：`renderCanvas(layers)` 512px → canvas.toBlob → FormData file 字段 → submit（带 Bearer）
- 图层坐标 512 网格，与后端 `_compose_rgba` 一致
- 登录态：token 存 localStorage；`auth.js` 的 `api()` 自动带 Bearer；图片 URL 用 `?token=` 查询参数（img 标签无法带 header）

## 7. 开发与测试注意（Windows 坑）

1. **PowerShell 中文乱码**：`python -c "...中文..."` 会被 GBK 控制台改写导致断言错误/404 假象。**所有含中文的测试脚本必须写成 UTF-8 文件**再执行，例如：
   ```powershell
   python -c "import sys; sys.path.insert(0, r'F:\code\python\zhangzhe_font'); exec(open(r'<utf8测试文件>', encoding='utf-8').read())"
   ```
2. 无 pytest；用 FastAPI TestClient（需要 `pip install httpx2`），且需先 `store.init_db()`。
3. 测试产生的用户/候选会写进真实 `queue/font.db`，测完记得清理。
4. `char` 是**路径参数**（`/api/char/{char}/submit`），不是表单字段——测试时 URL 需 URL-encode（`%E5%BC%A0`）。

## 8. 当前状态与下一步

- **真实缺字 2500 个**（3755 一级字 − 已有手写 1255），全部待人工拼字。
- 数据库中**暂无任何已批准候选**（测试数据已清理）；管理界面曾实测可用。
- 后端/前端均正常：`python -m src.cli review` → `http://127.0.0.1:8000`。
- 待办建议：
  - 正式使用前修改 `configs/default.yaml` 的 `admin_token` 和 `admin_emails`
  - 可补充：拼字页「保存/续编 project.json」（后端已有 project 文件机制）、导出 TTF 时合并人工候选、IP 限流第二道防线

## 9. 重要历史背景

- 拆字表：`data/components/decomp.json`（6763 字，IDC 树解析，一级 3755 全覆盖）+ `parts.txt`
- 部件库 V2：458 个部件真件（保留纵横比 + std_box 元数据）→ `data/components/parts/U{code:04X}.png` + `parts_meta.json`（`src/stage_parts.py` 的 build）
- 字体工程：simsun 标准字形 128×128（`data/stdsrc/`）；手写 256×256（`data/processed/`）
- 全部 CLI 入口见 `src/cli.py`（init/import/preprocess/classify/anchors/components/build_parts/assemble/train/generate/qa/rework/export/review），其中自动生成相关命令已废弃但保留入口
