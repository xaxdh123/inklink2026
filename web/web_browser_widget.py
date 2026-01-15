"""
基于 BaseFeatureWindow 的浏览器组件
保留原有的浏览器功能（工具栏、地址栏、前进后退等）
"""

from typing import Dict, Optional, Union, Callable
from PySide6 import QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from web.base_feature_window import BaseFeatureWindow


class BrowserWidget(BaseFeatureWindow):
    """增强的浏览器组件，基于BaseFeatureWindow

    在BaseFeatureWindow基础上添加：
    - 工具栏（前进、后退、刷新）
    - 地址栏
    - 进度条
    """

    address = None

    def __init__(
        self,
        presets: Optional[
            Dict[str, Union[str, Callable[[], QtWidgets.QWidget]]]
        ] = None,
        parent: Optional[QtWidgets.QWidget] = None,
        profile_name: str = "default",
    ):
        """
        初始化浏览器组件

        Args:
            presets: 预设URL字典 {名称: URL}
            parent: 父窗口
            profile_name: WebEngine profile名称
        """
        # 先初始化 current_view，因为父类初始化时会调用 _switch_to_feature
        self.current_view: Optional[QWebEngineView] = None

        super().__init__(
            features=presets or {},
            profile_name=profile_name,
            parent=parent,
            window_title="InkLink Browser",
        )

        self._build_toolbar()

        # 初始化完成后，如果已经有页面，更新 current_view
        if self.stacked.count() > 0:
            current_widget = self.stacked.currentWidget()
            if isinstance(current_widget, QWebEngineView):
                self.current_view = current_widget
                self._connect_view(current_widget)
                if self.address:
                    self.address.setText(current_widget.url().toString())
                    # self.address.setEnabled(True)

    def _build_toolbar(self):
        """构建工具栏"""
        # 在按钮栏和stacked之间插入工具栏
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)

        # 前进、后退、刷新按钮
        self.back_btn = QtWidgets.QToolButton()
        self.back_btn.setText("◀")
        self.back_btn.setToolTip("后退")
        self.back_btn.clicked.connect(self._on_back)
        toolbar_layout.addWidget(self.back_btn)

        self.forward_btn = QtWidgets.QToolButton()
        self.forward_btn.setText("▶")
        self.forward_btn.setToolTip("前进")
        self.forward_btn.clicked.connect(self._on_forward)
        toolbar_layout.addWidget(self.forward_btn)

        self.reload_btn = QtWidgets.QToolButton()
        self.reload_btn.setText("⟳")
        self.reload_btn.setToolTip("刷新")
        self.reload_btn.clicked.connect(self._on_reload)
        toolbar_layout.addWidget(self.reload_btn)

        toolbar_layout.addSpacing(6)

        # 地址栏
        self.address = QtWidgets.QLineEdit()
        self.address.setPlaceholderText("输入URL并按Enter")
        self.address.returnPressed.connect(self._on_go)
        self.address.setEnabled(False)  # 初始禁用，有网页视图时启用
        toolbar_layout.addWidget(self.address, 1)

        # Go按钮
        self.go_btn = QtWidgets.QToolButton()
        self.go_btn.setText("Go")
        self.go_btn.clicked.connect(self._on_go)
        toolbar_layout.addWidget(self.go_btn)

        # 进度条
        self.progress = QtWidgets.QProgressBar()
        self.progress.setMaximumHeight(2)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        # 创建工具栏容器
        toolbar_container = QtWidgets.QFrame()
        toolbar_container.setLayout(toolbar_layout)
        toolbar_container.setStyleSheet("QFrame { background-color: #2b2b2b; }")

        # 插入到布局中（按钮栏之后，stacked之前）
        main_layout = self.layout()
        self.button_layout.addWidget(toolbar_container)
        main_layout.insertWidget(1, self.progress)

    def _on_back(self):
        """后退"""
        if self.current_view:
            self.current_view.back()
        print(self.current_view, "_on_back")

    def _on_forward(self):
        """前进"""
        if self.current_view:
            self.current_view.forward()
        print(self.current_view, "_on_forward")

    def _on_reload(self):
        """刷新"""
        if self.current_view:
            self.current_view.reload()
        print(self.current_view, "_on_reload")

    def _on_go(self):
        """跳转到地址栏的URL"""
        if not self.current_view:
            return

        text = self.address.text().strip()
        if not text:
            return

        # 自动添加协议
        if not text.startswith(("http://", "https://")):
            text = "https://" + text

        try:
            self.current_view.setUrl(QUrl(text))
        except Exception as e:
            print(f"加载URL错误：{e}")

    def _switch_to_feature(self, name: str):
        """重写切换功能，更新当前视图和地址栏"""
        super()._switch_to_feature(name)

        # 更新当前视图和地址栏
        # 使用 stacked 的当前 widget，而不是 get_page（因为可能还没缓存）
        current_widget = self.stacked.currentWidget()
        if isinstance(current_widget, QWebEngineView):
            self.current_view = current_widget
            # 连接信号（避免重复连接）
            try:
                current_widget.urlChanged.disconnect()
            except:
                pass
            try:
                current_widget.loadProgress.disconnect()
            except:
                pass
            try:
                current_widget.loadFinished.disconnect()
            except:
                pass
            self._connect_view(current_widget)
            # 更新地址栏
            if self.address:
                self.address.setText(current_widget.url().toString())
                # self.address.setEnabled(True)
        else:
            self.current_view = None
            if self.address:
                self.address.clear()
                self.address.setEnabled(False)

    def _connect_view(self, view: QWebEngineView):
        """连接视图信号"""
        view.urlChanged.connect(self._on_url_changed)
        view.loadProgress.connect(
            lambda v: self.progress.setValue(v) if self.progress else None
        )
        view.loadFinished.connect(
            lambda ok: (
                None
                if not self.progress
                else self.progress.setValue(100) if ok else self.progress.setValue(0)
            )
        )

    def _on_url_changed(self, qurl: QUrl):
        """URL改变时更新地址栏"""
        try:
            self.address.setText(qurl.toString())
        except Exception as e:
            print(f"更新URL错误：{e}")

    def current_url(self) -> str:
        """获取当前URL"""
        if self.current_view:
            return self.current_view.url().toString()
        return ""
