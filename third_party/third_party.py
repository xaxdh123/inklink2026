from typing import Callable
from PySide6 import QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from trayapp import constant
from web.QNetworkHttpClient import QNetworkHttpClient
from web.get_module_urls import ModuleUrlsThreads
from web.web_browser_widget import BrowserWidget
from system_setting.version_info import VersionInfo


class ThirdParty(BrowserWidget):

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        args = self.get_sys_args()
        self.token = args.get("user_name", None) or ""
        profile_name = "ThirdParty"
        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {
            "盛大报价": "https://www.sd2000.com/Login"
        }
        super().__init__(self.presets, parent, profile_name, self.token)
        self.setWindowTitle("三方工具")
        if "jump_page" in args:
            self._switch_to_feature(args["jump_page"])
        self.work = ModuleUrlsThreads(profile_name)
        self.work.resp_name_urls.connect(self.add_feature)
        self.work.resp_resize.connect(self.resize)
        self.work.start()
