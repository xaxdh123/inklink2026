from pathlib import Path
from PySide6.QtCore import QSize, QThread, Signal
from trayapp.cos_utils import get_app_version_info

class ModuleUrlsThreads(QThread):
    resp_name_urls = Signal(str, str)
    resp_resize = Signal(QSize)
    def __init__(self, name):
        super().__init__()
        self.app_dir = Path(__file__).parent.parent
        self.name = name
    def run(self) -> None:
        # 移除 debugpy 尝试，减少初始化延迟
        data = get_app_version_info(self.name)
        if not data:
            return
        urls = data.get("urls", {})
        for k, v in urls.items():
            if v:
                self.resp_name_urls.emit(k, v)
        resize = data.get("resize")
        if resize:
            w, h = resize
            self.resp_resize.emit(QSize(w, h))
