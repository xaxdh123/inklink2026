import traceback
from trayapp.tray_app import TrayApp
import sys
import qdarktheme

if __name__ == "__main__":
    try:
        tray = TrayApp(sys.argv)
        qdarktheme.setup_theme(theme="dark")
        sys.exit(tray.exec())
    except Exception:
        traceback.print_exc()
        pass
