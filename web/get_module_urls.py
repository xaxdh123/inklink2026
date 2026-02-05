from pathlib import Path
import debugpy
from PySide6.QtCore import QSize, QThread, Signal
from trayapp.cos_utils import get_app_version_info


class ModuleUrlsThreads(QThread):
    resp_name_urls = Signal(str, str)
    resp_resize = Signal(QSize)

    def __init__(self, name):
        super().__init__()
        self.app_dir = Path(__file__).parent.parent
        self.name = name

    def run(self, /) -> None:
        try:
            debugpy.debug_this_thread()
        except Exception:
            pass
        data = get_app_version_info(self.name)
        print(data["urls"])
        for k, v in data["urls"].items():
            if v:
                self.resp_name_urls.emit(k, v)
        if data["resize"]:
            w, h = data["resize"]
            self.resp_resize.emit(QSize(w, h))
