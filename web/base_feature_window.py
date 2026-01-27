"""
基础功能窗口基类
支持顶部功能按钮栏和页面缓存（QStackedWidget）
支持网页链接（QWebEngineView）和原生QWidget
"""

from tkinter import N, NO
from typing import Callable
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from PySide6 import QtCore, QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebChannel import QWebChannel
from web.web_profile import create_persistent_profile
from web.web_channel_bridge import WebChannelBridge
from typing import Any
import os


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

    # 默认样式
    DEFAULT_STYLE = """
        QFrame#buttonBar {
            background-color: #2b2b2b;
            border-bottom: 1px solid #444;
        }
        QPushButton {
            background-color: #3d3d3d;
            color: #e0e0e0;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #0d47a1;
        }
        QPushButton:pressed {
            background-color: #0a3f91;
        }
        QPushButton:checked {
            background-color: #1565c0;
            color: #ffffff;
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

        self._build_ui()
        self._setup_features()

    def _build_ui(self):
        """构建UI界面"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部按钮栏
        self.button_bar = QtWidgets.QFrame()
        self.button_bar.setObjectName("buttonBar")
        self.button_bar.setStyleSheet(self.DEFAULT_STYLE)

        self.button_layout = QtWidgets.QHBoxLayout(self.button_bar)
        self.button_layout.setContentsMargins(4, 4, 4, 4)
        self.button_layout.setSpacing(4)

        layout.addWidget(self.button_bar)

        # 页面堆叠容器（缓存所有页面）
        self.stacked = QtWidgets.QStackedWidget()
        layout.addWidget(self.stacked, 1)

    def _setup_features(self):
        """设置功能按钮和页面"""
        if not self.features:
            return

        # 创建按钮和页面
        for name in self.features.keys():
            # 创建按钮
            btn = QtWidgets.QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=name: self._on_feature_clicked(n))

            self.button_map[name] = btn
            self.button_layout.addWidget(btn)

            # 创建页面（延迟加载，首次点击时创建）
            # 页面会在首次点击时创建并缓存

        # 添加弹性空间，使按钮靠左
        self.button_layout.addStretch()

        # 默认显示第一个功能
        if self.features:
            first_name = next(iter(self.features.keys()))
            self._switch_to_feature(first_name)

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
        if page not in self.page_cache.values():
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
        new_query = urlencode(q, doseq=True)
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
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
            from PySide6.QtWebEngineCore import QWebEnginePage

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
            view.setUrl(QUrl(url))
            return view
        except Exception as e:
            print(f"创建网页页面 '{name}' 时出错：{e}")
            import traceback

            traceback.print_exc()
            # 返回错误提示页面
            error_widget = QtWidgets.QLabel(f"无法加载页面：{e}")
            error_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            error_widget.setStyleSheet("color: #ff4444; padding: 20px;")
            return error_widget

    def add_feature(self, name: str, feature: str | Callable[[], QtWidgets.QWidget]):
        """动态添加功能"""
        self.features[name] = feature

        # 创建按钮
        btn = QtWidgets.QPushButton(name)
        btn.setCheckable(True)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked, n=name: self._on_feature_clicked(n))

        # 在最后一个stretch之前插入按钮
        self.button_map[name] = btn
        count = self.button_layout.count()
        self.button_layout.insertWidget(count - 1, btn)  # 在stretch之前插入

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

    def call_js_file(
        self,
        feature_name,
        file_path: str,
        callback: Callable[[Any], None] | None = None,
    ):
        """读取本地 JS 文件并在网页中执行

        Args:
            file_path: 本地 .js 文件的路径
            callback: 可选的回调函数
        """
        if not os.path.exists(file_path):
            print(f"错误：找不到文件 {file_path}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                script = f.read()
            self.call_js(feature_name, script, callback)
        except Exception as e:
            print(f"读取或执行 JS 文件时出错: {e}")

    def set_style(self, style: str):
        """设置自定义样式"""
        self.button_bar.setStyleSheet(style)

    def resizeEvent(self, event):
        """窗口尺寸改变时强制重新布局"""
        super().resizeEvent(event)
        layout = self.layout()
        print("resize",layout.itemAt(0))
        if layout is not None:
            layout.invalidate()
            layout.activate()
        self.updateGeometry()

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 清理资源
        self.page_cache.clear()
        self.button_map.clear()
        self.channel_bridges.clear()
        super().closeEvent(event)
