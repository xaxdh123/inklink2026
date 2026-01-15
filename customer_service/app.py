"""
客服中心应用
基于 BrowserWidget 创建独立的客服中心窗口
"""

import sys
import os
from pathlib import Path

# 确保能正确导入父目录的模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6 import QtWidgets
from web.web_browser_widget import BrowserWidget


def main():
    app = QtWidgets.QApplication(sys.argv)

    # Apply dark theme if available
    try:
        import pyqtdarktheme

        pyqtdarktheme.setup_theme(app, theme="dark")
    except Exception:
        pass

    # Define presets - 使用 web_browser_widget.py 中的配置
    presets = {
        "Google": "https://www.google.com",
        "Wikipedia": "https://www.wikipedia.org",
        "Python": "https://www.python.org",
        "ChatBox": "https://web.chatboxai.app",
    }

    # Create and show browser widget
    window = BrowserWidget(presets, profile_name="customer_service")
    window.setWindowTitle("客服中心")
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
