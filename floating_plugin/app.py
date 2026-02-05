import sys
from pathlib import Path

from floating_plugin.floating_plugin import FP
from PySide6 import QtWidgets
import argparse

# 确保能正确导入父目录的模块
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(description="浮窗插件")
    parser.add_argument("--user", dest="user_name", help="指定操作用户")
    args = parser.parse_args()
    if args.user_name:
        print(f"当前登录用户token: {args.user_name}")
    else:
        print("未检测到 --user 参数")
    window = FP(args.user_name)
    window.show()


if __name__ == "__main__":
    try:
        # Apply dark theme if available
        import pyqtdarktheme

        app = QtWidgets.QApplication(sys.argv)
        pyqtdarktheme.setup_theme(app, theme="dark")
        main()
        sys.exit(app.exec())
    except Exception:
        pass
