import sys
from pathlib import Path
from third_party.third_party import ThirdParty
from PySide6 import QtWidgets
import argparse
import importlib


# 确保能正确导入父目录的模块
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    # 1. 创建解析器对象
    parser = argparse.ArgumentParser(description="三方工具")

    # 2. 定义你想接收的参数
    # --user: 参数名
    # dest="user_name": 存储在代码里的变量名
    # help: 提示信息
    parser.add_argument("--user", dest="user_name", help="指定操作用户")
    parser.add_argument("--jump", dest="jump_page", help="指定跳转页面")
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
        pyqtdarktheme = importlib.import_module("pyqtdarktheme")
        pyqtdarktheme.setup_theme(app, theme="dark")
    except ImportError:
        pass
    except Exception:
        pass



    # Create and show browser widget
    window = ThirdParty(args.user_name)
    # 4. 使用参数
    if args.jump_page:
        print(f"当前跳转页面: {args.jump_page}")
        # 这里写你后续的业务逻辑，比如：if args.user_name == "admin": ...
        window.jump(args.jump_page)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
