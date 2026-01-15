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
