# encoding=utf-8
import wmi
import time
import uuid
import random
from PySide6 import QtCore, QtWidgets, QtGui

from trayapp import constant


def get_mac_address():

    mac = uuid.UUID(int=uuid.getnode()).hex[-12:].upper()
    for board in wmi.WMI().Win32_BaseBoard():
        if board.SerialNumber:
            mac += board.SerialNumber
            break
    return str(mac)


class LoginWorker(QtCore.QThread):
    finished = QtCore.Signal(bool, object)

    def __init__(self, mac: str, parent=None):
        super().__init__(parent)
        self.mac = mac

    def run(self):
        time.sleep(0.3)
        try:
            if constant.API_LOGIN_URL:

                import requests

                resp = requests.get(
                    constant.API_LOGIN_URL, params={"mac": self.mac}, timeout=6
                )
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("token")
                    if token:
                        self.finished.emit(True, token)
                        return
                self.finished.emit(False, resp.text)
                return
            else:
                time.sleep(1.5)
                if random.random() > 0.4:
                    token = f"mock-token-{self.mac.replace(':','')[:8]}"
                    self.finished.emit(True, token)
                else:
                    self.finished.emit(False, "mock login failed")
        except Exception as e:
            self.finished.emit(False, str(e))


class ResourceLoader(QtCore.QThread):
    finished = QtCore.Signal()

    def run(self):
        time.sleep(4)
        self.finished.emit()


class LoginWindow(QtWidgets.QWidget):
    login_success = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("登录")
        self.setFixedSize(240, 160)
        self.mac = get_mac_address()
        self.worker = LoginWorker(self.mac)
        self._build_ui()

        # Start resource loader in background (non-blocking)
        self.loader = ResourceLoader()
        self.loader.start()

        # Start login automatically
        QtCore.QTimer.singleShot(50, self.start_login)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("<b>欢迎，正在登录中…</b>")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.status_label = QtWidgets.QLabel("准备登录")
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        h = QtWidgets.QHBoxLayout()
        self.copy_btn = QtWidgets.QPushButton("复制 MAC")
        self.copy_btn.clicked.connect(self.copy_mac)
        self.copy_btn.setEnabled(False)
        h.addWidget(self.copy_btn)

        self.retry_btn = QtWidgets.QPushButton("重试")
        self.retry_btn.clicked.connect(self.start_login)
        self.retry_btn.setEnabled(False)
        h.addWidget(self.retry_btn)

        layout.addLayout(h)

        mac_label = QtWidgets.QLabel(f"MAC: {self.mac}")
        mac_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mac_label)

    def start_login(self):
        self.status_label.setText("登录中…")
        self.progress.setRange(0, 0)
        self.copy_btn.setEnabled(False)
        self.retry_btn.setEnabled(False)

        self.worker.finished.connect(self.on_login_result)
        self.worker.start()

    def on_login_result(self, ok: bool, payload):
        if ok:
            token = payload
            self.status_label.setText("登录成功")
            self.progress.setRange(0, 1)
            QtCore.QTimer.singleShot(300, lambda: self.login_success.emit(token))
        else:
            err = payload
            self.status_label.setText(f"登录失败：{err}")
            self.progress.setRange(0, 1)
            self.copy_btn.setEnabled(True)
            self.retry_btn.setEnabled(True)

    def copy_mac(self):
        QtGui.QGuiApplication.clipboard().setText(self.mac)
        QtWidgets.QToolTip.showText(self.mapToGlobal(self.copy_btn.pos()), "已复制 MAC")
