from PySide6 import QtWidgets

from trayapp import constant
from typing import Callable
from web.get_module_urls import ModuleUrlsThreads
from web.web_browser_widget import BrowserWidget


class CustomerService(BrowserWidget):

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        args = self.get_sys_args()
        self.token = args.user_name or ""
        profile_name = "CustomerService"
        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {
            "报价器": constant.FLOAT_QUO_URL
        }
        super().__init__(self.presets, parent, profile_name, self.token)

        self.setWindowTitle("客服中心")
        if args.jump_page:
            self.jump(args.jump_page)
        self.work = ModuleUrlsThreads(profile_name)
        self.work.resp_name_urls.connect(self.add_more)
        self.work.start()

    def add_more(self, data):
        for k, v in data.items():
            self.add_feature(k, v)
