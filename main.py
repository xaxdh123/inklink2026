from trayapp.tray_app import TrayApp
import sys


if __name__ == "__main__":
    app = TrayApp(sys.argv)
    try:
        import pyqtdarktheme

        pyqtdarktheme.setup_theme(app, theme="dark")
    except Exception:
        pass
    sys.exit(app.exec())
