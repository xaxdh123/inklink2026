# Web 功能模块文档

## 概述

`web` 文件夹现在包含一个可复用的基础功能窗口系统，支持：
- 顶部功能按钮栏（撑满）
- QStackedWidget 页面缓存
- 网页链接（QWebEngineView）和原生 QWidget 混合使用
- 页面状态持久化（缓存、表单数据等）
- **WebQtChannel 双向通信**（JavaScript ↔ Python）

## 文件结构

```
web/
├── base_feature_window.py    # 基础功能窗口基类（支持 WebChannel）
├── web_browser_widget.py     # 浏览器组件（基于基类，带工具栏）
├── web_profile.py            # WebEngine profile 管理（缓存配置）
├── web_channel_bridge.py     # WebChannel 桥接对象
├── web_app.py                # 浏览器应用入口（三方工具）
├── build_exe.bat             # web_browser 打包脚本
├── web_browser.spec          # web_browser PyInstaller 配置
├── BUILD_GUIDE.md            # 构建指南
├── WEBCHANNEL_USAGE.md       # WebChannel 使用指南
├── README.md                 # 本文档
└── customer_service/         # 客服中心应用
    ├── customer_service_app.py
    ├── customer_service.spec
    ├── build.bat
    └── README.md
```

## 快速开始

### 1. 使用 BaseFeatureWindow 创建功能窗口

```python
from base_feature_window import BaseFeatureWindow

# 纯网页链接
features = {
    "设计中心": "https://design.example.com",
    "排版中心": "https://typeset.example.com",
}

window = BaseFeatureWindow(features, window_title="功能中心")
window.show()
```

### 2. 混合使用网页和原生 Widget

```python
from base_feature_window import BaseFeatureWindow
from PySide6 import QtWidgets

def create_settings():
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.addWidget(QtWidgets.QLabel("设置页面"))
    return widget

features = {
    "设计中心": "https://design.example.com",  # 网页
    "设置": create_settings,                    # 原生Widget
}

window = BaseFeatureWindow(features)
window.show()
```

### 3. 使用 BrowserWidget（带工具栏）

```python
from web_browser_widget import BrowserWidget

presets = {
    "Google": "https://www.google.com",
    "Wikipedia": "https://www.wikipedia.org",
}

window = BrowserWidget(presets)
window.show()
```

## 功能特性

### BaseFeatureWindow

**核心特性：**
- ✅ 顶部按钮栏（自动撑满）
- ✅ QStackedWidget 页面缓存
- ✅ 延迟加载（首次点击时创建页面）
- ✅ 支持网页链接和原生 Widget
- ✅ 页面状态持久化
- ✅ **WebQtChannel 双向通信**（JavaScript ↔ Python）

**API：**
```python
# 添加功能
window.add_feature("新功能", "https://example.com")

# 移除功能
window.remove_feature("功能名")

# 获取页面
page = window.get_page("功能名")

# 设置自定义样式
window.set_style("QPushButton { ... }")
```

### BrowserWidget

**额外特性：**
- ✅ 工具栏（前进、后退、刷新）
- ✅ 地址栏
- ✅ 进度条
- ✅ URL 自动补全

## 创建新功能模块

### 示例：设计中心

```python
from base_feature_window import BaseFeatureWindow

class DesignCenterWindow(BaseFeatureWindow):
    def __init__(self, parent=None):
        features = {
            "设计工具": "https://design.example.com/tools",
            "素材库": "https://design.example.com/materials",
            "模板": "https://design.example.com/templates",
        }
        super().__init__(
            features=features,
            profile_name="design_center",
            parent=parent,
            window_title="设计中心"
        )
```

### 示例：混合功能

```python
from base_feature_window import BaseFeatureWindow
from PySide6 import QtWidgets

def create_local_tool():
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    btn = QtWidgets.QPushButton("本地工具")
    layout.addWidget(btn)
    return widget

class MixedFeatureWindow(BaseFeatureWindow):
    def __init__(self, parent=None):
        features = {
            "在线工具": "https://online.example.com",  # 网页
            "本地工具": create_local_tool,              # 原生Widget
        }
        super().__init__(features=features, parent=parent)
```

## 页面缓存机制

1. **延迟加载**：页面在首次点击时创建
2. **持久缓存**：创建的页面保存在 `page_cache` 中
3. **状态保持**：网页的滚动位置、表单数据等自动保存
4. **Profile 隔离**：每个功能使用独立的 WebEngine profile

## WebChannel 通信

BaseFeatureWindow 集成了 WebQtChannel，支持 JavaScript 和 Python 双向通信：

- ✅ **JavaScript 调用 Python**：注册处理器后，JS 可以调用 Python 方法
- ✅ **Python 调用 JavaScript**：执行 JS 代码或调用 JS 函数
- ✅ **消息传递**：双向消息传递机制

### 快速示例

```python
# Python 端
window.register_js_handler("功能名", "getData", lambda: {"result": "data"})

# JavaScript 端
window.addEventListener('qtwebchannelready', function(event) {
    const bridge = event.detail.bridge;
    const result = JSON.parse(bridge.call('getData'));
    console.log(result);
});
```

详细使用说明请查看 [WEBCHANNEL_USAGE.md](WEBCHANNEL_USAGE.md)

## 样式定制

### 默认样式

```python
DEFAULT_STYLE = """
    QFrame#buttonBar {
        background-color: #2b2b2b;
        border-bottom: 1px solid #444;
    }
    QPushButton {
        background-color: #3d3d3d;
        color: #e0e0e0;
        ...
    }
"""
```

### 自定义样式

```python
window.set_style("""
    QPushButton {
        background-color: #your-color;
        ...
    }
""")
```

## 打包为 exe

每个功能模块可以独立打包为 exe。参考 `customer_service` 文件夹的结构：

### 创建新功能模块

1. 在 `web` 目录下创建功能文件夹（如 `design_center`）
2. 创建应用文件（如 `design_center_app.py`）
3. 创建打包脚本和配置文件
4. 运行打包脚本生成 exe

### 示例：客服中心

客服中心应用已作为示例，位于 `web/customer_service/`：

```bash
cd web/customer_service
build.bat
```

打包后的 exe 位于 `..\..\bin\customer_service.exe`

### 创建其他功能模块

可以参考 `customer_service` 的结构创建其他功能模块：
- `design_center/` - 设计中心
- `typesetting_center/` - 排版中心
- `review_center/` - 审核中心

## 注意事项

1. **Profile 名称**：不同功能使用不同的 `profile_name`，实现缓存隔离
2. **Widget 工厂函数**：原生 Widget 必须通过工厂函数返回，不能直接传入实例
3. **页面生命周期**：页面在窗口关闭时自动清理
4. **错误处理**：网页加载失败时会显示错误提示页面

## 示例文件

- `example_features.py` - 代码示例，展示如何使用 BaseFeatureWindow
- `customer_service/` - 完整的客服中心应用示例（可打包为 exe）

## 功能模块

### 客服中心

完整的客服中心应用，位于 `customer_service/` 文件夹：
- 基于 `BrowserWidget` 创建
- 包含预设页面（Google, Wikipedia, Python, ChatBox）
- 支持独立打包为 exe
- 可从主应用的悬浮窗启动

查看 `customer_service/README.md` 了解详细使用说明。
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
# WebChannel 使用指南

BaseFeatureWindow 现在支持 WebQtChannel，允许网页与 Python 进行双向通信。

## 功能特性

- ✅ JavaScript 调用 Python 方法
- ✅ Python 调用 JavaScript 代码
- ✅ Python 向 JavaScript 发送消息
- ✅ 自动注入 WebChannel 库
- ✅ 每个功能页面独立的桥接对象

## JavaScript 调用 Python

### 1. 在 Python 中注册处理器

```python
from web.base_feature_window import BaseFeatureWindow

class MyWindow(BaseFeatureWindow):
    def __init__(self, parent=None):
        features = {
            "我的功能": "https://example.com",
        }
        super().__init__(features=features, parent=parent)
        
        # 注册 JavaScript 可以调用的方法
        self.register_js_handler("我的功能", "getUserInfo", self.handle_get_user_info)
        self.register_js_handler("我的功能", "saveData", self.handle_save_data)
    
    def handle_get_user_info(self, user_id):
        """处理来自 JavaScript 的调用"""
        return {
            "id": user_id,
            "name": "用户名",
            "email": "user@example.com"
        }
    
    def handle_save_data(self, data):
        """保存数据"""
        print(f"收到数据：{data}")
        return {"success": True}
```

### 2. 在 JavaScript 中调用

```javascript
// 等待 WebChannel 就绪
window.addEventListener('qtwebchannelready', function(event) {
    const bridge = event.detail.bridge;
    
    // 调用 Python 方法
    // 方法1：使用 call 方法（返回 JSON 字符串）
    const result = JSON.parse(bridge.call('getUserInfo', JSON.stringify(123)));
    console.log('用户信息:', result);
    
    // 方法2：直接调用（需要 Python 方法支持）
    bridge.getUserInfo(123).then(result => {
        console.log('用户信息:', result);
    });
    
    // 保存数据
    bridge.call('saveData', JSON.stringify({key: 'value'})).then(result => {
        const response = JSON.parse(result);
        if (response.success) {
            alert('保存成功！');
        }
    });
});
```

## Python 调用 JavaScript

```python
# 执行 JavaScript 代码
window.call_js("我的功能", """
    console.log('来自 Python 的消息');
    alert('Hello from Python!');
""")

# 调用 JavaScript 函数
window.call_js("我的功能", """
    if (typeof myFunction === 'function') {
        myFunction('参数1', '参数2');
    }
""")
```

## Python 向 JavaScript 发送消息

```python
# 发送消息到 JavaScript
window.send_message_to_js("我的功能", "dataUpdated", {
    "message": "数据已更新",
    "timestamp": "2024-01-01 12:00:00"
})
```

在 JavaScript 中接收：

```javascript
// 方式1：监听 signal
window.addEventListener('qtwebchannelready', function(event) {
    const bridge = event.detail.bridge;
    bridge.message_received.connect(function(eventName, data) {
        if (eventName === 'dataUpdated') {
            console.log('收到消息:', data);
        }
    });
});

// 方式2：监听自定义事件
window.addEventListener('dataUpdated', function(event) {
    console.log('数据已更新:', event.detail);
});
```

## 完整示例

### Python 端

```python
from web.base_feature_window import BaseFeatureWindow
from PySide6 import QtWidgets

class ExampleWindow(BaseFeatureWindow):
    def __init__(self, parent=None):
        features = {
            "示例": "https://example.com",
        }
        super().__init__(features=features, parent=parent)
        
        # 注册处理器
        self.register_js_handler("示例", "getConfig", self.get_config)
        self.register_js_handler("示例", "showMessage", self.show_message)
    
    def get_config(self):
        """返回配置信息"""
        return {
            "theme": "dark",
            "language": "zh-CN",
            "version": "1.0.0"
        }
    
    def show_message(self, message):
        """显示消息框"""
        QtWidgets.QMessageBox.information(self, "消息", message)
        return {"success": True}
```

### JavaScript 端

```html
<!DOCTYPE html>
<html>
<head>
    <title>WebChannel 示例</title>
</head>
<body>
    <h1>WebChannel 示例</h1>
    <button onclick="testCallPython()">调用 Python</button>
    <button onclick="testReceiveMessage()">接收消息</button>
    
    <script>
        let bridge = null;
        
        // 等待 WebChannel 就绪
        window.addEventListener('qtwebchannelready', function(event) {
            bridge = event.detail.bridge;
            console.log('WebChannel 已连接');
        });
        
        function testCallPython() {
            if (!bridge) {
                alert('WebChannel 尚未就绪');
                return;
            }
            
            // 获取配置
            const config = JSON.parse(bridge.call('getConfig'));
            console.log('配置:', config);
            
            // 显示消息
            const result = JSON.parse(bridge.call('showMessage', JSON.stringify('Hello from JavaScript!')));
            if (result.success) {
                console.log('消息已显示');
            }
        }
        
        function testReceiveMessage() {
            if (!bridge) {
                alert('WebChannel 尚未就绪');
                return;
            }
            
            // 监听消息
            bridge.message_received.connect(function(eventName, data) {
                console.log('收到消息:', eventName, data);
                alert(`收到消息: ${eventName}\n数据: ${JSON.stringify(data)}`);
            });
        }
    </script>
</body>
</html>
```

## API 参考

### BaseFeatureWindow 方法

#### `register_js_handler(feature_name: str, method_name: str, handler: Callable)`
注册 JavaScript 调用处理器。

#### `call_js(feature_name: str, script: str)`
在指定功能的页面中执行 JavaScript 代码。

#### `send_message_to_js(feature_name: str, event_name: str, data: dict)`
向指定功能的 JavaScript 发送消息。

#### `get_bridge(feature_name: str) -> Optional[WebChannelBridge]`
获取指定功能的 WebChannel 桥接对象。

### WebChannelBridge 方法（JavaScript 端）

#### `bridge.call(method: str, ...args: str) -> str`
调用 Python 方法，返回 JSON 字符串。

#### `bridge.message_received`
信号，当 Python 发送消息时触发。

## 注意事项

1. **等待就绪**：确保在 `qtwebchannelready` 事件后再使用 `window.bridge`
2. **JSON 序列化**：通过 `call` 方法传递的参数需要 JSON 序列化
3. **异步处理**：JavaScript 调用 Python 是异步的，使用 Promise 或回调处理结果
4. **错误处理**：Python 方法出错时会返回包含 `error` 字段的 JSON

## 调试技巧

```javascript
// 检查 WebChannel 状态
console.log('Bridge available:', typeof window.bridge !== 'undefined');
console.log('Bridge object:', window.bridge);

// 监听所有事件
window.addEventListener('qtwebchannelready', function(event) {
    console.log('WebChannel ready!', event.detail);
});
```
