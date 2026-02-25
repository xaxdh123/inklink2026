# sub_module.py
import logging
import sys
import traceback
import qdarktheme
from PySide6 import QtWidgets

import audit_center
import customer_service
import floating_plugin
import layout_center
import system_setting
import third_party
import design_center

MODES = {
    "CustomerService": customer_service.main,
    "FloatingPlugin": floating_plugin.main,
    "SystemSetting": system_setting.main,
    "ThirdParty": third_party.main,
    "DesignCenter": design_center.main,
    "AuditCenter": audit_center.main,
    "LayoutCenter": layout_center.main,
}


# 2. 核心：接管全局异常（这是防止闪退找不到原因的关键）
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    LOG_FILE = "except_log.txt"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),  # 写入文件
            logging.StreamHandler(sys.stdout),  # 同时输出到控制台
        ],
    )
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.critical(None, "程序崩溃", f"详细信息已写入 {LOG_FILE}")


def main():
    sys.excepthook = handle_exception
    app = QtWidgets.QApplication(sys.argv)
    qdarktheme.setup_theme(theme="dark")

    if len(sys.argv) < 2:
        print("Usage: exe_name [customer|float|setting|third|design|audit|layout]")
        return

    mode = sys.argv[1]
    MODES.get(mode, lambda: print(f"Unknown mode: {mode}"))()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
