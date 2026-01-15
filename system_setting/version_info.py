import os
from pathlib import Path
import traceback

import debugpy
from trayapp import constant
from typing import Optional, Dict
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
    后台线程：负责检查更新、对比MD5、下载文件
    """

    # 信号：组件ID, 状态文本, 按钮是否可用
    status_changed = Signal(str, str, bool)
    # 信号：进度值 (0-100)
    progress_changed = Signal(dict)
    # 信号：检查结束
    finished_check = Signal()

    def __init__(self, settings: QSettings, auto_download: bool = False):
        super().__init__()
        self.app_dir = Path(__file__).parent.parent
        self.settings = settings
        self.auto_download = auto_download
        self.running = True
        self.wait_file_list = {}

    def _get_file_list(self, comp, new_version):
        old_path = self.app_dir / constant.DIR_BIN / comp["sub_dir"]
        new_key = comp["key"] + "/" + new_version["version"]
        files_info = get_file_list(new_key)
        count = 0
        for file_info in files_info:
            if int(file_info["Size"]) == 0:
                continue
            new_md5 = file_info["ETag"].strip('"')
            old_file: Path = old_path / (file_info["Key"].replace(new_key, ""))
            if not old_file.exists() or md5_single(old_file) != new_md5:
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
        """
        核心逻辑：
        1. 遍历所有组件。
        2. 获取本地版本 (QSettings) 和 远程版本。
        3. 如果 auto_download=True 且需要更新，则模拟下载。
        4. 检查 new_version 下的文件是否完整。
        """
        try:
            debugpy.debug_this_thread()
        except Exception:
            # 非调试状态下忽略
            pass
        # 1. 统计脚本数量
        js_count_str = count_files_in_dir(self.app_dir / constant.DIR_JAVASCRIPT)
        self.status_changed.emit("ScriptCount", js_count_str, False)
        text = ""
        status_text = ""
        progress = 0
        for idx, comp in enumerate(constant.COMPONENT_MAP):
            if not self.running:
                break
            try:
                key = comp["key"]
                current_ver_code = self.settings.value(f"{key}/versionCode", 0)
                current_ver = self.settings.value(f"{key}/version", "0.0.0")
                r_ver = get_app_version_info(key)
                if r_ver["versionCode"] > current_ver_code:
                    # 如果开启了自动下载 且 文件未就绪，则开始下载
                    if self.auto_download:
                        self._get_file_list(comp, r_ver)
                        text = f' {comp["name"]} 获取文件列表中...'
                    else:
                        text = f' {comp["name"]} 获取下载信息 {r_ver["version"]}'
                        status_text = f"最新:{r_ver['versionCode']}[{r_ver['version']}]"
                else:
                    text = f' {comp["name"]} 获取版本信息 无更新'
                    status_text = f"当前:{current_ver_code}[{current_ver}]"
                progress = int(((idx + 1) / 8) * 100)
            except:
                traceback.print_exc()
                text = f' {comp["name"]} 获取版本信息  Fail'
            (self.status_changed.emit(key, status_text, False) if status_text else None)
            self.progress_changed.emit({"progress": progress, "text": text})
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
                download_single_file(
                    a["Key"], Path(a["Key"].replace(new_key, new_path))
                )
                count += 1
                progress = int(((count + 1) / total) * 100)
                text = f"正在下载{v['comp']['name']}{v['ver']['version']} ==> {count} /{total}"
                self.progress_changed.emit({"progress": progress, "text": text})
            status_text = f"最新:{v['ver']['versionCode']}[{v['ver']['version']}]"
            self.status_changed.emit(k, status_text, True)

    def stop(self):
        self.running = False


class VersionInfo(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = QSettings("Qiyin", "inklink")

        self._setup_ui()
        # 默认启动一次普通检查（不下载）
        self._start_worker(auto_download=False)
        self.btn_check_all.setDisabled(True)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 0. 顶部控制区 (新增)
        group_control = QGroupBox("全局操作")
        layout_control = QHBoxLayout()

        self.btn_check_all = QPushButton("批量检测并下载")
        self.btn_check_all.setCursor(Qt.PointingHandCursor)
        self.btn_check_all.setStyleSheet(
            """
            QPushButton {
                background-color: #409eff; 
                color: white; 
                font-weight: bold; 
                border-radius: 5px; 
                font-size: 14px;
                padding: 6px 12px;

            }
            QPushButton:hover { background-color: #66b1ff; }
            QPushButton:disabled { background-color: #a0cfff; }
        """
        )
        self.btn_check_all.clicked.connect(self.on_batch_check_clicked)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout_control.addWidget(self.btn_check_all)
        layout_control.addWidget(self.progress_bar)
        layout_ctrl_top = QVBoxLayout()
        layout_ctrl_top.addLayout(layout_control)
        self.progress_label = QLabel("")
        layout_ctrl_top.addWidget(
            self.progress_label, alignment=Qt.AlignmentFlag.AlignCenter
        )
        group_control.setLayout(layout_ctrl_top)
        main_layout.addWidget(group_control)
        main_layout.addStretch()

        # 1. 版本列表区域
        group_versions = QGroupBox("组件版本状态")
        container = QWidget()
        self.items_layout = QGridLayout(container)
        self.items_layout.setHorizontalSpacing(30)
        self.widgets: Dict[str, VersionItemWidget] = {}
        for index, comp in enumerate(constant.COMPONENT_MAP):
            w = VersionItemWidget(comp["name"], comp["key"])
            w.btn_update.clicked.connect(
                lambda checked, c=comp: self.on_update_clicked(c)
            )
            self.items_layout.addWidget(w, index // 2, index % 2)
            self.widgets[comp["key"]] = w
        ver_layout = QVBoxLayout()
        ver_layout.addWidget(container)
        group_versions.setLayout(ver_layout)
        main_layout.addWidget(group_versions)
        # 2. 脚本统计区域
        group_scripts = QGroupBox("资源统计")
        layout_scripts = QHBoxLayout()
        lbl_name = QLabel("报价脚本")
        lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_count = QLabel("统计中...")
        layout_scripts.addStretch()
        layout_scripts.addWidget(lbl_name)
        layout_scripts.addWidget(self.lbl_count)
        group_scripts.setLayout(layout_scripts)
        layout_scripts.addStretch()
        main_layout.addWidget(group_scripts)

    def _start_worker(self, auto_download: bool = False):
        """启动后台检测线程"""
        # 如果已有线程在运行，先停止
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
        """点击批量检测按钮"""
        self.btn_check_all.setEnabled(False)
        self.btn_check_all.setText("停止下载")
        self.progress_bar.setValue(0)
        # 启动带自动下载功能的 Worker
        self._start_worker(auto_download=True)

    def on_check_finished(self):
        """检查结束"""
        self.btn_check_all.setEnabled(True)
        self.btn_check_all.setText("批量检测并下载")
        if self.progress_bar.value() < 100:
            self.progress_bar.setValue(100)

    @Slot(str, str, bool)
    def on_worker_status_changed(self, key: str, status_text: str, is_ready: bool):
        """响应后台线程的状态更新"""
        if key == "ScriptCount":
            self.lbl_count.setText(status_text)
        elif key in self.widgets:
            self.widgets[key].set_status(status_text, is_ready)

    def on_update_clicked(self, comp_info: Dict):
        """
        点击更新按钮后的逻辑
        """
        source_dir = self.app_dir / constant.DIR_NEW_VERSION / comp_info["sub_dir"]
        if comp_info["sub_dir"] == "main":
            target_dir = self.app_dir
        else:
            target_dir = self.app_dir / constant.DIR_BIN / comp_info["sub_dir"]

        exe_path = os.path.abspath(comp_info["exe"])

        reply = QMessageBox.question(
            self,
            "确认更新",
            f"确定要关闭 [{comp_info['name']}] 并执行更新吗？\n\n程序将重启。",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.run_external_updater(source_dir, target_dir, exe_path)

    def run_external_updater(self, source: Path, target: Path, restart_exe: str):
        updater_path = self.app_dir / "updater.bat"

        if not os.path.exists(updater_path):
            self.create_mock_updater(updater_path)

        success = QProcess.startDetached(updater_path, [source, target, restart_exe])

        if success:
            print(f"Updater started: {source} -> {target}")
            # QApplication.quit()
        else:
            QMessageBox.critical(self, "错误", "无法启动更新脚本！")

    def create_mock_updater(self, path: str):
        content = """@echo off
timeout /t 2
echo Killing processes...
echo Copying files from %1 to %2 ...
xcopy /s /y "%~1\\*.*" "%~2\\"
echo Starting %3 ...
start "" "%~3"
exit
"""
        try:
            with open(path, "w", encoding="gbk") as f:
                f.write(content)
        except Exception as e:
            print(f"Failed to create mock updater: {e}")

    def closeEvent(self, event):
        if hasattr(self, "worker"):
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)


class VersionItemWidget(QWidget):
    """单行版本信息组件"""

    def __init__(self, title: str, key: str, parent=None):
        super().__init__(parent)
        self.key = key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)

        # 名称
        self.lbl_name = QLabel(title)
        self.lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")

        # 状态/版本信息
        self.lbl_status = QLabel("等待检测...")
        self.lbl_status.setStyleSheet("color: #666;")

        # 更新按钮
        self.btn_update = QPushButton("更新并重启")
        self.btn_update.setEnabled(False)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        # 样式优化
        self.btn_update.setStyleSheet(
            """
            QPushButton {
                background-color: #0078d7; color: white; border-radius: 4px; padding: 5px 10px;
            }
            QPushButton:disabled {
                background-color: #cccccc; color: #888888;
            }
            QPushButton:hover {
                background-color: #0063b1;
            }
        """
        )

        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_status)
        layout.addStretch()
        layout.addWidget(self.btn_update)

    def set_status(self, text: str, is_ready: bool):
        self.lbl_status.setText(text)
        self.btn_update.setEnabled(is_ready)
        if is_ready:
            self.lbl_status.setStyleSheet("color: #28a745; font-weight: bold;")  # 绿色
        elif "下载" in text:
            self.lbl_status.setStyleSheet("color: #e6a23c; font-weight: bold;")  # 橙色
        else:
            self.lbl_status.setStyleSheet("color: #666;")
