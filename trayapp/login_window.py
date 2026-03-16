# encoding=utf-8
import time
import uuid
import random
import os
import platform
from PySide6 import QtCore, QtWidgets, QtGui
from trayapp import constant

def get_mac_address():
    """
    跨平台获取 MAC 地址和硬件标识。
    """
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:].upper()
    
    # 仅在 Windows 下尝试获取主板序列号
    if platform.system() == "Windows":
        try:
            import wmi
            for board in wmi.WMI().Win32_BaseBoard():
                if board.SerialNumber:
                    mac += board.SerialNumber
                    break
        except Exception:
            pass
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
            else:
                # Mock 登录逻辑
                time.sleep(1.0)
                token = f"mock-token-{self.mac[:8]}"
                self.finished.emit(True, token)
        except Exception as e:
            self.finished.emit(False, str(e))

class LoginWindow(QtWidgets.QWidget):
    login_success = QtCore.Signal(str)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("InkLink 登录")
        self.setFixedSize(320, 240)
        self.mac = get_mac_address()
        self.worker = LoginWorker(self.mac)
        self._apply_style()
        self._build_ui()
        QtCore.QTimer.singleShot(500, self.start_login)

    def _apply_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: "Segoe UI", "Microsoft YaHei";
            }
            QPushButton {
                background-color: #3d3d3d;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 5px;
            }
        """)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        title = QtWidgets.QLabel("<b>InkLink 2026</b>")
        title.setStyleSheet("font-size: 18px; color: #0078d4;")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.status_label = QtWidgets.QLabel("正在验证设备身份...")
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setFixedHeight(10)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.retry_btn = QtWidgets.QPushButton("重试登录")
        self.retry_btn.clicked.connect(self.start_login)
        self.retry_btn.hide()
        layout.addWidget(self.retry_btn)

        mac_info = QtWidgets.QLabel(f"设备 ID: {self.mac[:12]}...")
        mac_info.setStyleSheet("color: #666666; font-size: 10px;")
        mac_info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mac_info)

    def start_login(self):
        self.status_label.setText("正在连接服务器...")
        self.progress.setRange(0, 0)
        self.retry_btn.hide()
        self.worker.finished.connect(self.on_login_result)
        self.worker.start()

    def on_login_result(self, ok: bool, payload):
        if ok:
            self.status_label.setText("登录成功，正在进入...")
            self.progress.setRange(0, 1)
            self.progress.setValue(1)
            QtCore.QTimer.singleShot(800, lambda: self.login_success.emit(payload))
        else:
            self.status_label.setText(f"登录失败: {payload}")
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self.retry_btn.show()
