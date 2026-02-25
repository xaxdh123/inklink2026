"""
基于 BaseFeatureWindow 的浏览器组件
保留原有的浏览器功能（工具栏、地址栏、前进后退等）
"""

import traceback
from typing import Callable
from PySide6 import QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from web.base_feature_window import BaseFeatureWindow
import argparse


class BrowserWidget(BaseFeatureWindow):
    """增强的浏览器组件，基于BaseFeatureWindow

    在BaseFeatureWindow基础上添加：
    - 工具栏（前进、后退、刷新）
    - 地址栏
    - 进度条
    """

    def __init__(
        self,
        presets: dict[str, str | Callable[[], QtWidgets.QWidget]] | None = None,
        parent: QtWidgets.QWidget | None = None,
        profile_name: str = "default",
        token: str | None = None,
    ):
        """
        初始化浏览器组件

        Args:
            presets: 预设URL字典 {名称: URL}
            parent: 父窗口
            profile_name: WebEngine profile名称
        """
        # 先初始化 current_view，因为父类初始化时会调用 _switch_to_feature
        self.current_view: QWebEngineView | None = None
        super().__init__(
            features=presets or {},
            profile_name=profile_name,
            parent=parent,
            token=token or "",
        )

        # 初始化完成后，如果已经有页面，更新 current_view
        if self.stacked.count() > 0:
            current_widget = self.stacked.currentWidget()
            if isinstance(current_widget, QWebEngineView):
                self.current_view = current_widget
                self._connect_view(current_widget)

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
                current_widget.loadFinished.disconnect()
            except:
                pass
            self._connect_view(current_widget)

        else:
            self.current_view = None

    def _connect_view(self, view: QWebEngineView):
        """连接视图信号"""
        view.urlChanged.connect(self._on_url_changed)

    def _on_url_changed(self, qurl: QUrl):
        """URL改变时更新地址栏"""
        try:
            self.title_bar.url_bar.setText(qurl.toString())
        except Exception as e:
            print(f"更新URL错误：{e}")

    def current_url(self) -> str:
        """获取当前URL"""
        if self.current_view:
            return self.current_view.url().toString()
        return ""

    def get_sys_args(self) -> dict:
        # 1. 创建解析器对象
        parser = argparse.ArgumentParser(description=self.__class__)
        parser.add_argument("--user", dest="user_name", help="指定操作用户")
        parser.add_argument("--jump", dest="jump_page", help="指定跳转页面")
        # 3. 解析参数
        args, _ = parser.parse_known_args()
        # 4. 使用参数
        result = {
            "user_name": args.user_name or "",
            "jump_page": args.jump_page or "",
        }

        if result["user_name"]:
            print(f"当前登录用户token: {result['user_name']}")
        else:
            print("未检测到 --user 参数")

        if result["jump_page"]:
            print(f"当前跳转页面: {result['jump_page']}")
        else:
            print("未检测到 --jump 参数")

        return result
