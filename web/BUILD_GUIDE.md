# Web Browser Executable Build Guide

## 快速开始

### 1. 安装 PyInstaller
```bash
pip install pyinstaller
```

### 2. 构建 exe
在 `web` 目录下运行：

#### Windows (PowerShell):
```powershell
cd web
pyinstaller web_browser.spec --distpath ..\bin --buildpath ..\build
```

#### Windows (CMD):
```cmd
cd web
pyinstaller web_browser.spec --distpath ..\bin --buildpath ..\build
```

或直接双击 `build_exe.bat`

### 3. 输出文件
生成的exe位置：`../bin/web_browser.exe`

### 4. 在 main.py 中使用
修改 main.py 中的"三方工具"按钮处理：

```python
from launcher import launch_process
import os

# 在 main.py 的 create_tray 方法中
for name in features:
    if name == "三方工具":
        # 启动 web_browser.exe
        exe_path = os.path.join(os.path.dirname(__file__), "bin", "web_browser.exe")
        act.triggered.connect(lambda checked, path=exe_path: launch_process(path))
    else:
        act.triggered.connect(
            lambda checked, n=name: QtWidgets.QMessageBox.information(
                None, n, f"从托盘打开：{n}"
            )
        )
```

## 文件说明

- `web_app.py` - 独立web应用入口，包含main函数
- `web_browser_widget.py` - BrowserWidget核心组件
- `web_profile.py` - 浏览器profile管理（缓存、存储）
- `web_browser.spec` - PyInstaller配置文件
- `build_exe.bat` - Windows自动构建脚本

## 注意事项

1. **首次运行较慢**：exe启动时会解压依赖包，首次较慢是正常的
2. **缓存位置**：浏览器数据存储在 `%APPDATA%\InkLink\web_cache\`
3. **多进程**：可以同时运行多个web_browser.exe实例
4. **打包大小**：完整的exe约200-300MB（包含PySide6和Chromium）

## 进阶选项

如果要减小exe大小，可以修改 `web_browser.spec`：
- 移除 `pyqtdarktheme` (如果不需要)
- 设置 `upx=False` (禁用UPX压缩)
- 使用 `--onefile` 打包成单文件（更简洁但启动稍慢）

## 故障排除

**exe启动失败**
1. 确保PySide6已安装：`pip install PySide6>=6.5`
2. 检查 `web_profile.py` 是否在同目录
3. 运行 `web_app.py` 直接测试：`python web_app.py`

**缺少依赖**
- 更新 `web_browser.spec` 中的 `hiddenimports` 列表
