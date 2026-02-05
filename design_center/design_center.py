from PySide6 import QtWidgets
from PySide6 import QtCore
from web.web_browser_widget import BrowserWidget

from trayapp import constant
from typing import Callable


class DC(BrowserWidget):
    def __init__(self, token, parent: QtWidgets.QWidget | None = None):
        self.token = token or ""
        profile_name = "design_center"
        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {
            "设计中心": constant.DESIGN_CENTER_URL
        }
        super().__init__(self.presets, parent, profile_name, self.token)

        self.setWindowTitle("浮窗插件")
        self.last_request_time = 0
        self.register_js_handler("设计中心", "openDesignFile", self.openDesignFile)

    def openDesignFile(self, data):
        print(data)
