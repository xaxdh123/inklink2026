# sub_module.py
import sys
import traceback
import qdarktheme
from PySide6 import QtWidgets

import customer_service
import floating_plugin
import system_setting
import third_party
import design_center


def run_customer():
    customer_service.main()


def run_float():
    floating_plugin.main()


def run_setting():
    system_setting.main()


def run_third():
    third_party.main()


def run_design():
    design_center.main()


MODES = {
    "customer": run_customer,
    "float": run_float,
    "setting": run_setting,
    "third": run_third,
    "design": run_design,
}


def main():
    app = QtWidgets.QApplication(sys.argv)
    qdarktheme.setup_theme(theme="dark")

    if len(sys.argv) < 2:
        print("Usage: exe_name [customer|float|setting|third|design]")
        return

    mode = sys.argv[1]
    MODES.get(mode, lambda: print(f"Unknown mode: {mode}"))()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
