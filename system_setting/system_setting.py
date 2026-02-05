from typing import Callable
from PySide6 import QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from trayapp import constant
from web.web_browser_widget import BrowserWidget
from system_setting.version_info import VersionInfo


class Setting(BrowserWidget):

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        args = self.get_sys_args()
        self.token = args.user_name or ""
        profile_name = "system_setting"

        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {
            "个人中心": constant.SETTING_USER_URL,
            "消息中心": constant.SETTING_MSG_URL,
            "版本信息": lambda: VersionInfo(),
        }
        super().__init__(self.presets, parent, profile_name, self.token)
        self.scroll_message()
        if args.jump_page:
            self.jump(args.jump_page)

    def scroll_message(self):
        def create_listen(name):
            if name == "消息中心":
                page = self.get_page("消息中心")
                if isinstance(page, QWebEngineView):
                    page.loadFinished.connect(
                        lambda: page.page().runJavaScript("alert(111)")
                    )

        self.create_page_signal.connect(create_listen)

    def jump(self, name):
        self._switch_to_feature(name)
