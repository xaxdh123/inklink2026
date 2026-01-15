from PySide6 import QtWidgets
from trayapp import constant
from web.web_browser_widget import BrowserWidget
from typing import Optional
from system_setting.version_info import VersionInfo


class Setting(BrowserWidget):

    def __init__(
        self,
        token,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        self.token = token or ""
        profile_name = "system_setting"

        self.presets = {
            "个人中心": f"{constant.SETTING_USER_URL}?no_layout=1&token=${self.token}",
            "消息中心": f"{constant.SETTING_MSG_URL}?no_layout=1&token=${self.token}",
            "版本信息": lambda: VersionInfo(),
        }
        super().__init__(
            self.presets,
            parent,
            profile_name,
        )
        self.scroll_message()

    def scroll_message(self):
        def create_listen(name):
            if name == "消息中心":
                page = self.get_page("消息中心")
                page.loadFinished.connect(
                    lambda: page.page().runJavaScript("alert(111)")
                )

        self.create_page_signal.connect(create_listen)

    def jump(self, name):
        self._switch_to_feature(name)
