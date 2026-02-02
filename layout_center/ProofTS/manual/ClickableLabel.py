# encoding: utf-8
import base64
import os
import traceback

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QLabel,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QCheckBox,
    QLineEdit,
)


class ClickableLabel(QLabel):
    """
    支持文字选中／复制，并在鼠标释放时发出 clicked 信号。
    """

    clicked = Signal()

    def __init__(self, parent=None, text=""):
        super().__init__(parent)
        self.setText(text)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class ImageTextCheckBox(QWidget):
    """
    带网络图片的复选框：
      • 保留原生勾选框指示器
      • 文本前显示一张网络图片
      • 点击图片/文字区也会切换状态
      • 信号：toggled(bool)
    """

    toggled = Signal(bool)

    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.record = record
        self.setFixedHeight(60)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self._cb = QCheckBox(self)
        h.addWidget(self._cb, 0, Qt.AlignmentFlag.AlignVCenter)
        self._lbl = ClickableLabel('<img src="" width=40 height=30/>')
        h.addWidget(self._lbl)
        v = QVBoxLayout()
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        h.addLayout(v)
        try:
            self.designFileName = self.record["designList"][0]["designFsPath"]
            self.designFileName = os.path.basename(self.designFileName)
        except:
            self.designFileName = (
                self.record["flowStoreName"]
                + "-"
                + self.record["productMain"]["flowProductName"]
                + "-"
                + self.record["productMain"]["productRealNum"]
                + "-"
                + self.record["productMain"]["productSimpleMaterial"].split(":")[-1]
                + "-"
                + self.record["productMain"]["productSimpleCraft"]
                + "-"
                + self.record["productMain"]["productSimpleInfo"]
            )

        name = QLineEdit(self, text=self.designFileName, readOnly=True)
        name.setCursorPosition(0)
        v.addWidget(name, 1, Qt.AlignmentFlag.AlignVCenter)
        h2 = QHBoxLayout()
        h2.setContentsMargins(0, 0, 0, 0)
        h2.setSpacing(0)

        h2.addWidget(
            QLabel(self.record["systemOrderNo"], styleSheet="color:#999999;font-size:10px", fixedWidth=120),  # type: ignore
            Qt.AlignmentFlag.AlignVCenter,
        )
        try:
            designNo = self.record["designList"][0]["designCode"]
        except:
            designNo = self.record["flowProduceNo"]
        h2.addWidget(
            QLabel(designNo, styleSheet="color:#999999;font-size:10px", fixedWidth=100),  # type: ignore
            Qt.AlignmentFlag.AlignVCenter,
        )

        h2.addWidget(
            QLabel(
                self.record["orderExtra"]["markName"],
                styleSheet="color:#999999;font-size:10px",
                fixedWidth=120,
            ),  # type: ignore
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        h2.addWidget(
            QLabel(
                self.record["flowTbName"],
                styleSheet="color:#999999;font-size:10px",
            ),  # type: ignore
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        remark = self.record.get("productMain").get("flowProductRemark", "") or ""
        remark = (
            remark.replace("：", ":")
            .replace("客服备注:", "")
            .replace("\n买家留言:", "")
            .replace("\n本地备注:", "")
        )
        eRemark = QLineEdit(
            self, text=remark, readOnly=True, styleSheet="border:none;background:rgba(0,0,0,0);font-size:10px"  # type: ignore
        )
        eRemark.setCursorPosition(0)
        h2.addWidget(eRemark, 1, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(h2)
        # 3. 点击文字/图片时切换复选框
        self._lbl.clicked.connect(lambda: self._cb.toggle())
        self._cb.toggled.connect(self.toggled.emit)

        try:
            # 4. 异步下载网络图
            thumb_url = self.record["designList"][0]["designImage"]
            self._nam = QNetworkAccessManager(self)
            self._nam.finished.connect(self._on_image_fetched)
            self._nam.get(QNetworkRequest(QUrl(f"{thumb_url}?w=40")))
        except:
            traceback.print_exc()

    def _on_image_fetched(self, reply: QNetworkReply):
        if reply.error() and reply.error() != QNetworkReply.NetworkError.NoError:
            return
        data = reply.readAll()
        pix = QPixmap()
        pix.loadFromData(data)

        b64 = base64.b64encode(data).decode()  # type: ignore
        html = f'<img src="data:image/png;base64,{b64}" width=40 height=30 align="middle"/>'
        self._lbl.setText(html)

    # 暴露部分 QCheckBox 接口
    def isChecked(self):
        return self._cb.isChecked()

    def setChecked(self, c: bool):
        self._cb.setChecked(c)

    def text(self):
        return self.designFileName
