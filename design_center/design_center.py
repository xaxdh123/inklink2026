from PySide6 import QtWidgets
from PySide6.QtCore import Signal
from PySide6.QtGui import Qt
from design_center.design_util import DesignUtil
from web.get_module_urls import ModuleUrlsThreads
from web.web_browser_widget import BrowserWidget
from trayapp import constant
from typing import Callable


class DesignCenter(BrowserWidget, DesignUtil):
    signal_msg = Signal(dict)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        args = self.get_sys_args()
        self.token = args.get("user_name", None) or ""
        profile_name = "DesignCenter"
        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {
            "设计中心": constant.DESIGN_CENTER_URL
        }
        super().__init__(self.presets, parent, profile_name, self.token)
        self.handle_register()
        if "jump_page" in args:
            self._switch_to_feature(args["jump_page"])
        self.work = ModuleUrlsThreads(profile_name)
        self.work.resp_name_urls.connect(self.add_feature)
        self.work.resp_resize.connect(self.resize)
        self.work.start()
        self.signal_msg.connect(self.handle_msg)

    def handle_msg(self, data):
        print("handle_msg", data)
        if "msg" in data:
            QtWidgets.QMessageBox.warning(self, "提示", data["msg"])
        if "runJS" in data:
            self.call_js("设计中心", data["runJS"], callback=print)

    def handle_register(self):
        register_list = [
            "openDesignFile",
            "jumpToDesignFile",
            "startDesign",
            "confirmFirstDraft",
            "confirmFinalDraft",
        ]
        register_dict = {
            name: lambda x, fn=getattr(self, name): fn(x, self.signal_msg)
            for name in register_list
        }
        for k, v in register_dict.items():
            self.register_js_handler("设计中心", k, v)
