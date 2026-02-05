"""
三方应用
基于 BrowserWidget 创建独立的客服中心窗口
"""

import sys
import qdarktheme
from pathlib import Path
from PySide6 import QtWidgets
from third_party.third_party import ThirdParty

# 确保能正确导入父目录的模块
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    window = ThirdParty()
    window.show()


if __name__ == "__main__":
    try:
        # Apply dark theme if available
        app = QtWidgets.QApplication(sys.argv)
        qdarktheme.setup_theme(theme="dark")
        main()
        sys.exit(app.exec())
    except Exception:
        pass
