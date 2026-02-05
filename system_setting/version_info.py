import os
from pathlib import Path
from typing import Optional, Dict

from system_setting.UpdateCheckWorker import UpdateCheckWorker
from trayapp import constant
from PySide6.QtWidgets import (
    QGridLayout,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
    QScrollArea,
    QDialog,
)
from PySide6.QtCore import Qt, Slot, QProcess

from utils import GLOB_CONFIG


class VersionItemWidget(QFrame):
    """单行版本信息卡片 - 样式优化版"""

    def __init__(self, title: str, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("VersionCard")
        self._setup_ui(title)

    def _setup_ui(self, title):
        self.setStyleSheet(
            """
            #VersionCard {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            #VersionCard:hover {
                border: 1px solid #409eff;
                background-color: #fcfdfe;
            }
        """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)

        self.lbl_name = QLabel(title)
        self.lbl_name.setStyleSheet("font-weight: 600; font-size: 14px; color: #333;")

        self.lbl_status = QLabel("等待检测...")
        self.lbl_status.setStyleSheet("color: #909399; font-size: 12px;")

        self.btn_update = QPushButton("更新并重启")
        self.btn_update.setEnabled(False)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setFixedSize(90, 30)
        self.btn_update.setStyleSheet(
            """
            QPushButton {
                background-color: #409eff; color: white; border-radius: 4px;
                font-size: 12px; font-weight: bold; border: none;
            }
            QPushButton:hover { background-color: #66b1ff; }
            QPushButton:disabled {
                background-color: #f5f7fa; color: #c0c4cc; border: 1px solid #e4e7ed;
            }
        """
        )

        layout.addWidget(self.lbl_name)
        layout.addSpacing(10)
        layout.addWidget(self.lbl_status)
        layout.addStretch()
        layout.addWidget(self.btn_update)

    def set_status(self, text: str, is_ready: bool):
        self.lbl_status.setText(text)
        self.btn_update.setEnabled(is_ready)
        if is_ready:
            self.lbl_status.setStyleSheet(
                "color: #67c23a; font-weight: bold; font-size: 12px;"
            )
            self.setStyleSheet(
                "#VersionCard { border: 1px solid #67c23a; background-color: #f0f9eb; }"
            )
        elif "下载" in text:
            self.lbl_status.setStyleSheet(
                "color: #e6a23c; font-weight: bold; font-size: 12px;"
            )
        else:
            self.lbl_status.setStyleSheet("color: #909399; font-size: 12px;")


class VersionInfo(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.app_dir = Path(__file__).parent.parent

        self.setStyleSheet("background-color: #f5f7f9;")
        self._setup_ui()

        # 初始化检查
        self._start_worker(auto_download=False)
        self.btn_check_all.setDisabled(True)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 顶部面板
        top_panel = QFrame()
        top_panel.setStyleSheet(
            "background-color: white; border-radius: 10px; border: 1px solid #ebedf0;"
        )
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(20, 15, 20, 15)

        title_layout = QHBoxLayout()
        title_lbl = QLabel("系统组件管理")
        title_lbl.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #2c3e50; border:none;"
        )

        self.btn_check_all = QPushButton("批量检测并下载")
        self.btn_check_all.setCursor(Qt.PointingHandCursor)
        self.btn_check_all.setMinimumWidth(140)
        self.btn_check_all.setStyleSheet(
            """
            QPushButton {
                background-color: #409eff; color: white; font-weight: bold;
                border-radius: 6px; padding: 8px 15px; font-size: 13px; border: none;
            }
            QPushButton:hover { background-color: #66b1ff; }
            QPushButton:disabled { background-color: #a0cfff; }
        """
        )
        self.btn_check_all.clicked.connect(self.on_batch_check_clicked)

        title_layout.addWidget(title_lbl)
        title_layout.addStretch()
        title_layout.addWidget(self.btn_check_all)
        top_layout.addLayout(title_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar { background-color: #ebeef5; border-radius: 4px; border: none; }
            QProgressBar::chunk { background-color: #409eff; border-radius: 4px; }
        """
        )
        top_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("准备就绪")
        self.progress_label.setStyleSheet(
            "color: #606266; font-size: 12px; border: none;"
        )
        top_layout.addWidget(self.progress_label)

        main_layout.addWidget(top_panel)

        # 列表滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        self.items_layout = QGridLayout(container)
        self.items_layout.setContentsMargins(0, 5, 0, 5)
        self.items_layout.setSpacing(12)

        self.widgets: Dict[str, VersionItemWidget] = {}
        for index, comp in enumerate(constant.COMPONENT_MAP):
            w = VersionItemWidget(comp["name"], comp["key"])
            w.btn_update.clicked.connect(
                lambda checked, c=comp: self.on_update_clicked(c)
            )
            self.items_layout.addWidget(w, index // 2, index % 2)
            self.widgets[comp["key"]] = w

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # 底部统计
        footer = QFrame()
        footer.setFixedHeight(40)
        footer.setStyleSheet(
            "background-color: #eef1f6; border-radius: 6px; border: 1px solid #dcdfe6;"
        )
        footer_layout = QHBoxLayout(footer)

        lbl_script_tag = QLabel("报价脚本统计:")
        lbl_script_tag.setStyleSheet("color: #475669; font-weight: bold; border: none;")
        self.lbl_count = QLabel("统计中...")
        self.lbl_count.setStyleSheet("color: #409eff; font-weight: bold; border: none;")

        footer_layout.addStretch()
        footer_layout.addWidget(lbl_script_tag)
        footer_layout.addWidget(self.lbl_count)
        footer_layout.addStretch()
        main_layout.addWidget(footer)

    def _show_custom_message(
        self, title: str, content: str, is_question: bool = False
    ) -> bool:
        """自定义美化版的消息对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dialog.setAttribute(Qt.WA_TranslucentBackground)

        container = QFrame(dialog)
        container.setObjectName("DialogContainer")
        container.setFixedSize(360, 200)
        container.setStyleSheet(
            """
            #DialogContainer {
                background-color: white;
                border: 1px solid #dcdfe6;
                border-radius: 12px;
            }
            QLabel#Title {
                font-size: 16px; font-weight: bold; color: #303133; border: none;
                padding: 8px;
            }
            QLabel#Content {
                font-size: 14px; color: #606266; border: none;
                padding: 8px;
            }
        """
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(25, 20, 25, 20)

        # 标题栏
        title_lbl = QLabel(title)
        title_lbl.setObjectName("Title")
        layout.addWidget(title_lbl)
        layout.addSpacing(10)

        # 内容区
        content_lbl = QLabel(content)
        content_lbl.setObjectName("Content")
        content_lbl.setWordWrap(True)
        content_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(content_lbl)
        layout.addStretch()

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_confirm = QPushButton("确定")
        btn_confirm.setCursor(Qt.PointingHandCursor)
        btn_confirm.setFixedHeight(34)
        btn_confirm.setStyleSheet(
            """
            QPushButton {
                background-color: #409eff; color: white; border-radius: 4px;
                font-weight: bold; border: none; padding: 0 20px;
            }
            QPushButton:hover { background-color: #66b1ff; }
        """
        )
        btn_confirm.clicked.connect(dialog.accept)

        if is_question:
            btn_cancel = QPushButton("取消")
            btn_cancel.setCursor(Qt.PointingHandCursor)
            btn_cancel.setFixedHeight(34)
            btn_cancel.setStyleSheet(
                """
                QPushButton {
                    background-color: white; color: #606266; border-radius: 4px;
                    border: 1px solid #dcdfe6; padding: 0 20px;
                }
                QPushButton:hover { background-color: #f5f7fa; color: #409eff; border-color: #c6e2ff; }
            """
            )
            btn_cancel.clicked.connect(dialog.reject)
            btn_layout.addStretch()
            btn_layout.addWidget(btn_cancel)
            btn_layout.addWidget(btn_confirm)
        else:
            btn_layout.addStretch()
            btn_layout.addWidget(btn_confirm)

        layout.addLayout(btn_layout)

        # 让对话框居中
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)

        return dialog.exec() == QDialog.Accepted

    def _start_worker(self, auto_download: bool = False):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        self.worker = UpdateCheckWorker(GLOB_CONFIG, auto_download=auto_download)
        self.worker.status_changed.connect(self.on_worker_status_changed)
        self.worker.progress_changed.connect(self.progress_update)
        self.worker.finished_check.connect(self.on_check_finished)
        self.worker.start()

    @Slot(dict)
    def progress_update(self, data):
        if "progress" in data:
            self.progress_bar.setValue(data["progress"])
        if "text" in data:
            self.progress_label.setText(data["text"])

    def on_batch_check_clicked(self):
        self.btn_check_all.setEnabled(False)
        self.btn_check_all.setText("正在下载...")
        self.progress_bar.setValue(0)
        self._start_worker(auto_download=True)

    def on_check_finished(self):
        self.btn_check_all.setEnabled(True)
        self.btn_check_all.setText("批量检测并下载")
        if self.progress_bar.value() < 100:
            self.progress_bar.setValue(100)

    @Slot(str, str, bool)
    def on_worker_status_changed(self, key: str, status_text: str, is_ready: bool):
        if key == "ScriptCount":
            self.lbl_count.setText(status_text)
        elif key in self.widgets:
            self.widgets[key].set_status(status_text, is_ready)

    def on_update_clicked(self, comp_info: Dict):
        source_dir = self.app_dir / constant.DIR_NEW_VERSION / comp_info["sub_dir"]
        if comp_info["sub_dir"] == "main":
            target_dir = self.app_dir
        else:
            target_dir = self.app_dir / constant.DIR_BIN / comp_info["sub_dir"]

        exe_path = os.path.abspath(target_dir / comp_info["exe"])

        # 使用自定义美化版弹窗
        confirmed = self._show_custom_message(
            "确认更新",
            f"确定要关闭 [{comp_info['name']}] 并执行更新吗？\n\n更新完成后程序将自动重启。",
            is_question=True,
        )

        if confirmed:
            self.run_external_updater(source_dir, target_dir, exe_path)

    def run_external_updater(self, source: Path, target: Path, restart_exe: str):
        updater_path = self.app_dir / constant.DIR_BIN / "updater.bat"
        success = QProcess.startDetached(
            str(updater_path), [str(source), str(target), restart_exe]
        )
        if not success:
            # 这里的错误提示也改用自定义弹窗
            self._show_custom_message("错误", "无法启动外部更新脚本，请检查权限！")

    def closeEvent(self, event):
        if hasattr(self, "worker"):
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)
