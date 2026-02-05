from PySide6 import QtWidgets
from web.get_module_urls import ModuleUrlsThreads
from web.web_browser_widget import BrowserWidget
from trayapp import constant
from typing import Callable


class DesignCenter(BrowserWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        args = self.get_sys_args()
        self.token = args.get("user_name", None) or ""
        profile_name = "DesignCenter"
        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {
            "设计中心": constant.DESIGN_CENTER_URL
        }
        super().__init__(self.presets, parent, profile_name, self.token)
        self.register_js_handler("设计中心", "openDesignFile", self.openDesignFile)
        self.setWindowTitle("设计中心")
        if "jump_page" in args:
            self._switch_to_feature(args["jump_page"])
        self.work = ModuleUrlsThreads(profile_name)
        self.work.resp_name_urls.connect(self.add_more)
        self.work.start()

    def openDesignFile(self, data):
        print(data)

    def add_more(self, data):
        for k, v in data.items():
            self.add_feature(k, v)
