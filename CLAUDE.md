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
