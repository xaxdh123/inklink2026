# CLAUDE.md — InkLink2026 Codebase Guide

This document is intended for AI assistants (e.g., Claude) working on this repository. It describes the project structure, conventions, workflows, and important context needed to contribute effectively.

---

## Project Overview

**InkLink2026** is a Windows desktop application for print industry workflow management. It is built with Python + PySide6 (Qt) and packaged into standalone executables via PyInstaller.

The application consists of:
- A **main tray application** (`trayapp/`) that acts as the central launcher and coordinator.
- **7 independent sub-modules**, each a separate executable for a specific business domain.
- A **shared web framework** (`web/`) for embedding web-based UIs with bidirectional Python↔JavaScript communication.
- **Shared utilities** (`utils/`) used across all modules.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.x |
| GUI Framework | PySide6 6.10.1 (Qt) |
| Theme | pyqtdarktheme (dark mode) |
| Packaging | PyInstaller 6.17.0 |
| HTTP Client | urllib3, requests, httpx |
| Cloud Storage | Tencent COS (`cos_python_sdk_v5`) |
| Image Processing | Pillow 12.1.0, PyMuPDF 1.26.7 |
| PDF/Layout | PyMuPDF |
| ORM / DB | SQLAlchemy 2.0.45 (limited use) |
| Cryptography | pycryptodome 3.23.0 |
| System Utilities | psutil 7.2.1, pywin32 311 |
| Formatting | black 26.1.0 |
| Debugging | debugpy |

Full dependency list: `requirements.txt`

---

## Repository Structure

```
inklink2026/
├── main.py                  # Entry point — launches TrayApp
├── sub_module.py            # Sub-module dispatcher (CLI args select which module)
├── config.ini               # Runtime configuration (paths, credentials, UI settings)
├── requirements.txt         # Python dependencies (pinned versions)
├── build_exe.bat            # Windows build script (PyInstaller)
├── main.spec                # PyInstaller spec for main.exe
├── ink2026.spec             # PyInstaller spec for all sub-modules
├── wmi.py                   # WMI/system info utilities
├── updater.bat              # Self-update script
│
├── trayapp/                 # Main tray application
│   ├── tray_app.py          # TrayApp: tray icon, login, module launching
│   ├── login_window.py      # Login UI
│   ├── floating_window.py   # Floating widget for quick access
│   ├── constant.py          # All constants: API URLs, component map, COS config
│   ├── launcher_utils.py    # Process launch + singleton detection
│   └── cos_utils.py         # Tencent COS operations (upload/download)
│
├── utils/
│   ├── __init__.py          # Global singletons: GLOB_CONFIG, GLOB_NETWORK; unit conversion
│   └── network.py           # ApiClient: HTTP requests, Bearer token auth, connection pooling
│
├── web/                     # Shared web framework
│   ├── base_feature_window.py   # Base class for web-embedded feature windows
│   ├── web_browser_widget.py    # BrowserWidget with toolbar (nav, address, progress)
│   ├── web_profile.py           # WebEngine profile management
│   ├── web_channel_bridge.py    # JS↔Python bidirectional bridge
│   └── QNetworkHttpClient.py    # HTTP client for web layer
│
├── audit_center/            # Audit Center module
├── customer_service/        # Customer Service module
├── design_center/           # Design Center (Adobe Illustrator integration)
│   ├── design_util.py
│   ├── design_worker.py
│   └── SingleSelectDialog.py
├── floating_plugin/         # Floating plugin/popup module
├── layout_center/           # Layout/Typesetting Center
│   ├── ProofTS/             # Proof typesetting system
│   └── Roll_Splice/         # Roll splicing algorithm (get_best3–6 variants)
├── system_setting/          # System Settings + update checker
├── third_party/             # Third-party tool integrations
│
├── javascript/              # FP-*.js scripts (floating plugin JS resources)
├── resources/               # Icons, templates, assets
└── .vscode/
    └── launch.json          # Debug configs for each module
```

---

## Module Architecture

Each sub-module follows a consistent pattern:

```
<module_name>/
├── <module_name>.py         # Main class (e.g., DesignCenter, AuditCenter)
├── app.py                   # Application wrapper / entry point
└── __init__.py              # Module initializer
```

Sub-modules are launched as **separate processes** by the tray app. Each sub-module can also run standalone via `sub_module.py --mode <module_name>`.

---

## Entry Points

| Script | Purpose |
|---|---|
| `main.py` | Starts the TrayApp (system tray icon + coordinator) |
| `sub_module.py` | Runs a specific sub-module by name (CLI arg: `--mode`) |

---

## Configuration

### `config.ini`
The primary runtime configuration file, managed via Python's `configparser`. Key sections:

| Section | Purpose |
|---|---|
| `[General]` | Typeset sequence counter |
| `[auth]` | Stored credentials and JWT token |
| `[page]` | Page layout thresholds and sizes |
| `[rect]` | Rectangle dimensions per format |
| `[storage]` | Work list patterns and combinations |
| `[ui]` | Paths (`src_path`, `dest_path`) and timing (`delay_time`, `over_time`) |

### Global Singletons (`utils/__init__.py`)
- `GLOB_CONFIG` — App-wide QSettings-based config accessor
- `GLOB_NETWORK` — Shared `ApiClient` instance for HTTP operations

---

## Networking / API

**Base URL**: `https://private.qiyinbz.com:31415/`

**Client**: `utils/network.py` → `ApiClient`
- Supports sync (`urllib_get`, `urllib_post`) and async variants
- Bearer token authentication (token stored in `config.ini [auth]`)
- Connection pooling via `urllib3.PoolManager`
- Retry logic on network errors

**Key Endpoints** (defined in `trayapp/constant.py`):

| Constant | URL |
|---|---|
| `API_LOGIN_URL` | `.../permission-api/loginQyMac` |
| `SETTING_USER_URL` | `https://admin.qiyinbz.com/permission/user/profile` |
| `SETTING_MSG_URL` | `https://admin.qiyinbz.com/permission/index` |
| `FLOAT_QUO_URL` | `https://admin.qiyinbz.com/quotate-page/...` |
| `DESIGN_CENTER_URL` | `https://admin.qiyinbz.com/erp/design/designSheetList` |

---

## Web Framework (`web/`)

Provides embedded browser windows with Python↔JavaScript communication. Key classes:

- **`BaseFeatureWindow`** — Extend this for any web-based feature. Provides `QStackedWidget` for lazy-loaded pages and `WebChannel` integration.
- **`WebBrowserWidget`** — Full browser widget with navigation toolbar.
- **`WebChannelBridge`** — Registers Python objects as JavaScript-callable. JavaScript calls land in Python slots; Python can call `runJavaScript()` back.
- **`WebProfile`** — Manages cache/storage paths under `%APPDATA%\InkLink\web_cache\`.

---

## Build System

### Build all executables (Windows)
```bat
build_exe.bat
```

This runs `pyinstaller` with `main.spec` (for `main.exe`) and `ink2026.spec` (for all sub-modules). Outputs land in `./bin/`.

### Directory structure after build
```
bin/
├── main/main.exe
├── customer_service/customer_service.exe
├── floating_plugin/floating_plugin.exe
├── system_setting/system_setting.exe
├── third_party/third_party.exe
├── design_center/design_center.exe
├── audit_center/audit_center.exe
└── layout_center/layout_center.exe
```

### Code signing
`build_exe.bat` invokes `signtool` if available for signing the output executables.

---

## Update System

1. Version info fetched from Tencent COS: `ver-info.json`
2. `system_setting/` module contains `UpdateCheckWorker` (background thread)
3. Patches downloaded to `new_version/<sub_dir>/`
4. `updater.bat` copied to `bin/` to apply updates

---

## Code Conventions

### Naming
| Element | Style |
|---|---|
| Files | `snake_case.py` |
| Classes | `PascalCase` |
| Constants | `UPPER_SNAKE_CASE` |
| Variables/functions | `snake_case` |

### Error Handling
- Use `try/except` broadly; log exceptions to `except_log.txt` via `traceback`
- Use `QMessageBox` for user-facing error dialogs
- Never silently swallow critical exceptions

### Threading
- Long-running operations (network, file I/O) must run in background `QThread` workers or `threading.Thread`
- Never block the Qt main thread
- Use Qt signals/slots for thread-to-UI communication

### GUI Patterns
- Inherit from `QMainWindow`, `QWidget`, or `QDialog` as appropriate
- Use Qt stylesheets (CSS-like) for theming; respect the dark theme from `pyqtdarktheme`
- Use `QStackedWidget` for multi-page UIs (lazy loading supported via `BaseFeatureWindow`)
- Signal/slot pattern for all event handling

### Comments
- The codebase uses **Chinese-language comments** throughout (the product targets Chinese users)
- Write new comments in Chinese to stay consistent with the existing style
- Use docstrings for public methods and classes

### Imports
- Standard library imports first, then third-party, then local
- Avoid wildcard imports (`from module import *`)

---

## Running Locally (Development)

### Prerequisites
- Python 3.x (Windows recommended — pywin32 is required)
- Install dependencies: `pip install -r requirements.txt`

### Run main app
```bash
python main.py
```

### Run a specific sub-module
```bash
python sub_module.py --mode design_center
python sub_module.py --mode audit_center
python sub_module.py --mode layout_center
# etc.
```

### Debug in VSCode
Use `.vscode/launch.json` — pre-configured debug targets exist for each module and for `main.py`.

---

## Testing

There is **no automated test suite** in this repository. Testing is done manually:
- Run individual modules via `sub_module.py` or VSCode debug configs
- Verify functionality through the UI

When adding new code, ensure it can be manually exercised by running the relevant module.

---

## Important Files to Know

| File | Why It Matters |
|---|---|
| `trayapp/constant.py` | All API URLs, component mappings, COS credentials |
| `utils/__init__.py` | Global config + network singletons |
| `utils/network.py` | All HTTP communication logic |
| `web/base_feature_window.py` | Base class for web-embedded windows |
| `web/web_channel_bridge.py` | JS↔Python bridge implementation |
| `config.ini` | Runtime config (credentials, paths, timing) |
| `requirements.txt` | Pinned dependency versions |

---

## Security Notes

> **Important**: The following are known issues; do not copy this pattern for new code.

- **Hard-coded COS credentials** exist in `trayapp/constant.py` — avoid exposing or committing new secrets
- **Plain-text credentials** stored in `config.ini` — this is existing behavior; do not add more
- **Bearer token** stored locally without encryption

When adding new features that require credentials, use environment variables or secure storage rather than hard-coding.

---

## Platform Constraints

- This application is **Windows-only** (`pywin32`, WMI, Windows paths, `.bat` build scripts)
- File paths use Windows conventions (`%APPDATA%`, backslashes in some places)
- Do not introduce Linux/macOS-only APIs

---

## Git Workflow

- Main branch: `master` / `main`
- Feature branches: descriptive names, e.g. `claude/add-feature-XYZ`
- Commit messages: short imperative summary in English or Chinese
- No CI/CD pipeline — manual build and test

---

## ProofTS 拼版组件详细架构

`layout_center/ProofTS/` 包含两个核心拼版组件，分别对应 LayoutCenter 的两个 Tab。

### 组件总览

```
LayoutCenter (BrowserWidget)
├── Tab: 打样专版 → OneComb (QWidget)          # 自动拼版
│   ├── QThread (_faker) → MainWorker           # 主循环：扫描文件 → 拼版 → 上传
│   └── AutoThread                              # 后台轮询：5秒/次，超时自动合版
├── Tab: 打样手排 → SlowCom (QWidget)           # 手动排版
│   └── ApplicationManager → QThreadPool       # 线程池，每单一个 MyReusableTask
└── Tab: 卷筒拼版 → RollWidget                  # 卷筒拼版算法（子进程）
```

---

### OneComb — 自动拼版（`comb/`）

#### 文件结构

| 文件 | 类 | 说明 |
|------|----|------|
| `comb/oneCom.py` | `OneComb(QWidget)` | UI层：路径配置、启动/停止按钮、日志浏览器 |
| `comb/MainWorker.py` | `MainWorker(QObject)` | 核心逻辑：文件扫描、拼版计算、.NET调用、上传 |
| `comb/AutoThread.py` | `AutoThread(QThread)` | 后台自动合版线程（5秒轮询） |
| `comb/FileObj.py` | `FileObj` | 文件数据模型：解析文件名元数据、计算放置参数 |
| `comb/__init__.py` | — | 工具函数：坐标计算、版号生成 |

#### 数据流

```
源目录 PDF 文件
  ↓ loop_find_file()  正则解析文件名，构建 FileObj
  ↓ FileObj.gen_size()  读取 PDF 实际尺寸
  ↓ FileObj.gen_params()  计算各版型的放置包围盒
  ↓ judge_fixed() / judge_same() / judge_page()  选择最优版型
  ↓ handle_files()  按 customer+mate+craft 分组等待配对
  ↓ placed_file()  → .NET SinglePack  执行拼版，生成印刷+线稿 PDF
  ↓ place_end()   加版号/二维码/文字戳，分割多页，移动文件
  ↓ 上传 T3 ERP 系统（标准设计）/ 生产API（不干胶设计）
  ↓ 成品移动到 print / line / cutting 目录
```

#### 文件名解析规则

自动拼版通过正则从 PDF 文件名中提取全部元数据：

```
文件名格式: {店铺}^{客户}^{数量}^{工艺}^{素材}^{设计号}^{宽x高}^{备注}^{?}^{?}^{?}.pdf
解析正则:   (.+)^(.+)^(\d+)^(.+)^(.+)^(.+)^(\d+x\d+)^(.*)^(\d+)^(.+)^(.+).pdf
```

`design`（设计号）字段后缀的特殊含义：

| 后缀 | 含义 |
|------|------|
| `拼多个[m][n]` | 多拼模式，m=列数，n=行数 |
| `[deep_cut]` | 需要深刀线 |
| `[no_cut]` | 不裁切 |

#### 版型选择策略

`judge_fixed()` → `judge_same()` → `judge_page()` 依次尝试：

| 方法 | 适用场景 | 逻辑 |
|------|----------|------|
| `judge_fixed()` | A3/A4/A5 固定尺寸 | 直接匹配固定格式，无需计算 |
| `judge_same()` | 可重复摆放的单品 | 优先最高利用率版型（1/2/4拼） |
| `judge_page()` | 通用 | 选总页数最少的版型 |

#### 线程并发模型

```
Qt 主线程
├── OneComb UI（按钮、日志、路径输入）
└── 信号接收（message_signal → signal_work()）

_faker（QThread）
└── MainWorker.start()  主扫描循环（阻塞运行）

AutoThread（QThread）
└── 每5秒：检查超时 → comb_files() → 调用 worker.placed_file()/place_end()
    ⚠️ 与 MainWorker 共享同一实例，通过 _do_next 标志协调
```

> **注意**：`AutoThread` 和 `MainWorker` 共享同一个 `MainWorker` 实例，
> `GLOB_CONFIG["half_quarter_page"]` 组作为跨线程共享状态缓存半版/四版队列，
> 修改此区域代码时需注意线程安全。

#### .NET 集成点（`comb/MainWorker.py`）

| .NET 方法 | 调用位置 | 作用 |
|-----------|----------|------|
| `SinglePack` (ClassLibrary1) | `placed_file()` | 核心拼版算法，计算最优排布 |
| `AddTextStamp` (Pack) | `place_end()` | 向 PDF 添加文字印章（版号/订单信息） |
| `AddQRStamp` (Pack) | `place_end()` | 向 PDF 添加二维码 |
| `setNo` (Pack) | `place_end()` | 在 PDF 中写入版号 |
| `addFiles` (ClassLibrary1) | `placed_file()` | 向拼版引擎输入文件路径列表 |
| `addImg` (ClassLibrary1) | `placed_file()` | 向拼版引擎输入图像数据 |

#### 信号/槽连接（OneComb）

| 信号来源 | 信号 | 目标槽 | 用途 |
|----------|------|--------|------|
| `_faker` (QThread) | `started` | `MainWorker.start()` | 启动主扫描循环 |
| `_faker` | `finished` | `_faker.deleteLater()` | 清理线程资源 |
| `MainWorker` | `message_signal(obj)` | `OneComb.signal_work(obj)` | 状态更新/日志/UI控制 |
| `AutoThread` | `__sign_auto` | `OneComb.signal_work()` | 自动合版完成通知 |

`message_signal` 的 `obj` 消息类型：

| `obj["action"]` | 含义 |
|-----------------|------|
| `"done"` | 主循环结束，恢复 UI |
| `"auto_done"` | 自动合版结束，恢复监听按钮 |
| `"next"` | 允许 worker 处理下一批 |
| `"msg"` | 日志文本，追加到浏览器 |
| `"typeset"` | 更新当前版号显示 |
| `"RETRY_UPLOAD"` | 弹出重试对话框 |

#### 配置键（`config.ini` `[ui]` 和 `[rect]` 节）

| 键 | 说明 |
|----|------|
| `ui/src_path` | 源目录（待拼版 PDF） |
| `ui/src_mv_path` | 备份目录（处理后源文件移至此） |
| `ui/dest_path` | 印刷输出目录 |
| `ui/dest_2_path` | 线稿输出目录 |
| `ui/dest_dao_path` | 刀线输出目录 |
| `ui/delay_time` | 等待文件完整上传的延迟秒数 |
| `ui/over_time` | AutoThread 超时时长（分钟） |
| `ui/space_item` | 拼版元素间距（mm） |
| `rect/single` | 单版画布尺寸 |
| `rect/half` | 双版画布尺寸 |
| `rect/quart` | 四版画布尺寸 |
| `page/single_threshold` | 单版空间阈值 |
| `page/single_extra` | 单版额外空间 |
| `page/outline_size` | 允许的裁切尺寸列表 |
| `storage/can_work_list` | 可处理的工艺过滤正则列表 |
| `storage/combine_multi` | 多拼模式匹配字符串 |
| `half_quarter_page/*` | 半版/四版等待队列缓存（跨线程） |

---

### SlowCom — 手动排版（`manual/`）

#### 文件结构

| 文件 | 类 | 说明 |
|------|----|------|
| `manual/slowCom.py` | `SlowCom(QWidget)` | UI层：订单搜索、选择、提交 |
| `manual/MainWorker.py` | `ApplicationManager(QObject)` | 线程池管理器 |
| `manual/MainWorker.py` | `MyReusableTask(QObject, QRunnable)` | 单个排版任务（在线程池中执行） |
| `manual/ClickableLabel.py` | `ImageTextCheckBox(QWidget)` | 订单选择卡片（含缩略图异步加载） |
| `manual/ClickableLabel.py` | `ClickableLabel(QLabel)` | 可发出 clicked 信号的 Label |

#### 数据流

```
用户输入订单号 → search()
  ↓ POST production-api/produce/produceList
  ↓ 每条订单渲染为 ImageTextCheckBox（异步加载缩略图）

用户勾选订单 → create()
  ↓ GET production-api/typesettingNew/creatAdhesiveTypesettingNo
  ↓ 获取版号，填充 data_info（设计号/客户/素材/工艺/尺寸/数量）

用户点击提交 → start()
  ↓ ApplicationManager.submit_new_task({pName, cName, size, data, orders, remark})
  ↓ MyReusableTask 提交到 QThreadPool

MyReusableTask.run()（线程池）
  ↓ 重命名 PDF（含元数据）
  ↓ place_title_A3()  → .NET AddTextStamp（标题/备注/页数信息）
  ↓ place_qr_A3_page() → .NET AddQRStamp（每页版号二维码）
  ↓ place_qr_A3()     → .NET AddQRStamp（订单二维码）
  ↓ clr_move_file2_A3() → 按数量分级移动到输出目录 + 上传生产 API
  ↓ 清理临时文件 → 发出完成信号
```

#### 线程模型

```
Qt 主线程
├── SlowCom UI（搜索、勾选、提交按钮）
└── 信号接收（ApplicationManager.signal → recvMsg()）

QThreadPool.globalInstance()
├── MyReusableTask-1（任务1）
├── MyReusableTask-2（任务2）
└── ...（并发执行，互不干扰）
```

每个 `MyReusableTask` 独立持有自己的 .NET 引用和文件路径，线程间无共享状态。

#### .NET 集成点（`manual/MainWorker.py`）

| .NET 方法 | 调用位置 | 作用 |
|-----------|----------|------|
| `AddTextStamp` (Pack) | `place_title_A3()` | 添加标题、备注、页码文字戳 |
| `AddQRStamp` (Pack) | `place_qr_A3_page()` | 每页添加版号二维码 |
| `AddQRStamp` (Pack) | `place_qr_A3()` | 添加订单二维码 |

二维码通过 Python `qrcode` 库生成 → PIL 转为 200×200px TIFF → 字节数组传给 .NET。

#### 信号/槽连接（SlowCom）

| 信号来源 | 信号 | 目标槽 | 用途 |
|----------|------|--------|------|
| `MyReusableTask` | `signal(str)` | `SlowCom.recvMsg(str)` | 任务状态回调 |
| 印刷文件列表 | `clicked` | `SlowCom.listen()` | 同步刀线文件列表选中状态 |
| 备注输入框 | `textChanged` | `SlowCom.update_type()` | 刷新类型名称显示 |
| A3 切换按钮 | `clicked` | lambda | 切换尺寸输入框显示 |
| 清除按钮 | `clicked` | lambda | 在清除（x）和追加（+）模式间切换 |

`recvMsg` 的消息格式：

| 消息内容 | 含义 |
|----------|------|
| `"start"` | 任务开始，禁用输入，刷新文件列表 |
| 其他字符串 | 日志文本，追加到浏览器 |

#### 配置键

| 键 | 说明 |
|----|------|
| `ui/slow_src_path` | 手动源目录（印刷 PDF） |
| `ui/slow_src_mv_path` | 手动源目录（刀线 PDF） |
| `ui/slow_dest_path` | 手动输出目录（印刷+刀线） |
| `ui/slow_dest_dao_path` | 手动输出目录（刀线线稿） |
| `storage/data_order_no` | 按日期跟踪的订单计数（用于输出目录分级） |

#### API 端点（手动排版专用）

| 方法 | 路径 | 用途 |
|------|------|------|
| `POST` | `production-api/produce/produceList` | 搜索订单列表 |
| `GET` | `production-api/typesettingNew/creatAdhesiveTypesettingNo` | 创建版号 |

搜索支持两种策略：先按 `systemOrderNo`（订单号）搜索，无结果则按 `flowTbName`（品类）搜索。

---

### 两个组件的关键差异对比

| 维度 | OneComb（自动） | SlowCom（手动） |
|------|----------------|-----------------|
| **触发方式** | 自动扫描目录 | 用户手动搜索订单并提交 |
| **线程模型** | 单 QThread + AutoThread | QThreadPool（多任务并发） |
| **版型** | 1/2/4拼，自动算法选择 | 固定 A3 格式 |
| **文件来源** | 文件名含全部元数据 | 从 API 获取订单信息 |
| **上传目标** | T3 ERP + 生产 API | 生产 API 只 |
| **版号生成** | 本地生成（`get_typeset_no()`） | 从 API 获取 |
| **.NET 核心调用** | SinglePack（拼版算法） | AddTextStamp/AddQRStamp |
| **输出数量分级** | 无分级 | 按数量：1-2 / 3-10 / 11-30 / >30 |

---

### 调试建议

- 使用 `.vscode/launch.json` 中的 `layout_center` 配置可直接调试整个模块
- ProofTS 组件支持 `debugpy`，在 `MainWorker.start()` 和 `AutoThread.run()` 入口处会尝试 attach
- 两个组件均将错误写入 `except_log.txt`（`traceback.print_exc(file=...)`）
- `message_signal` 的 `"msg"` 消息会在 UI 日志中显示，是观察运行状态的主要手段

---

## Glossary

| Term | Meaning |
|---|---|
| TrayApp | Main tray icon application that coordinates all sub-modules |
| Sub-module | Independent feature executable (design_center, audit_center, etc.) |
| COS | Tencent Cloud Object Storage — used for patches and assets |
| ProofTS | Proof typesetting subsystem within layout_center |
| Roll_Splice | Roll splicing algorithm subsystem within layout_center |
| WebChannel | Qt WebChannel — JS↔Python bidirectional communication layer |
| GLOB_CONFIG | Global QSettings-backed config singleton |
| GLOB_NETWORK | Global ApiClient singleton for HTTP requests |
| OneComb | 自动拼版组件（打样专版 Tab），自动扫描文件目录并拼版 |
| SlowCom | 手动排版组件（打样手排 Tab），手动搜索订单并提交排版任务 |
| AutoThread | OneComb 中的后台轮询线程，每5秒检查超时并自动合版 |
| MyReusableTask | SlowCom 中每个排版任务的执行单元，在 QThreadPool 中运行 |
| FileObj | OneComb 中表示单个待拼版文件的数据模型 |
| ApplicationManager | SlowCom 中管理 QThreadPool 和任务列表的对象 |
