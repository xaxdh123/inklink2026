# encoding: utf-8
import datetime
import glob
import json
import os
import re
import time
import traceback

from PySide6.QtCore import QSettings, QMargins, QStringListModel, QByteArray, QEvent, Qt
from PySide6.QtGui import QTextCursor, QIntValidator
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QListView,
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QGridLayout,
    QMessageBox,
)

from manual.ClickableLabel import ImageTextCheckBox
from manual.MainWorker import ApplicationManager
from utils import GLOB_CONFIG, GLOB_NETWORK


class SlowCom(QWidget):
    remark = ""
    data_info = []
    data_order = []
    labelStyle = {
        "fixedHeight": 30,
        "fixedWidth": 50,
        "styleSheet": "background-color: #88FFFFFF;padding: 0 4px;font-size:12px",
    }
    lineEditStyle = labelStyle.copy()
    lineEditStyle["fixedWidth"] = 200
    btnStyle = labelStyle.copy()
    btnStyle["styleSheet"] = "opacity:0.8;padding: 0 4px;font-size:12px"

    def init_top(self):
        parent = QGridLayout(contentsMargins=QMargins(0, 0, 0, 0), spacing=0)  # type: ignore
        self.srcPath = QLineEdit(
            text=GLOB_CONFIG.value("ui/slow_src_path"), **self.lineEditStyle
        )
        self.srcPath.textChanged.connect(
            lambda x: GLOB_CONFIG.setValue("ui/slow_src_path", x)
        )
        srcSel = QPushButton(text="印刷", **self.btnStyle)  # type: ignore
        srcSel.clicked.connect(lambda: self.select_file(self.srcPath))
        self.srcMvPath = QLineEdit(
            text=GLOB_CONFIG.value("ui/slow_src_mv_path"), **self.lineEditStyle
        )
        self.srcMvPath.textChanged.connect(
            lambda x: GLOB_CONFIG.setValue("ui/slow_src_mv_path", x)
        )
        srcMvSel = QPushButton(text="刀版", **self.btnStyle)  # type: ignore
        srcMvSel.clicked.connect(lambda: self.select_file(self.srcMvPath))
        self.startB = QPushButton(text="提交", fixedHeight=60)  # type: ignore
        self.startB.clicked.connect(self.start)
        parent.addWidget(srcSel, 0, 0, 1, 1)
        parent.addWidget(self.srcPath, 0, 1, 1, 4)
        parent.addWidget(srcMvSel, 0, 5, 1, 1)
        parent.addWidget(self.srcMvPath, 0, 6, 1, 4)
        parent.addWidget(self.startB, 0, 10, 2, 1)

        self.desPath = QLineEdit(
            text=GLOB_CONFIG.value("ui/slow_dest_path"), **self.lineEditStyle
        )
        self.desPath.textChanged.connect(
            lambda x: GLOB_CONFIG.setValue("ui/slow_dest_path", x)
        )
        desSel = QPushButton(text="印&刀", **self.btnStyle)  # type: ignore
        desSel.clicked.connect(lambda: self.select_file(self.desPath))
        self.desDaoPath = QLineEdit(
            text=GLOB_CONFIG.value("ui/slow_dest_dao_path"), **self.lineEditStyle
        )
        self.desDaoPath.textChanged.connect(
            lambda x: GLOB_CONFIG.setValue("ui/slow_dest_dao_path", x)
        )
        desDaoSel = QPushButton(text="自割", **self.btnStyle)  # type: ignore
        desDaoSel.clicked.connect(lambda: self.select_file(self.desDaoPath))
        parent.addWidget(desSel, 1, 0, 1, 1)
        parent.addWidget(self.desPath, 1, 1, 1, 4)
        parent.addWidget(desDaoSel, 1, 5, 1, 1)
        parent.addWidget(self.desDaoPath, 1, 6, 1, 4)
        return parent

    def init_mid(self):
        self.groupbox = QGroupBox("订单信息")
        gridLayout = QGridLayout(contentsMargins=QMargins(4, 4, 4, 4), spacing=2)  # type: ignore

        self.edit_filename = QLineEdit(
            placeholderText="模糊查找[Enter触发'搜索']",
            styleSheet="background-color: #88FFFFFF;padding: 0 4px;font-size:12px",
            fixedHeight=30,
        )  # type: ignore

        self.clearBtn = QPushButton(
            "x",
            styleSheet="background-color:#88229922;border:none;border-radius:20px;padding: 0 4px;font-size:12px",
            fixedWidth=30,
            fixedHeight=30,
        )  # type: ignore
        self.clearBtn.clicked.connect(
            lambda: self.clearBtn.setText("x" if self.clearBtn.text() != "x" else "+")
        )

        self.searchBtn = QPushButton(
            "查询",
            styleSheet="background-color:#88229922;padding: 0 4px;font-size:12px",
            fixedWidth=80,
            fixedHeight=30,
        )  # type: ignore
        self.searchBtn.clicked.connect(self.search)

        createBtn = QPushButton(
            "创建",
            styleSheet="background-color:#887777AA;padding: 0 4px;font-size:12px",
            fixedWidth=80,
            fixedHeight=30,
        )  # type: ignore
        createBtn.clicked.connect(self.create)

        self.edit_typeset = QLineEdit(
            placeholderText="要添加的备注",
            styleSheet="background-color: #88FFFFFF;padding: 0 4px;font-size:12px",
            fixedHeight=30,
        )  # type: ignore

        def listenRemark():
            self.remark = self.edit_typeset.text()
            self.update_type()

        self.edit_typeset.textChanged.connect(listenRemark)

        self.A3Btn = QPushButton(
            "A3",
            styleSheet="background-color:#88CCAA88;padding: 0 4px;font-size:12px",
            fixedWidth=30,
            fixedHeight=30,
        )  # type: ignore

        def a3change():
            self.edit_size.setText(
                "297X420" if self.A3Btn.text() == "A3" else "320X464"
            )
            self.A3Btn.setText("3+" if self.A3Btn.text() == "A3" else "A3")

        self.A3Btn.clicked.connect(a3change)
        self.edit_size = QLineEdit(
            "320X464",
            styleSheet="background-color: #88FFFFFF;padding: 0 4px;font-size:12px",
            fixedWidth=80,
            fixedHeight=30,
        )  # type: ignore

        self.edit_count = QLineEdit(
            placeholderText="张数↲",
            styleSheet="background-color: #88FFFFFF;padding: 0 4px;font-size:12px",
            fixedWidth=80,
            fixedHeight=30,
        )  # type: ignore
        self.edit_count.setValidator(QIntValidator(0, 999999))

        self.type_name = QLineEdit()

        def refresh_folder():
            self.printList.setModel(
                QStringListModel(
                    [
                        os.path.basename(path)
                        for path in glob.iglob(
                            os.path.join(GLOB_CONFIG.value("ui/slow_src_path"), "*.pdf")
                        )
                    ]
                )
            )
            self.cutList.setModel(
                QStringListModel(
                    [
                        os.path.basename(path)
                        for path in glob.iglob(
                            os.path.join(
                                GLOB_CONFIG.value("ui/slow_src_mv_path"), "*.pdf"
                            )
                        )
                    ]
                )
            )

        self.type_name.textChanged.connect(refresh_folder)
        self.type_name.setReadOnly(True)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)  # 内容大小改变时自动调整滚动区域
        scroll.setFixedHeight(200)
        self.edit_count.returnPressed.connect(createBtn.click)
        self.edit_filename.returnPressed.connect(self.searchBtn.click)

        # 创建一个承载内容的 QWidget，并设置其 layout 为 QVBoxLayout
        content = QWidget()
        self.tableLayout = QVBoxLayout(content)
        self.tableLayout.setContentsMargins(2, 0, 0, 0)
        self.tableLayout.setSpacing(0)

        # 把 content 作为 scroll 的可滚动区域
        scroll.setWidget(content)
        self.empty = QLabel("暂无数据", alignment=Qt.AlignmentFlag.AlignCenter)
        self.tableLayout.addWidget(self.empty)
        gridLayout.addWidget(QLabel("单号/旺旺"), 0, 0)
        gridLayout.addWidget(self.edit_filename, 0, 1)
        gridLayout.addWidget(self.edit_count, 0, 3)
        gridLayout.addWidget(self.edit_typeset, 1, 1)
        gridLayout.addWidget(self.clearBtn, 0, 2)
        gridLayout.addWidget(self.searchBtn, 0, 4)
        gridLayout.addWidget(QLabel("备注"), 1, 0)
        gridLayout.addWidget(self.A3Btn, 1, 2)
        gridLayout.addWidget(self.edit_size, 1, 3)
        gridLayout.addWidget(createBtn, 1, 4)
        gridLayout.addWidget(QLabel("大版文件名"), 2, 0)
        gridLayout.addWidget(self.type_name, 2, 1, 1, 4)
        gridLayout.addWidget(scroll, 3, 0, 1, 5)
        gridLayout.setColumnStretch(1, 1)
        self.groupbox.setLayout(gridLayout)
        self.groupbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return self.groupbox

    def __init__(self):
        super(SlowCom, self).__init__()

        layout = QVBoxLayout(contentsMargins=QMargins(0, 0, 0, 0), spacing=0)  # type: ignore
        layout.addLayout(self.init_top())
        self.foldView = QHBoxLayout(contentsMargins=QMargins(4, 4, 4, 4), spacing=4)  # type: ignore
        self.printList = QListView(fixedHeight=60)  # type: ignore
        self.printList.clicked.connect(self.listen)
        self.cutList = QListView(fixedHeight=60)  # type: ignore
        self.cutList.clicked.connect(self.listen)
        self.foldView.addWidget(self.printList)
        self.foldView.addWidget(self.cutList)
        layout.addLayout(self.foldView)
        layout.addWidget(self.init_mid())
        self.browser = QTextBrowser(
            styleSheet="background-color: #99FFFFFF;margin-top:4px"  # type: ignore
        )
        layout.addWidget(self.browser)
        self.setLayout(layout)
        self.pool = ApplicationManager(self.recvMsg)

    def recvMsg(self, obj):
        if "start" == obj:
            self.update_btn(False)
            self.startB.setText("下一个")
            self.edit_filename.clear()
            self.edit_typeset.clear()
            self.type_name.clear()
            self.edit_count.clear()
            self.groupbox.setTitle("查找订单")
            while self.tableLayout.count():
                item = self.tableLayout.takeAt(0)
                if item.widget() and isinstance(item.widget(), ImageTextCheckBox):
                    item.widget().deleteLater()  # type: ignore
            self.printList.setModel(
                QStringListModel(
                    [
                        os.path.basename(path)
                        for path in glob.iglob(
                            os.path.join(GLOB_CONFIG.value("ui/slow_src_path"), "*.pdf")
                        )
                    ]
                )
            )
            self.cutList.setModel(
                QStringListModel(
                    [
                        os.path.basename(path)
                        for path in glob.iglob(
                            os.path.join(
                                GLOB_CONFIG.value("ui/slow_src_mv_path"), "*.pdf"
                            )
                        )
                    ]
                )
            )
        else:
            self.append(obj)

    def select_file(self, key):
        filePath = QFileDialog.getExistingDirectory(self, "选择路径")
        key.setText(filePath)

    def append(self, text):
        self.browser.moveCursor(QTextCursor.MoveOperation.End)
        self.browser.append(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ":\t" + text
        )

    def start(self):
        type_name = self.type_name.text() + ".pdf"

        pList: QStringListModel = self.printList.model()  # type: ignore
        if not self.printList.selectedIndexes():
            pList = QStringListModel(
                [
                    os.path.basename(path)
                    for path in glob.iglob(
                        os.path.join(GLOB_CONFIG.value("ui/slow_src_path"), "*.pdf")
                    )
                ]
            )
            self.printList.setModel(pList)
            for i in range(pList.rowCount()):
                if type_name == pList.data(pList.index(i)):
                    self.printList.setCurrentIndex(pList.index(i))
                    break

            # 获取cutList模型
        cList: QStringListModel = self.cutList.model()  # type: ignore
        if not self.cutList.selectedIndexes():
            cList = QStringListModel(
                [
                    os.path.basename(path)
                    for path in glob.iglob(
                        os.path.join(GLOB_CONFIG.value("ui/slow_src_mv_path"), "*.pdf")
                    )
                ]
            )
            self.cutList.setModel(cList)
            for i in range(cList.rowCount()):
                if type_name == cList.data(cList.index(i)):
                    self.cutList.setCurrentIndex(cList.index(i))
                    break

        pIndex = self.printList.currentIndex()
        pName = pList.data(pIndex) if pIndex.isValid() else None

        cIndex = self.cutList.currentIndex()
        cName = cList.data(cIndex) if cIndex.isValid() else None
        self.pool.submit_new_task(
            dict(
                pName=pName,
                cName=cName,
                size=self.edit_size.text(),
                data=self.data_info,
                orders=self.data_order,
                remark=self.remark,
            ),
        )
        self.startB.setText("提交中。")

    def listen(self):
        # 获取 printList 当前选中项
        pList: QStringListModel = self.printList.model()  # type: ignore
        pIndex = self.printList.currentIndex()
        pName = pList.data(pIndex) if pIndex.isValid() else None

        # 获取 cutList 当前选中项
        cList: QStringListModel = self.cutList.model()  # type: ignore
        cIndex = self.cutList.currentIndex()
        cName = cList.data(cIndex) if cIndex.isValid() else None

        # 如果只有 printList 有选中项，检查 cutList 中是否有重名
        if pName and not cName:
            for i in range(cList.rowCount()):
                if cList.data(cList.index(i)) == pName:
                    self.cutList.setCurrentIndex(cList.index(i))
                    cName = pName
                    break

        # 如果只有 cutList 有选中项，检查 printList 中是否有重名
        if cName and not pName:
            for i in range(pList.rowCount()):
                if pList.data(pList.index(i)) == cName:
                    self.printList.setCurrentIndex(pList.index(i))
                    pName = cName
                    break

    def update_btn(self, disable):
        self.srcPath.setDisabled(disable)
        self.desPath.setDisabled(disable)
        self.srcMvPath.setDisabled(disable)
        self.desDaoPath.setDisabled(disable)

    def update_type(self):
        self.type_name.setText(
            f"{'-'.join(self.data_info[:] + [self.remark])}_手动排版"
        )

    def create(self):
        try:
            count = self.edit_count.text()
            if not count:
                QMessageBox.warning(self, "提示", "张数！！")
                return

            more_info = []
            customer = []
            crafts = []
            material = []
            tags = ["当天", "加急"]
            self.data_order = []
            for i in range(self.tableLayout.count()):
                item = self.tableLayout.itemAt(i).widget()
                if item and isinstance(item, ImageTextCheckBox) and item.isChecked():
                    _ir = item.record
                    more_info.extend(
                        [t for t in tags if t in item.text() and t not in more_info]
                    )

                    data_short = [x for x in item.text().split("-")[0] if x]
                    if _ir["systemOrderNo"] not in data_short:
                        self.data_order.append(_ir["systemOrderNo"] + "-" + item.text())

                    craft_list = []
                    if "^" in item.text():
                        parts = item.text().split("^")
                        for _index, sp in enumerate(parts):
                            if re.match(r"\d+x\d+", sp):
                                if _index > 0:
                                    craft_list.extend(parts[_index - 1].split(","))
                                if _index > 4:
                                    customer.append(parts[_index - 5])
                    else:
                        if _ir["flowTbName"] not in customer:
                            customer.append(_ir["flowTbName"])
                        craft_list.extend(
                            _ir["productMain"]["productSimpleCraft"].split(",")
                        )
                    for c in craft_list:
                        if c not in crafts:
                            crafts.append(c)
                    m = _ir["productMain"]["productSimpleMaterial"].split(":")[-1]
                    if m not in material:
                        material.append(m)
            if len(material) > 1:
                QMessageBox.warning(self, "错误", "只能选择同种材质的订单创建大版！")
                return

            def handle_reply(resp):
                if resp["code"] == 200:
                    self.data_info = [
                        resp["data"],
                        ",".join(customer),
                        material[0],
                        ",".join(crafts),
                        self.edit_size.text(),
                        f"{count}张",
                    ]
                    self.data_info.extend(more_info)
                    print(self.data_info)
                    self.update_type()
                    self.groupbox.setTitle(f"原：{','.join(self.data_order)}")
                    self.append(f"创建大版成功： 新=>{self.type_name.text()}")
                else:
                    QMessageBox.warning(self, "错误", resp["msg"])
                    self.append(f'创建大版失败：{resp["msg"]}')

            GLOB_NETWORK.get(
                "production-api/typesettingNew/creatAdhesiveTypesettingNo",
                resp=handle_reply,
            )
        except Exception as e:
            self.append(f"创建大版报错：{e}")

    def search(self):
        try:
            self.groupbox.setTitle("订单信息")
            if self.clearBtn.text() == "x":
                # 清理表格布局中的所有组件
                while self.tableLayout.count():
                    item = self.tableLayout.takeAt(0)
                    if item.widget() and isinstance(item.widget(), ImageTextCheckBox):
                        item.widget().deleteLater()  # type: ignore

            self.searchBtn.setDisabled(True)
            self.searchBtn.setText("查询中...")
            request_data = {"page": 1, "pageSize": 30}

            def _resp(resp):
                self.searchBtn.setDisabled(False)
                self.searchBtn.setText("查询")
                if resp["code"] == 200:
                    content = resp["data"]["records"]
                    if len(content):
                        self.empty.hide()
                        for record in content:
                            self.tableLayout.addWidget(ImageTextCheckBox(record))
                        item = self.tableLayout.itemAt(0).widget()
                        if isinstance(item, ImageTextCheckBox):
                            item.setChecked(True)
                    elif "systemOrderNo" in request_data:
                        del request_data["systemOrderNo"]
                        request_data["flowTbName"] = self.edit_filename.text()  # type: ignore
                        GLOB_NETWORK.post(
                            "production-api/produce/produceList",
                            resp=_resp,
                            data=request_data,
                        )
                    else:
                        self.empty.show()
                        self.empty.setText("找到0条数据")
                    self.append(
                        f'{"追加" if self.clearBtn.text() == "+" else "清除"}获取【{self.edit_filename.text()}】共 {len(content)}条'
                    )
                else:
                    self.empty.show()
                    self.empty.setText(resp["msg"])
                    self.append(
                        f'{"追加" if self.clearBtn.text() == "+" else "清除"}获取【{self.edit_filename.text()}】失败：{resp["msg"]}'
                    )
                pass

            request_data["systemOrderNo"] = self.edit_filename.text()  # type: ignore
            GLOB_NETWORK.post(
                "production-api/produce/produceList", resp=_resp, data=request_data
            )

        except Exception as e:
            self.append(f"查询订单报错:{e}")
