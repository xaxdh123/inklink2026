# encoding: utf-8
import datetime

from PySide6.QtCore import QMargins, QThread, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QTextBrowser,
    QGridLayout,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QLabel,
    QMessageBox,
)

from comb import GLOB_CONFIG

from comb.AutoThread import AutoThread
from comb.MainWorker import MainWorker


class OneComb(QWidget):

    def init_view(self):
        labelStyle = {
            "fixedHeight": 30,
            "fixedWidth": 50,
            "styleSheet": "background-color: #88FFFFFF;padding: 0 4px;font-size:12px",
        }
        lineEditStyle = labelStyle.copy()
        lineEditStyle["fixedWidth"] = 200
        btnStyle = labelStyle.copy()
        btnStyle["styleSheet"] = "opacity:0.8;padding: 0 4px;font-size:12px"

        parent = QGridLayout(contentsMargins=QMargins(0, 0, 0, 0), spacing=0)
        srcPath = QLineEdit(text=GLOB_CONFIG.value("ui/src_path"), **lineEditStyle)
        srcPath.editingFinished.connect(
            lambda: GLOB_CONFIG.setValue("ui/src_path", srcPath.text())
        )
        srcSel = QPushButton(text="原始", **btnStyle)
        srcSel.clicked.connect(lambda: self.select_file(srcPath))
        srcMvPath = QLineEdit(text=GLOB_CONFIG.value("ui/src_mv_path"), **lineEditStyle)
        srcMvPath.editingFinished.connect(
            lambda: GLOB_CONFIG.setValue("ui/src_mv_path", srcMvPath.text())
        )
        srcMvSel = QPushButton(text="备份", **btnStyle)
        srcMvSel.clicked.connect(lambda: self.select_file(srcMvPath))
        self.startB = QPushButton(text="开始", fixedHeight=60)
        self.startB.clicked.connect(self.start)
        self.startB2 = QPushButton(text="监听", fixedHeight=30)
        self.startB2.clicked.connect(self.listen)
        parent.addWidget(srcSel, 0, 0, 1, 1)
        parent.addWidget(srcPath, 0, 1, 1, 4)
        parent.addWidget(srcMvSel, 0, 5, 1, 1)
        parent.addWidget(srcMvPath, 0, 6, 1, 4)
        parent.addWidget(self.startB, 0, 10, 2, 1)
        parent.addWidget(self.startB2, 2, 10, 1, 1)

        desPath = QLineEdit(text=GLOB_CONFIG.value("ui/dest_path"), **lineEditStyle)
        desPath.editingFinished.connect(
            lambda: GLOB_CONFIG.setValue("ui/dest_path", desPath.text())
        )
        desSel = QPushButton(text="印刷", **btnStyle)
        desSel.clicked.connect(lambda: self.select_file(desPath))
        desDaoPath = QLineEdit(
            text=GLOB_CONFIG.value("ui/dest_dao_path"), **lineEditStyle
        )
        desDaoPath.editingFinished.connect(
            lambda: GLOB_CONFIG.setValue("ui/dest_dao_path", desDaoPath.text())
        )
        desDaoSel = QPushButton(text="自割", **btnStyle)
        desDaoSel.clicked.connect(lambda: self.select_file(desDaoPath))
        parent.addWidget(desSel, 1, 0, 1, 1)
        parent.addWidget(desPath, 1, 1, 1, 4)
        parent.addWidget(desDaoSel, 1, 5, 1, 1)
        parent.addWidget(desDaoPath, 1, 6, 1, 4)

        des2Path = QLineEdit(text=GLOB_CONFIG.value("ui/dest_2_path"), **lineEditStyle)
        des2Path.editingFinished.connect(
            lambda: GLOB_CONFIG.setValue("ui/dest_2_path", des2Path.text())
        )
        des2Sel = QPushButton(text="刀线", **btnStyle)
        des2Sel.clicked.connect(lambda: self.select_file(des2Path))
        spaceItem = QLineEdit(text=GLOB_CONFIG.value("ui/over_time"), **labelStyle)
        spaceItem.editingFinished.connect(
            lambda: GLOB_CONFIG.setValue("ui/over_time", spaceItem.text())
        )
        self.typeset = QLabel(text=f"当前大版号为:--------------", **lineEditStyle)
        parent.addWidget(des2Sel, 2, 0, 1, 1)
        parent.addWidget(des2Path, 2, 1, 1, 4)
        parent.addWidget(spaceItem, 2, 5, 1, 1)
        parent.addWidget(self.typeset, 2, 6, 1, 4)

        self.browser = QTextBrowser(
            styleSheet="background-color: #99FFFFFF;margin-top:2px"
        )
        parent.addWidget(self.browser, 3, 0, 1, 11)
        parent.setRowStretch(3, 1)
        parent.setColumnStretch(10, 1)
        self.setLayout(parent)
        self.st_list = [srcPath, srcMvPath, desPath, desDaoPath, des2Path, spaceItem]

    def __init__(self):
        super(OneComb, self).__init__()
        self.init_view()
        self._faker = QThread(self)
        # worker 对象
        # 关键：移动到子线程
        self.worker = MainWorker()
        self.worker.moveToThread(self._faker)
        self._faker.started.connect(self.worker.start)
        self._faker.finished.connect(self._faker.deleteLater)

        self.worker.message_signal.connect(self.signal_work)
        self.autoThread = AutoThread(self.worker, self.signal_work)

    def select_file(self, key):
        filePath = QFileDialog.getExistingDirectory(self, "选择路径")
        key.setText(filePath)

    def signal_work(self, obj):
        print(obj)
        if "done" in obj and obj["done"]:
            self.startB.setText("开始")
            [w.setDisabled(False) for w in self.st_list]
        if "auto_done" in obj and obj["auto_done"]:
            self.startB2.setText("监听")
        if "next" in obj and obj["next"]:
            self.worker._do_next = True
        if "msg" in obj and obj["msg"]:
            self.append(obj["msg"])
        if "typeset" in obj and obj["typeset"]:
            self.typeset.setText(f"当前大版号为:{obj['typeset']}")
        if "action" in obj and obj["action"] == "RETRY_UPLOAD":
            # 弹出提示框
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("上传系统失败")
            msg_box.setText(obj.get("msg", "上传系统失败，是否重试？"))
            retry_btn = msg_box.addButton("重试一次", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton("忽略(手动处理)", QMessageBox.ButtonRole.RejectRole)

            # 这里使用非阻塞方式执行，或者直接 exec()
            # 因为信号是在主线程执行的，弹窗不会影响 Worker 线程继续跑下一张单子
            msg_box.exec()
            if msg_box.clickedButton() == retry_btn:
                QTimer.singleShot(
                    0, lambda: self.worker.upload_to_system(obj["payload"])
                )

    def append(self, text):
        self.browser.moveCursor(QTextCursor.MoveOperation.End)
        self.browser.append(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ":\t" + text
        )

    def start(self):
        # 启动/停止逻辑：
        # - 点击“开始”时：如果线程未运行则启动线程；如果线程已运行则唤醒 worker 继续处理。
        # - 点击“停止”时：请求 worker 停止并优雅退出线程，恢复 UI 状态。
        if self.startB.text() == "开始":
            self.startB.setText("停止")
            [w.setDisabled(True) for w in self.st_list]
            # 若线程尚未运行则启动线程，否则直接允许 worker 继续下一轮
            if not self._faker.isRunning():
                self._faker.start()
            else:
                self.worker._do_next = True
            # 同时触发监听按钮（以便自动开始监听行为保持一致）
            if self.startB2.text() == "监听":
                self.autoThread.start()
                self.startB2.setText("停止")
        else:
            # 请求 worker 停止其循环
            self.worker.stop()

    def listen(self):
        if self.startB2.text() == "监听":
            self.autoThread.start()
            self.startB2.setText("停止")
        else:
            self.autoThread.stop()
