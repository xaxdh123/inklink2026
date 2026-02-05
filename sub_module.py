# sub_module.py
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
    "customer": customer_service.main,
    "float": floating_plugin.main,
    "setting": system_setting.main,
    "third": third_party.main,
    "design": design_center.main,
    "audit": audit_center.main,
    "layout": layout_center.main,
}


def main():
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
