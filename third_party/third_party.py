from typing import Callable
from PySide6 import QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from trayapp import constant
from web.QNetworkHttpClient import QNetworkHttpClient
from web.web_browser_widget import BrowserWidget
from system_setting.version_info import VersionInfo


class ThirdParty(BrowserWidget):

    def __init__(self, token, parent: QtWidgets.QWidget | None = None):
        self.token = token or ""
        profile_name = "system_setting"

        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {
            "个人中心": constant.SETTING_USER_URL
        }
        super().__init__(self.presets, parent, profile_name, token)
        http = QNetworkHttpClient(self.token, self)
        http.get_json(constant.THIRD_PARTY_URL, done=self.add_from_url, num=23)

    def add_from_url(self, ok, data, num):
        if not ok:
            QtWidgets.QErrorMessage().showMessage(data)
            return
        for item in data["data"]:
            name = item["globalKey"]
            url = item["globalValue"]
            self.add_feature(name, url)

    def jump(self, name):
        self._switch_to_feature(name)
