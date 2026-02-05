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
    "CustomerService": customer_service.main,
    "FloatingPlugin": floating_plugin.main,
    "SystemSetting": system_setting.main,
    "ThirdParty": third_party.main,
    "DesignCenter": design_center.main,
    "AuditCenter": audit_center.main,
    "LayoutCenter": layout_center.main,
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
