from PySide6 import QtWidgets
from web.get_module_urls import ModuleUrlsThreads
from web.web_browser_widget import BrowserWidget

from typing import Callable


class LayoutCenter(BrowserWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        args = self.get_sys_args()
        self.token = args.user_name or ""
        profile_name = "LayoutCenter"
        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {}
        super().__init__(self.presets, parent, profile_name, self.token)
        self.setWindowTitle("排版中心")
        if args.jump_page:
            self.jump(args.jump_page)
        self.work = ModuleUrlsThreads(profile_name)
        self.work.resp_name_urls.connect(self.add_more)
        self.work.start()

    def openDesignFile(self, data):
        print(data)

    def add_more(self, data):
        for k, v in data.items():
            self.add_feature(k, v)
