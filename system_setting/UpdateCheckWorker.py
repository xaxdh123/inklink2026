import traceback

from pathlib import Path
import debugpy
from trayapp import constant
from PySide6.QtCore import QSettings, QThread, Signal
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

    @staticmethod
    def _safe_int(value, default=0):
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

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
                current_ver_code = self._safe_int(
                    self.settings.value(f"{key}/versionCode", 0), 0
                )
                current_ver = self.settings.value(f"{key}/version", "0.0.0")
                r_ver = get_app_version_info(key)

                if not r_ver or "versionCode" not in r_ver:
                    text = f' {comp["name"]} 获取版本信息失败'
                    status_text = "获取版本信息失败"
                else:
                    r_ver_code = self._safe_int(r_ver.get("versionCode", 0), 0)
                    r_ver_name = r_ver.get("version", "0.0.0")

                if status_text:
                    pass
                elif r_ver_code > current_ver_code:
                    if self.auto_download:
                        self._get_file_list(comp, r_ver)
                        text = f' {comp["name"]} 获取文件列表中...'
                    else:
                        text = f' {comp["name"]} 获取下载信息 {r_ver_name}'
                        status_text = f"最新:{r_ver_code}[{r_ver_name}]"
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
