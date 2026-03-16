from PySide6.QtCore import QThread, Signal
import os
import shutil
import traceback

class DesignTaskWorker(QThread):
    """
    后台任务工作线程，处理 IO 密集型操作，避免主线程卡顿。
    """
    finished = Signal(dict)
    error = Signal(str, str)
    progress = Signal(str)

    def __init__(self, task_type, params):
        super().__init__()
        self.task_type = task_type
        self.params = params

    def run(self):
        try:
            if self.task_type == "export_pdf_and_upload":
                self._handle_export_and_upload()
            elif self.task_type == "scan_files":
                self._handle_scan_files()
        except Exception as e:
            self.error.emit(f"任务 {self.task_type} 失败", str(e))
            traceback.print_exc()

    def _handle_export_and_upload(self):
        jobs = self.params.get("jobs", [])
        upload_params = self.params.get("upload_params", {})
        
        # 1. 执行 PDF 导出
        for ai_path, pdf_path in jobs:
            self.progress.emit(f"正在导出 PDF: {os.path.basename(ai_path)}")
            self._export_ai_to_pdf(ai_path, pdf_path)
        
        # 2. 执行上传/复制逻辑
        self.progress.emit("正在同步定稿文件...")
        self._upload_files(upload_params)
        
        self.finished.emit({"type": "export_pdf_and_upload", "status": "success"})

    def _export_ai_to_pdf(self, ai_path, pdf_path):
        # 仅在 Windows 下有效
        if os.name != 'nt':
            return
        try:
            import pythoncom
            import win32com.client
            from win32com.client import gencache
            pythoncom.CoInitialize()
            gencache.Rebuild()
            ai = win32com.client.Dispatch("Illustrator.Application")
            doc = ai.Open(os.path.abspath(ai_path))
            pdf_opt = win32com.client.Dispatch("Illustrator.PDFSaveOptions")
            doc.SaveAs(os.path.abspath(pdf_path), pdf_opt)
            doc.Close(2)
        finally:
            if os.name == 'nt':
                pythoncom.CoUninitialize()

    def _upload_files(self, p):
        src_paths = p.get("src_paths", [])
        dpath = p.get("dpath", "")
        flow_id = p.get("flow_id", "")
        remove_set = p.get("remove_set", set())
        
        os.makedirs(dpath, exist_ok=True)
        last_dest = ""
        for src in src_paths:
            dest = os.path.join(dpath, os.path.basename(src))
            shutil.copy(src, dest)
            if src in remove_set:
                try: os.remove(src)
                except: pass
            last_dest = dest
        
        if last_dest:
            self.finished.emit({"type": "update_fs_path", "flow_id": flow_id, "dest_path": last_dest})

    def _handle_scan_files(self):
        # 模拟耗时的文件扫描逻辑
        path = self.params.get("path", "")
        # 实际扫描逻辑...
        self.finished.emit({"type": "scan_files", "result": []})
