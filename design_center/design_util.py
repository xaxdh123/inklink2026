import os
import shutil
import traceback
import json
import re
import subprocess
from PySide6 import QtWidgets, QtCore
from design_center.design_worker import DesignTaskWorker
from design_center.SingleSelectDialog import SingleSelectDialog
from trayapp import constant
from utils import GLOB_CONFIG

class DesignUtil:
    """
    设计中心工具类，重构后支持异步任务处理，避免主线程卡顿。
    """
    def __init__(self):
        self.active_workers = []

    def _cf_emit(self, signal, data):
        if signal:
            signal.emit(data)

    def _cf_fail(self, signal, title, err):
        msg = f"{title}: {err}"
        print(msg)
        self._cf_emit(signal, {"msg": msg})

    def openDesignFile(self, path, signal):
        if not path or not os.path.exists(path):
            self._cf_emit(signal, {"msg": "文件不存在或路径为空"})
            return
        try:
            if os.name == 'nt':
                os.startfile(path)
            else:
                subprocess.run(['xdg-open', path])
        except Exception as e:
            self._cf_fail(signal, "文件打开失败", e)

    def jumpToDesignFile(self, path, signal):
        if not path:
            self._cf_emit(signal, {"msg": "路径为空"})
            return
        os.makedirs(path, exist_ok=True)
        self.openDesignFile(path, signal)

    def confirmFinalDraft(self, data, signal):
        """
        确认定稿逻辑：重构为异步处理。
        """
        try:
            items = self._normalize_event_data(data)
            if not items:
                return self._cf_fail(signal, "确认定稿失败", "无效的数据格式")
            
            # 1. 查找定稿候选文件
            cand_dict = self._cf_find_candidates(items)
            if not cand_dict:
                return self._cf_fail(signal, "确认定稿失败", "未找到符合条件的定稿文件")
            
            # 2. 用户选择文件（UI 交互必须在主线程）
            selected_paths = self._cf_select_candidates(cand_dict)
            if not selected_paths:
                return
            
            # 3. 准备异步任务
            jobs = self._cf_build_ai_to_pdf_jobs(items)
            # 默认存储路径
            dpath = items[0].get("finalDraftDath", os.path.join(os.path.expanduser("~"), "Documents", "InkLink", "FinalDrafts"))
            flow_id = items[0].get("flowDesignId", "unknown")
            third_no = items[0].get("thirdOrderNo", "")
            
            upload_params = {
                "src_paths": selected_paths,
                "dpath": dpath,
                "flow_id": flow_id,
                "third_no": third_no,
                "remove_set": set()
            }
            
            # 4. 启动异步工作线程
            worker = DesignTaskWorker("export_pdf_and_upload", {"jobs": jobs, "upload_params": upload_params})
            worker.finished.connect(lambda res: self._on_task_finished(res, signal))
            worker.error.connect(lambda t, e: self._cf_fail(signal, t, e))
            
            self.active_workers.append(worker)
            worker.start()
            
            self._cf_emit(signal, {"msg": "定稿处理已在后台开始，请稍候..."})
            
        except Exception as e:
            self._cf_fail(signal, "确认定稿异常", e)

    def _on_task_finished(self, result, signal):
        if result.get("type") == "update_fs_path":
            flow_id = result.get("flow_id")
            dest_path = result.get("dest_path")
            runJS = self._cf_build_update_fs_path_js(flow_id, dest_path)
            self._cf_emit(signal, {"runJS": runJS})
        elif result.get("type") == "export_pdf_and_upload":
            self._cf_emit(signal, {"msg": "定稿处理完成！"})

    def _normalize_event_data(self, data):
        if isinstance(data, str):
            try: data = json.loads(data)
            except: return []
        if isinstance(data, dict):
            data = data.get("data", [])
        return data if isinstance(data, list) else []

    def _cf_find_candidates(self, items):
        out = {}
        for it in items:
            full = it.get("designOriginPath", "")
            if full and os.path.exists(full):
                fn = os.path.basename(full)
                out[fn] = full
        return out

    def _cf_select_candidates(self, cand_dict):
        keys = list(cand_dict.keys())
        dlg = SingleSelectDialog(keys, title="请选择定稿文件", parent=None)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            # 假设 SingleSelectDialog 返回选中的 key
            return [cand_dict[k] for k in keys if k in dlg.get_selected_keys()]
        return []

    def _cf_build_ai_to_pdf_jobs(self, items):
        jobs = []
        for it in items:
            origin = it.get("designOriginPath", "")
            if not origin: continue
            folder = os.path.dirname(origin)
            base = os.path.splitext(os.path.basename(origin))[0]
            ai_path = os.path.join(folder, base + ".ai")
            if os.path.exists(ai_path):
                pdf_path = os.path.join(folder, base + ".pdf")
                jobs.append((ai_path, pdf_path))
        return jobs

    def _cf_build_update_fs_path_js(self, flow_id, dest_path):
        p = (dest_path or "").replace("\\", "\\\\")
        return f"if(window.updateFsPath) window.updateFsPath('{flow_id}', '{p}');"
