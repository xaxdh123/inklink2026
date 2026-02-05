from operator import is_
from PySide6 import QtCore, QtWidgets
from pathlib import Path
from system_setting.UpdateCheckWorker import UpdateCheckWorker
from trayapp.launcher_utils import launch_process
from trayapp import constant
from utils import GLOB_CONFIG


class FloatingWindow(QtWidgets.QWidget):
    visibilityChanged = QtCore.Signal(bool)
    global_style = """
            QFrame#frame {
                background-color: #2b2b2b;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: 1px solid #4d4d4d;
                border-radius: 3px;
                padding: 0px 6px;
                height: 22px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0d47a1;
                border: 1px solid #1565c0;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #1565c0;
                border: 1px solid #1976d2;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 11px;
            }
            QLabel#titleLabel {
                font-weight: 800;
                color: #64b5f6;
                font-size: 12px;
            }
            QLabel#msgLabel {
                font-weight: 400;
                color: #aaaaaa;
                font-size: 10px;
            }
            QLabel#versionLabel {
                font-weight: 400;
                color: #666666;
                font-size: 8px;
            }
        """

    def __init__(self, token: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("悬浮面板")
        self.token = token
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(160, 160)
        self._drag_pos = None  # 用于窗口拖拽
        self._build_ui()
        self.check_update()

    def check_update(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        self.worker = UpdateCheckWorker(GLOB_CONFIG, auto_download=True)
        self.worker.status_changed.connect(self.on_worker_status_changed)
        self.worker.start()

    def on_worker_status_changed(self, key: str, status_text: str, is_ready: bool):
        self._msg_label.setText(key + ": " + status_text)
        self._msg_label.setStyleSheet("color: #909399; font-size: 9px;background:none;")
        if is_ready:
            self._msg_label.setStyleSheet(
                "color: #67c23a; font-weight: bold; font-size: 9px;background:none;"
            )
            self._msg_label.clicked.connect(
                lambda: self.on_feature(constant.COMPONENT_MAP[-1])
            )

    def _build_ui(self):
        frame = QtWidgets.QFrame(self)
        frame.setObjectName("frame")
        # Modern dark theme compatible stylesheet
        frame.setStyleSheet(self.global_style)
        v = QtWidgets.QVBoxLayout(frame)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(0)
        head_layout = QtWidgets.QHBoxLayout()
        _head_1 = QtWidgets.QVBoxLayout(frame)

        self._title_label = QtWidgets.QLabel("工具面板")
        self._title_label.setObjectName("titleLabel")
        # enable dragging by title label: install event filter to forward mouse events
        self._title_label.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
        self._title_label.installEventFilter(self)
        _head_1.addWidget(
            self._title_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self._msg_label = QtWidgets.QPushButton("点击查看消息")
        self._msg_label.setObjectName("msgLabel")
        self._msg_label.setFixedHeight(16)
        _head_1.addWidget(
            self._msg_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )
        head_layout.addLayout(_head_1, 1)
        _setting = QtWidgets.QPushButton("🛠")
        _setting.clicked.connect(lambda: self.on_feature(constant.COMPONENT_MAP[-1]))
        head_layout.addWidget(_setting, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
        v.addLayout(head_layout)
        v.addStretch()
        vg = QtWidgets.QGridLayout()
        vg.setSpacing(3)
        show_items = [x for x in constant.COMPONENT_MAP if "float" in x["show_type"]]
        for i, item in enumerate(show_items):
            b = QtWidgets.QPushButton(item["name"])
            # 修复lambda闭包问题：需要捕获exe的值，而不是引用
            b.clicked.connect(lambda checked, _i=item: self.on_feature(_i))
            vg.addWidget(b, i % 3, i // 3)
        v.addLayout(vg)
        self._version_label = QtWidgets.QLabel("inklink-v1.0.0")
        self._version_label.setObjectName("versionLabel")
        v.addStretch()
        v.addWidget(self._version_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

    def on_feature(self, item):

        app_dir = Path(__file__).parent.parent
        exe_path = app_dir / constant.DIR_BIN / item["sub_dir"] / item["exe"]

        # 检查文件是否存在
        if not exe_path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "文件未找到",
                f"未找到对应的exe文件：\n{exe_path}\n\n"
                f"请确保已打包对应的功能模块。",
            )
            return

        # 启动exe（写入token到配置文件并启动）
        try:
            launch_process(str(exe_path), ["--user", self.token], detach=True)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(
                self, "启动失败", f"无法找到exe文件：\n{exe_path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "启动失败", f"无法启动 '{item['name']}'：\n{str(e)}"
            )

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.visibilityChanged.emit(True)
        except Exception:
            pass

    def hideEvent(self, event):
        super().hideEvent(event)
        try:
            self.visibilityChanged.emit(False)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        # allow dragging the window when interacting with the title label
        try:
            if obj is getattr(self, "_title_label", None):
                t = event.type()
                # Mouse button press
                if t == QtCore.QEvent.Type.MouseButtonPress:
                    if event.button() == QtCore.Qt.MouseButton.LeftButton:
                        # replicate mousePressEvent logic using globalPosition
                        self._drag_pos = (
                            event.globalPosition().toPoint()
                            - self.frameGeometry().topLeft()
                        )
                        event.accept()
                        return True
                # Mouse move
                if t == QtCore.QEvent.Type.MouseMove:
                    if (
                        self._drag_pos is not None
                        and event.buttons() & QtCore.Qt.MouseButton.LeftButton
                    ):
                        self.move(event.globalPosition().toPoint() - self._drag_pos)
                        event.accept()
                        return True
                # Mouse release
                if t == QtCore.QEvent.Type.MouseButtonRelease:
                    if event.button() == QtCore.Qt.MouseButton.LeftButton:
                        self._drag_pos = None
                        event.accept()
                        return True
        except Exception:
            pass
        return super().eventFilter(obj, event)
