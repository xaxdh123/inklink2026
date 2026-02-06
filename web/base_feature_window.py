import os
import traceback
from typing import Callable, Any
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import QUrl, Signal, Qt, QPoint, QSize
from PySide6.QtGui import QIcon
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
        layout.setSpacing(8)

        # 1. 窗口控制按钮 (使用图标)
        # 映射关系: 红色->关闭, 绿色->最小化(或最大化), 黄色->全屏(或最小化)
        # 根据你提供的文件名颜色: close(红), subtract(绿), fullscreen(黄)
        # 通常 macOS 是 红(关) 黄(小) 绿(大)。
        # 这里我们优先匹配功能:
        # Close -> close-fill.png
        # Maximize -> fullscreen-fill.png
        # Minimize -> subtract-fill.png

        self.btn_close = self._create_control_button("close-fill.png", "#ff5f56")
        self.btn_min = self._create_control_button(
            "subtract-fill.png", "#ffbd2e"
        )  # 最小化通常放中间或左边
        self.btn_max = self._create_control_button("fullscreen-fill.png", "#27c93f")

        layout.addWidget(self.btn_close)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)

        layout.addSpacing(15)

        # 2. 地址栏 (集成在标题栏中间，占据最大宽度)
        self.url_bar = QtWidgets.QLineEdit()
        self.url_bar.setPlaceholderText("地址栏...")
        self.url_bar.setReadOnly(True)
        self.url_bar.setStyleSheet(
            """
            QLineEdit {
                background: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                color: #ddd;
                padding: 2px 10px;
                font-size: 11px;
                selection-background-color: #2196f3;
            }
        """
        )
        layout.addWidget(self.url_bar, 1)  # stretch=1 撑满中间

        layout.addSpacing(15)

        # 3. 标题标签 (放在右上角)
        self.title_label = QtWidgets.QLabel("")
        self.title_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.8); font-weight: bold; font-family: 'Microsoft YaHei'; font-size: 12px;"
        )
        layout.addWidget(self.title_label)

        self.btn_close.clicked.connect(self.window().close)
        self.btn_min.clicked.connect(self.window().showMinimized)
        self.btn_max.clicked.connect(self._toggle_maximize)

    def _create_control_button(self, icon_name, fallback_color):
        """创建控制按钮，优先使用图标，否则使用色块"""
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(16, 16)

        icon_path = os.path.join("resources", icon_name)
        if os.path.exists(icon_path):
            # 有图标：背景透明，显示图标
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(16, 16))
            btn.setStyleSheet(
                """
                QPushButton { border: none; background-color: transparent; }
                QPushButton:hover { background-color: rgba(255,255,255,0.15); border-radius: 4px; }
            """
            )
        else:
            # 无图标：显示圆形色块 (回退方案)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {fallback_color}; border-radius: 8px; border: none; }} QPushButton:hover {{ background-color: white; }}"
            )
        return btn

    def _toggle_maximize(self):
        # 切换最大化/还原状态，并更新图标
        win = self.window()
        if win.isMaximized():
            win.showNormal()
            self._update_max_icon("fullscreen-fill.png")
        else:
            win.showMaximized()
            self._update_max_icon("fullscreen-exit-line.png")

    def _update_max_icon(self, icon_name):
        icon_path = os.path.join("resources", icon_name)
        if os.path.exists(icon_path):
            self.btn_max.setIcon(QIcon(icon_path))

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

    # 样式表微调：显著增强选中状态
    MAIN_STYLE = """
        QWidget#mainContainer {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4a637e, stop:1 #0d47a1);
            border-radius: 12px;
        }
        QFrame#topNavArea {
            background-color: rgba(255, 255, 255, 0.05);
            border-bottom: 1px solid rgba(255, 255, 255, 0.15);
        }
        
        /* 导航按钮基础样式 */
        QPushButton.NavBtn {
            background-color: transparent;
            color: #b0bec5;
            border: none;
            padding: 0px 15px;
            font-size: 12px;
            font-weight: normal;
            border-top: 3px solid transparent; /* 预留边框位置防止抖动 */
        }
        
        /* 鼠标悬停 */
        QPushButton.NavBtn:hover {
            background-color: rgba(255, 255, 255, 0.08);
            color: white;
        }
        
        /* 选中状态 - 优化版 */
        QPushButton.NavBtn:checked {
            color: white;
            font-weight: bold;
            background-color: rgba(255, 255, 255, 0.5); /* 明显的蓝色背景 */
            border-top: 3px solid #00e5ff; /* 鲜艳的青色下划线 */
        }
        
        QStackedWidget {
            background-color: #f5f5f5; /* 稍微带点灰的白，护眼 */
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
        }
    """

    def __init__(
        self,
        features: dict[str, str | Callable[[], QtWidgets.QWidget]] | None = None,
        profile_name: str = "default",
        parent: QtWidgets.QWidget | None = None,
        token="",
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setWindowTitle(profile_name)
        self.token = token
        self.features: dict[str, str | Callable[[], QtWidgets.QWidget]] = dict(
            features or {}
        )
        self.profile_name = profile_name

        self.page_cache: dict[str, QtWidgets.QWidget] = {}
        self.button_map: dict[str, QtWidgets.QPushButton] = {}
        self.current_page: QtWidgets.QWidget | None = None
        self.channel_bridges: dict[str, WebChannelBridge] = {}
        self._drag_pos = QPoint()

        self._build_ui(profile_name)
        self._setup_features()

    def _build_ui(self, title):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)

        self.container = QtWidgets.QFrame()
        self.container.setObjectName("mainContainer")
        self.container.setStyleSheet(self.MAIN_STYLE)
        self.main_layout.addWidget(self.container)

        layout = QtWidgets.QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. 标题栏
        self.title_bar = CustomTitleBar(self)
        self.title_bar.title_label.setText(title)
        layout.addWidget(self.title_bar)

        # 2. 导航栏 (高度压缩)
        self.top_nav = QtWidgets.QFrame()
        self.top_nav.setObjectName("topNavArea")
        self.top_nav.setFixedHeight(32)
        nav_layout = QtWidgets.QHBoxLayout(self.top_nav)
        nav_layout.setContentsMargins(8, 0, 8, 0)
        nav_layout.setSpacing(5)

        # 工具按钮 (使用图标)
        self.btn_back = self._create_tool_btn(
            "arrow-left-line.png", "后退", self._web_back
        )
        self.btn_reload = self._create_tool_btn(
            "refresh-line.png", "刷新", self._web_reload
        )
        self.btn_dev = self._create_tool_btn(
            "bug-line.png", "调试工具", self._web_devtool
        )

        nav_layout.addWidget(self.btn_back)
        nav_layout.addWidget(self.btn_reload)

        # 分隔线
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setStyleSheet(
            "background-color: rgba(255,255,255,0.15); width: 1px; margin: 4px 4px;"
        )
        nav_layout.addWidget(line)

        # 功能按钮布局
        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_layout.setSpacing(0)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.addLayout(self.button_layout)
        nav_layout.addWidget(line)
        nav_layout.addWidget(self.btn_dev)
        layout.addWidget(self.top_nav)

        # 3. 页面区
        self.stacked = QtWidgets.QStackedWidget()
        layout.addWidget(self.stacked, 1)

    def _create_tool_btn(self, icon_name, tip, callback):
        """创建工具栏按钮，优先加载 resources 下的图标"""
        btn = QtWidgets.QPushButton()
        btn.setToolTip(tip)
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.PointingHandCursor)

        # 尝试加载图标
        icon_path = os.path.join("resources", icon_name)
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(20, 20))
            # 纯图标样式
            btn.setStyleSheet(
                """
                QPushButton { background-color: transparent; border: none; border-radius: 4px; }
                QPushButton:hover { background-color: rgba(255,255,255,0.15); }
                QPushButton:pressed { background-color: rgba(255,255,255,0.25); }
            """
            )
        else:
            # 回退到文字
            fallback_map = {
                "arrow-left-line.png": "←",
                "refresh-line.png": "⟳",
                "bug-line.png": "🛠",
            }
            btn.setText(fallback_map.get(icon_name, "?"))
            btn.setStyleSheet(
                """
                QPushButton { background-color: transparent; color: white; border-radius: 4px; font-weight: bold; font-size: 14px; }
                QPushButton:hover { background-color: rgba(255,255,255,0.15); }
            """
            )

        btn.clicked.connect(callback)
        return btn

    def _setup_features(self):
        if not self.features:
            return
        for name in list(self.features.keys()):
            self._add_button_to_ui(name)
        if self.features:
            self._switch_to_feature(next(iter(self.features.keys())))

    def _add_button_to_ui(self, name):
        btn = QtWidgets.QPushButton(name)
        btn.setProperty("class", "NavBtn")
        btn.setCheckable(True)
        btn.setFixedHeight(32)  # 与 top_nav 高度对齐
        btn.setCursor(Qt.PointingHandCursor)
        # 设置 Expanding 使其横向撑满
        btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        btn.clicked.connect(lambda checked, n=name: self._on_feature_clicked(n))
        self.button_map[name] = btn
        self.button_layout.addWidget(btn)

    # --- 以下保留原有所有业务逻辑函数 ---
    def _on_feature_clicked(self, name: str):
        self._switch_to_feature(name)

    def _switch_to_feature(self, name: str):
        if name not in self.features:
            return
        for btn_name, btn in self.button_map.items():
            btn.setChecked(btn_name == name)
        page = self._get_or_create_page(name)
        if not page:
            return
        if page not in [self.stacked.widget(i) for i in range(self.stacked.count())]:
            self.stacked.addWidget(page)
        self.stacked.setCurrentWidget(page)
        self.current_page = page
        # 更新标题栏地址显示
        if isinstance(page, QWebEngineView):
            self.title_bar.url_bar.setText(page.url().toString())
        else:
            self.title_bar.url_bar.setText("Native Widget")

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
        if name in self.page_cache:
            return self.page_cache[name]
        feature = self.features[name]
        if isinstance(feature, str):
            page = self._create_web_page(name, feature)
        elif callable(feature):
            try:
                page = feature()
            except Exception as e:
                print(f"Error: {e}")
                return None
        else:
            return None

        if page:
            self.page_cache[name] = page
            self.stacked.addWidget(page)
            self.create_page_signal.emit(name)
        return page

    def _create_web_page(self, name: str, url: str) -> QtWidgets.QWidget:
        try:
            profile = create_persistent_profile(f"{self.profile_name}_{name}")
            view = QWebEngineView()
            page = QWebEnginePage(profile, view)
            view.setPage(page)
            channel = QWebChannel(self)
            bridge = WebChannelBridge(self)
            bridge.web_view = view
            channel.registerObject("pyBridge", bridge)
            self.channel_bridges[name] = bridge
            page.setWebChannel(channel)
            view.setUrl(QUrl(self._ensure_token_param(url)))
            # 监听地址变化更新地址栏
            view.urlChanged.connect(
                lambda qurl: self.title_bar.url_bar.setText(qurl.toString())
            )
            return view
        except Exception as e:
            traceback.print_exc()
            return QtWidgets.QLabel(f"Error: {e}")

    def add_feature(self, name, feature):
        self.features[name] = feature
        self._add_button_to_ui(name)

    def remove_feature(self, name):
        if name not in self.features:
            return
        if name in self.button_map:
            self.button_layout.removeWidget(self.button_map[name])
            self.button_map[name].deleteLater()
            del self.button_map[name]
        if name in self.page_cache:
            self.stacked.removeWidget(self.page_cache[name])
            self.page_cache[name].deleteLater()
            del self.page_cache[name]
        del self.features[name]

    def get_page(self, name):
        return self.page_cache.get(name)

    def get_bridge(self, name):
        return self.channel_bridges.get(name)

    def register_js_handler(self, feature_name, method_name, handler):
        if feature_name in self.channel_bridges:
            self.channel_bridges[feature_name].register_handler(method_name, handler)

    def call_js(self, feature_name, script, callback=None):
        page = self.get_page(feature_name)
        if isinstance(page, QWebEngineView):
            page.page().runJavaScript(script, callback)

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
            dev_win.resize(1000, 600)
            layout = QtWidgets.QVBoxLayout(dev_win)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(dev_view)
            dev_win.show()

    def closeEvent(self, event):
        self.page_cache.clear()
        self.button_map.clear()
        self.channel_bridges.clear()
        super().closeEvent(event)
