from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QRadioButton,
    QPushButton,
    QLabel,
    QWidget,
    QScrollArea,
    QFrame,
    QComboBox,
)
from PySide6.QtCore import Qt


class SingleSelectDialog(QDialog):
    def __init__(
        self, options, title="请选择", default=None, parent=None, merge_wid_visiable=0
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 260)
        self.selected = None
        self.merge_wid_visiable = merge_wid_visiable
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 标题
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(title_label)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_widget = QWidget()
        scroll_layout = QHBoxLayout(scroll_widget)
        scroll_layout.setAlignment(Qt.AlignCenter)
        scroll_layout.setSpacing(20)
        scroll_layout.setContentsMargins(10, 10, 10, 10)

        self.radios = []
        for i, opt in enumerate(options):
            r = QRadioButton(opt)
            r.setStyleSheet(
                """
                QRadioButton {
                    font-size: 14px;
                    padding: 6px 12px;
                    border-radius: 8px;
                }
                QRadioButton::indicator {
                    width: 18px;
                    height: 18px;
                }
            """
            )
            # 默认选中逻辑
            # if (default and opt == default) or (default is None and i == 0):
            #     r.setChecked(True)
            r.clicked.connect(self.radios_clicked)
            scroll_layout.addWidget(r)
            self.radios.append(r)
        self.radios[0].setChecked(True)

        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        self.merge_wid = QWidget()
        self.merge_layout = QHBoxLayout()
        self.merge_combox = QComboBox()
        self.merge_combox.addItems(["分开单独ai", "合并到一个ai"])
        self.merge_layout.addStretch()
        self.merge_layout.addWidget(QLabel("选择方式:"))
        self.merge_layout.addWidget(self.merge_combox)
        self.merge_layout.addStretch()
        self.merge_wid.setLayout(self.merge_layout)
        main_layout.addWidget(self.merge_wid)
        self.merge_wid.setVisible(self.merge_wid_visiable)
        # 按钮区（居中）
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.setSpacing(20)

        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")

        btn_ok.setFixedWidth(80)
        btn_cancel.setFixedWidth(80)

        btn_ok.setStyleSheet(
            """
            QPushButton {
                background-color: #0078d7;
                color: white;
                padding: 6px 15px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #006bb3;
            }
        """
        )
        btn_cancel.setStyleSheet(
            """
            QPushButton {
                background-color: #e0e0e0;
                color: #333;
                padding: 6px 15px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #c8c8c8;
            }
        """
        )

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        main_layout.addLayout(btn_layout)

    def radios_clicked(self):
        self.merge_wid.setVisible(
            self.sender().text() == ".ai" and self.merge_wid_visiable
        )

    def get_selected(self):
        for r in self.radios:
            if r.isChecked():
                return r.text(), self.merge_combox.currentIndex()
        return None, 0
