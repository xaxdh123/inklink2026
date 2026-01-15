import sys
from pathlib import Path

from floating_plugin.floating_plugin import FP
from PySide6 import QtWidgets
import argparse

# 确保能正确导入父目录的模块
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    # 1. 创建解析器对象
    parser = argparse.ArgumentParser(description="浮窗插件")

    # 2. 定义你想接收的参数
    # --user: 参数名
    # dest="user_name": 存储在代码里的变量名
    # help: 提示信息
    parser.add_argument("--user", dest="user_name", help="指定操作用户")

    # 3. 解析参数
    args = parser.parse_args()

    # 4. 使用参数
    if args.user_name:
        print(f"当前登录用户token: {args.user_name}")
        # 这里写你后续的业务逻辑，比如：if args.user_name == "admin": ...
    else:
        print("未检测到 --user 参数")

    app = QtWidgets.QApplication(sys.argv)

    # Apply dark theme if available
    try:
        import pyqtdarktheme

        pyqtdarktheme.setup_theme(app, theme="dark")
    except Exception:
        pass

    # Define presets - 使用 web_browser_widget.py 中的配置

    # Create and show browser widget
    window = FP(args.user_name)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
