import os
import traceback
from typing import Callable, Any
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import QUrl, Signal, Qt, QPoint
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebChannel import QWebChannel

# 保持原有的导入结构
from web.web_profile import create_persistent_profile
from web.web_channel_bridge import WebChannelBridge


class CustomTitleBar(QtWidgets.QWidget):
    """自定义标题栏，支持拖拽和窗口控制"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(35)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(4)

        # macOS 风格控制按钮
        self.btn_close = self._create_control_button("#ff5f56")
        self.btn_max = self._create_control_button("#27c93f")
        self.btn_min = self._create_control_button("#ffbd2e")
        layout.addWidget(self.btn_close)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_min)
        layout.addSpacing(24)
        # 新增：地址栏 (占据中间位置)
        self.url_bar = QtWidgets.QLineEdit()
        self.url_bar.setPlaceholderText("URL")
        self.url_bar.setReadOnly(True)
        self.url_bar.setStyleSheet(
            """
            QLineEdit {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 4px;
                color: #ddd;
                padding: 2px 8px;
                font-size: 12px;
            }
        """
        )
        layout.addWidget(self.url_bar, 1)  # stretch=1 使其撑满中间

        layout.addSpacing(24)
        self.title_label = QtWidgets.QLabel("")
        self.title_label.setStyleSheet(
            "color: white; font-weight: bold; font-family: 'Microsoft YaHei';"
        )
        layout.addWidget(self.title_label)
        # 移除底部的 addStretch，让标题靠右

        self.btn_close.clicked.connect(self.window().close)
        self.btn_min.clicked.connect(self.window().showMinimized)
        self.btn_max.clicked.connect(self._toggle_maximize)

    def _create_control_button(self, color):
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(16, 16)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {color}; border-radius: 7px; border: none; }} QPushButton:hover {{ background-color: white; }}"
        )
        return btn

    def _toggle_maximize(self):
        if self.window().isMaximized():
            self.window().showNormal()
        else:
            self.window().showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window()._drag_pos = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.window().move(
                event.globalPosition().toPoint() - self.window()._drag_pos
            )
            event.accept()


class BaseFeatureWindow(QtWidgets.QWidget):
    create_page_signal = Signal(str)
    """基础功能窗口基类
    特性：
    - 顶部一排撑满的功能按钮
    - QStackedWidget 缓存所有页面（网页或原生Widget）
    - 支持网页链接（自动创建QWebEngineView）
    - 支持原生QWidget（通过工厂函数）
    - 页面状态持久化（网页缓存、表单数据等）
    """

    # 优化后的样式表
    MAIN_STYLE = """
        QWidget#mainContainer {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a237e, stop:1 #0d47a1);
            border-radius: 12px;
        }
        QFrame#topNavArea {
            background-color: rgba(255, 255, 255, 0.1);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        QPushButton.NavBtn {
            background-color: rgba(255, 255, 255, 0.15);
            color: #e0e0e0;
            border: none;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        QPushButton.NavBtn:hover {
            background-color: rgba(255, 255, 255, 0.3);
        }
        QPushButton.NavBtn:checked {
            background-color: #1565c0;
            color: white;
        }
        QStackedWidget {
            background-color: white;
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        }
    """

    def __init__(
        self,
        features: dict[str, str | Callable[[], QtWidgets.QWidget]] | None = None,
        profile_name: str = "default",
        parent: QtWidgets.QWidget | None = None,
        window_title: str = "功能窗口",
        token="",
    ):
        """
        初始化基础功能窗口

        Args:
            features: 功能字典，键为按钮名称，值为：
                     - str: URL字符串，将创建QWebEngineView
                     - Callable: 返回QWidget的工厂函数，用于原生Widget
            profile_name: WebEngine profile名称（用于网页缓存）
            parent: 父窗口
            window_title: 窗口标题
        """
        super().__init__(parent)
        # 1. 设置无边框和透明背景样式
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setWindowTitle(window_title)
        self.token = token

        self.features: dict[str, str | Callable[[], QtWidgets.QWidget]] = dict(
            features or {}
        )
        self.profile_name = profile_name

        # 页面缓存：按钮名称 -> QWidget
        self.page_cache: dict[str, QtWidgets.QWidget] = {}

        # 按钮映射：按钮名称 -> QPushButton
        self.button_map: dict[str, QtWidgets.QPushButton] = {}

        # 当前显示的页面
        self.current_page: QtWidgets.QWidget | None = None

        # WebChannel 桥接对象缓存：页面名称 -> WebChannelBridge
        self.channel_bridges: dict[str, WebChannelBridge] = {}
        self._drag_pos = QPoint()

        # 初始化UI（新样式）
        self._build_ui(window_title)
        # 初始化功能（业务逻辑）
        self._setup_features()

    def _build_ui(self, title):
        """重新构建UI布局，加入无边框圆角及顶部集成导航栏"""
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)  # 阴影/边缘留白

        self.container = QtWidgets.QFrame()
        self.container.setObjectName("mainContainer")
        self.container.setStyleSheet(self.MAIN_STYLE)
        self.main_layout.addWidget(self.container)

        layout = QtWidgets.QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. 自定义标题栏（包含控制按钮）
        self.title_bar = CustomTitleBar(self)
        self.title_bar.title_label.setText(title)
        layout.addWidget(self.title_bar)

        # 2. 组合式功能栏（工具组 + 业务按钮）
        self.top_nav = QtWidgets.QFrame()
        self.top_nav.setObjectName("topNavArea")
        self.top_nav.setFixedHeight(40)  # 减少高度
        nav_layout = QtWidgets.QHBoxLayout(self.top_nav)
        nav_layout.setContentsMargins(10, 2, 10, 2)
        nav_layout.setSpacing(10)

        # 工具组（后退、刷新、DevTools）
        self.btn_back = self._create_tool_btn("👈", "后退", self._web_back)
        self.btn_reload = self._create_tool_btn("", "刷新", self._web_reload)
        self.btn_dev = self._create_tool_btn("", "开发者工具", self._web_devtool)

        nav_layout.addWidget(self.btn_back)
        nav_layout.addWidget(self.btn_reload)
        nav_layout.addWidget(self.btn_dev)

        # 垂直分隔线
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setStyleSheet(
            "background-color: rgba(255,255,255,0.2); width: 1px; margin: 6px 2px;"
        )
        nav_layout.addWidget(line)

        # 业务功能按钮布局容器
        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_layout.setSpacing(5)
        nav_layout.addLayout(self.button_layout)

        # 移除 nav_layout.addStretch() 以允许按钮撑满

        layout.addWidget(self.top_nav)

        # 3. 内容切换区
        self.stacked = QtWidgets.QStackedWidget()
        layout.addWidget(self.stacked, 1)

    def _create_tool_btn(self, text, tip, callback):
        """辅助方法：创建统一样式的工具按钮"""
        btn = QtWidgets.QPushButton(text)
        btn.setToolTip(tip)
        btn.setFixedSize(24, 24)  # 稍微调小以适应 reduced height
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(255,255,255,0.1);
                color: white;
                border-radius: 12px;
                font-size: 12px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.25); }
        """
        )
        btn.clicked.connect(callback)
        return btn

    # ----------------------------------------------------------------
    # 以下为完全保留的原有业务逻辑方法
    # ----------------------------------------------------------------

    def _setup_features(self):
        """设置功能按钮和页面"""
        if not self.features:
            return
        for name in list(self.features.keys()):
            self._add_button_to_ui(name)
        if self.features:
            first_name = next(iter(self.features.keys()))
            self._switch_to_feature(first_name)

    def _add_button_to_ui(self, name):
        """业务逻辑：将按钮添加到布局"""
        btn = QtWidgets.QPushButton(name)
        btn.setProperty("class", "NavBtn")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        # 设置 Expanding 策略以撑满空间
        btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        btn.clicked.connect(lambda checked, n=name: self._on_feature_clicked(n))
        self.button_map[name] = btn
        self.button_layout.addWidget(btn)

    def _on_feature_clicked(self, name: str):
        """处理功能按钮点击"""
        self._switch_to_feature(name)

    def _switch_to_feature(self, name: str):
        """切换到指定功能页面"""
        if name not in self.features:
            return

        # 更新按钮状态
        for btn_name, btn in self.button_map.items():
            btn.setChecked(btn_name == name)

        # 获取或创建页面
        page = self._get_or_create_page(name)
        if not page:
            return

        # 切换到该页面
        if page not in [self.stacked.widget(i) for i in range(self.stacked.count())]:
            # 如果页面不在stacked中，添加它
            self.stacked.addWidget(page)

        # 设置当前页面
        self.stacked.setCurrentWidget(page)
        self.current_page = page

    def _ensure_token_param(self, url: str) -> str:
        if not self.token:
            return url
        parts = urlsplit(url)
        q = parse_qsl(parts.query, keep_blank_values=True)
        if not any(k == "token" for k, _ in q):
            q.append(("token", self.token))
        if not any(k == "no_layout" for k, _ in q):
            q.append(("no_layout", "1"))
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(q, doseq=True),
                parts.fragment,
            )
        )

    def _get_or_create_page(self, name: str) -> QtWidgets.QWidget | None:
        """获取或创建功能页面"""
        # 如果已缓存，直接返回
        if name in self.page_cache:
            return self.page_cache[name]

        # 创建新页面
        feature = self.features[name]

        if isinstance(feature, str):

            # URL字符串，创建QWebEngineView
            page = self._create_web_page(name, feature)
        elif callable(feature):
            # 工厂函数，创建原生QWidget
            try:
                page = feature()
                if not isinstance(page, QtWidgets.QWidget):
                    print(f"警告：功能 '{name}' 的工厂函数未返回QWidget")
                    return None
            except Exception as e:
                print(f"创建功能 '{name}' 的Widget时出错：{e}")
                return None
        else:
            print(f"错误：功能 '{name}' 的类型不支持：{type(feature)}")
            return None

        if page:
            # 缓存页面
            self.page_cache[name] = page
            # 添加到stacked（但不立即显示）
            self.stacked.addWidget(page)
            self.create_page_signal.emit(name)
        return page

    def _create_web_page(self, name: str, url: str) -> QtWidgets.QWidget:
        """创建网页页面"""
        try:

            # 创建profile（使用功能名称作为子profile，实现隔离）
            profile = create_persistent_profile(f"{self.profile_name}_{name}")

            # 创建WebEngineView
            view = QWebEngineView()
            page = QWebEnginePage(profile, view)
            view.setPage(page)

            # 创建并设置 WebChannel
            channel = QWebChannel(self)
            bridge = WebChannelBridge(self)
            bridge.web_view = view
            channel.registerObject("pyBridge", bridge)
            self.channel_bridges[name] = bridge

            # 设置 WebChannel 到页面
            page.setWebChannel(channel)

            # 加载URL
            view.setUrl(QUrl(self._ensure_token_param(url)))
            return view
        except Exception as e:
            print(f"创建网页页面 '{name}' 时出错：{e}")
            traceback.print_exc()
            error_widget = QtWidgets.QLabel(f"无法加载页面：{e}")
            error_widget.setAlignment(Qt.AlignCenter)
            error_widget.setStyleSheet("color: #ff4444; padding: 20px;")
            return error_widget

    def add_feature(self, name: str, feature: str | Callable[[], QtWidgets.QWidget]):
        """动态添加功能"""
        self.features[name] = feature
        self._add_button_to_ui(name)

    def remove_feature(self, name: str):
        """移除功能"""
        if name not in self.features:
            return

        # 移除按钮
        if name in self.button_map:
            btn = self.button_map[name]
            self.button_layout.removeWidget(btn)
            btn.deleteLater()
            del self.button_map[name]

        # 移除页面
        if name in self.page_cache:
            page = self.page_cache[name]
            self.stacked.removeWidget(page)
            page.deleteLater()
            del self.page_cache[name]

        # 移除功能定义
        del self.features[name]

    def get_page(self, name: str) -> QtWidgets.QWidget | None:
        """获取指定功能的页面（如果已创建）"""
        return self.page_cache.get(name)

    def get_bridge(self, name: str) -> WebChannelBridge | None:
        """获取指定功能的 WebChannel 桥接对象

        Args:
            name: 功能名称

        Returns:
            WebChannelBridge 对象，如果不存在返回 None
        """
        return self.channel_bridges.get(name)

    def register_js_handler(
        self, feature_name: str, method_name: str, handler: Callable[..., Any]
    ):
        """为指定功能注册 JavaScript 调用处理器

        Args:
            feature_name: 功能名称
            method_name: JavaScript 中调用的方法名
            handler: Python 函数或方法
        """
        if feature_name in self.channel_bridges:
            self.channel_bridges[feature_name].register_handler(method_name, handler)
        else:
            print(f"警告：功能 '{feature_name}' 还没有 WebChannel 桥接对象")

    def call_js(
        self,
        feature_name: str,
        script: str,
        callback: Callable[[Any], None] | None = None,
    ):
        """在指定功能的页面中执行 JavaScript 代码

        Args:
            feature_name: 功能名称
            script: JavaScript 代码
        """
        page = self.get_page(feature_name)
        if isinstance(page, QWebEngineView):
            page.page().runJavaScript(script, callback)
        else:
            print(f"警告：功能 '{feature_name}' 不是网页页面")

    # 浏览器导航控制业务逻辑
    def _web_back(self):
        if isinstance(self.current_page, QWebEngineView):
            self.current_page.back()

    def _web_reload(self):
        if isinstance(self.current_page, QWebEngineView):
            self.current_page.reload()

    def _web_devtool(self):
        if isinstance(self.current_page, QWebEngineView):
            dev_view = QWebEngineView()
            self.current_page.page().setDevToolsPage(dev_view.page())
            dev_win = QtWidgets.QDialog(self)
            dev_win.setWindowTitle("开发者工具")
            dev_win.resize(1000, 600)
            l = QtWidgets.QVBoxLayout(dev_win)
            l.setContentsMargins(0, 0, 0, 0)
            l.addWidget(dev_view)
            dev_win.show()

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 清理资源
        self.page_cache.clear()
        self.button_map.clear()
        self.channel_bridges.clear()
        super().closeEvent(event)
