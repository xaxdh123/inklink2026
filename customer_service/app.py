"""
客服中心应用
基于 BrowserWidget 创建独立的客服中心窗口
"""

import sys
import qdarktheme
from pathlib import Path
from customer_service.customer_service import CustomerService

from PySide6 import QtWidgets

# 确保能正确导入父目录的模块
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    window = CustomerService()
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
