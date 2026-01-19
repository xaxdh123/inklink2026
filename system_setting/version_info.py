import os
from pathlib import Path
import traceback
from typing import Optional, Dict

import debugpy
from trayapp import constant
from PySide6.QtWidgets import (
    QGridLayout,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QProgressBar,
    QFrame,
    QScrollArea,
    QDialog,
)
from PySide6.QtCore import Qt, QSettings, QThread, Signal, Slot, QProcess
from trayapp.cos_utils import (
    count_files_in_dir,
    download_single_file,
    get_app_version_info,
    get_file_list,
    md5_single,
)


class UpdateCheckWorker(QThread):
    """
    后台线程：负责检查更新、对比MD5、下载文件（业务逻辑完全保留）
    """

    status_changed = Signal(str, str, bool)
    progress_changed = Signal(dict)
    finished_check = Signal()

    def __init__(self, settings: QSettings, auto_download: bool = False):
        super().__init__()
        self.app_dir = Path(__file__).parent.parent
        self.settings = settings
        self.auto_download = auto_download
        self.running = True
        self.wait_file_list = {}

    def _get_file_list(self, comp, new_version):
        """
        核心逻辑修改：
        1. 先判断 DIR_NEW_VERSION 文件夹（已下载但未覆盖的文件）
        2. 再判断 DIR_BIN 文件夹（当前正在使用的旧文件）
        """
        # 定义两个对比路径
        bin_path = self.app_dir / constant.DIR_BIN / comp["sub_dir"]
        new_ver_path = self.app_dir / constant.DIR_NEW_VERSION / comp["sub_dir"]

        new_key = comp["key"] + "/" + new_version["version"]
        # 从 COS 拉取该组件版本的文件清单
        files_info = get_file_list(new_key)
        count = 0

        for file_info in files_info:
            if int(file_info["Size"]) == 0:
                continue


            new_md5 = file_info["ETag"].strip('"')
            relative_file_path = file_info["Key"].replace(new_key, "").lstrip("/")

            # 路径 1: 检查新版本暂存区是否已经下载了正确的文件
            temp_file: Path = new_ver_path / relative_file_path
            if temp_file.exists() and md5_single(temp_file) == new_md5:
                # 暂存区已有，无需重复下载
                continue

            # 路径 2: 检查当前 bin 目录是否已经是最新
            old_file: Path = bin_path / relative_file_path
            if not old_file.exists() or md5_single(old_file) != new_md5:
                # 两个地方都没有最新文件，加入下载列表
                # 按组件 key 聚合待下载文件清单
                if comp["key"] not in self.wait_file_list:
                    self.wait_file_list[comp["key"]] = {
                        "comp": comp,
                        "ver": new_version,
                        "list": [],
                    }
                self.wait_file_list[comp["key"]]["list"].append(file_info)
                count += 1


        self.status_changed.emit(comp["key"], f"共{count}个文件需下载", False)

    def run(self):
        try:
            debugpy.debug_this_thread()
        except Exception:
            pass

        js_count_str = count_files_in_dir(self.app_dir / constant.DIR_JAVASCRIPT)
        self.status_changed.emit("ScriptCount", js_count_str, False)

        for idx, comp in enumerate(constant.COMPONENT_MAP):
            if not self.running:
                break
            try:
                status_text = ""
                key = comp["key"]
                current_ver_code = self.settings.value(f"{key}/versionCode", 0)
                current_ver = self.settings.value(f"{key}/version", "0.0.0")
                r_ver = get_app_version_info(key)

                if r_ver["versionCode"] > current_ver_code:
                    if self.auto_download:
                        self._get_file_list(comp, r_ver)
                        text = f' {comp["name"]} 获取文件列表中...'
                    else:
                        text = f' {comp["name"]} 获取下载信息 {r_ver["version"]}'
                        status_text = f"最新:{r_ver['versionCode']}[{r_ver['version']}]"
                else:
                    text = f' {comp["name"]} 获取版本信息 无更新'
                    status_text = f"当前:{current_ver_code}[{current_ver}]"

                progress = int(((idx + 1) / len(constant.COMPONENT_MAP)) * 100)
                if status_text:
                    self.status_changed.emit(key, status_text, False)
                self.progress_changed.emit({"progress": progress, "text": text})
            except:
                traceback.print_exc()
                self.progress_changed.emit(
                    {"progress": 0, "text": f' {comp["name"]} 获取信息失败'}
                )

        if self.auto_download and len(self.wait_file_list):
            self.simulate_download_files()
        self.finished_check.emit()

    def simulate_download_files(self):
        count = 0
        total = sum([len(v["list"]) for v in self.wait_file_list.values()])
        for k, v in self.wait_file_list.items():
            new_path = str(
                self.app_dir / constant.DIR_NEW_VERSION / v["comp"]["sub_dir"]
            )
            new_key = k + "/" + v["ver"]["version"]
            for a in v["list"]:
                if not self.running:
                    return
                # 将 COS Key 映射为本地 new_version 路径
                download_single_file(
                    a["Key"], Path(a["Key"].replace(new_key, new_path))
                )

                count += 1
                progress = int((count / total) * 100)
                text = f"正在下载 {v['comp']['name']} {v['ver']['version']} ==> {count}/{total}"
                self.progress_changed.emit({"progress": progress, "text": text})

            status_text = f"最新:{v['ver']['versionCode']}[{v['ver']['version']}]"
            self.status_changed.emit(k, status_text, True)

    def stop(self):
        self.running = False


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
        self.settings = QSettings("Qiyin", "inklink")
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

        self.worker = UpdateCheckWorker(self.settings, auto_download=auto_download)
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
