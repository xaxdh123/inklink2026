from importlib.resources import contents
import traceback
from PySide6 import QtWidgets, QtGui

from trayapp import constant
from trayapp.login_window import LoginWindow
from trayapp.floating_window import FloatingWindow
from trayapp.launcher_utils import launch_process
from pathlib import Path


class TrayApp(QtWidgets.QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)
        self.login_win = LoginWindow()
        self.login_win.login_success.connect(self.on_login_success)
        self.login_win.show()

        self.tray = None
        self.floating = None

    def create_tray(self, token):
        self.token = token
        if self.tray:
            return
        icon = QtGui.QIcon.fromTheme("applications-system")
        if icon.isNull():
            # fallback: create a simple pixmap
            pm = QtGui.QPixmap(64, 64)
            pm.fill(QtGui.QColor("#2d8cff"))
            icon = QtGui.QIcon(pm)

        tray = QtWidgets.QSystemTrayIcon(icon, self)
        menu = QtWidgets.QMenu()

        # Add a toggle action to show/hide the floating window
        show_float_act = menu.addAction("显示悬浮窗")
        show_float_act.setCheckable(True)
        show_float_act.setChecked(False)
        # keep reference so other handlers (e.g. tray double-click) can toggle it
        self.show_float_act = show_float_act
        for item in constant.COMPONENT_MAP:
            if "tray" not in item["show_type"]:
                continue
            name = item["name"]
            act = menu.addAction(name)

            def _launch_web_browser(checked, current_item=item):
                try:
                    app_dir = Path(__file__).parent.parent
                    exe_path = (
                        app_dir
                        / constant.DIR_BIN
                        / current_item["sub_dir"]
                        / current_item["exe"]
                    )
                    if exe_path.exists():
                        launch_process(str(exe_path), ["--user", self.token])
                    else:
                        QtWidgets.QMessageBox.warning(
                            None,
                            "文件未找到",
                            f"{name} exe未找到：\n{exe_path}\n\n请先构建exe文件。",
                        )
                except Exception as e:
                    traceback.print_exc()
                    QtWidgets.QMessageBox.critical(
                        None, "启动失败", f"无法启动exe：\n{str(e)}"
                    )

            act.triggered.connect(_launch_web_browser)

        menu.addSeparator()
        quit_act = menu.addAction("退出")
        quit_act.triggered.connect(self.quit)
        tray.setContextMenu(menu)
        tray.show()
        # connect tray activation (double-click) to toggle handler
        try:
            tray.activated.connect(self._on_tray_activated)
        except Exception:
            pass
        self.tray = tray

    def on_login_success(self, token: str):
        # Hide login, show floating window and create tray
        # store token for later use by tray handlers
        self.token = token
        self.login_win.hide()
        self.floating = FloatingWindow(token)
        # place at top-right corner
        screen = self.primaryScreen().availableGeometry()
        x = screen.right() - self.floating.width() - 20
        y = screen.top() + 40
        self.floating.move(x, y)
        self.floating.show()
        # Recreate tray but ensure the '显示悬浮窗' action toggles the current floating window
        self.create_tray(token)
        # find the show action and bind its behavior
        try:
            menu = self.tray.contextMenu()
            if menu:
                for act in menu.actions():
                    if act.text() == "显示悬浮窗":
                        # set initial checked state
                        act.setChecked(self.floating.isVisible())

                        def _on_toggle(checked, tok=token):
                            try:
                                if checked:
                                    if not self.floating:
                                        self.floating = FloatingWindow(tok)
                                        screen = (
                                            self.primaryScreen().availableGeometry()
                                        )
                                        x = screen.right() - self.floating.width() - 20
                                        y = screen.top() + 40
                                        self.floating.move(x, y)
                                    self.floating.show()
                                    self.floating.raise_()
                                else:
                                    if self.floating:
                                        self.floating.hide()
                            except Exception:
                                pass

                        act.toggled.connect(_on_toggle)
                        # keep tray action in sync when floating window is hidden/shown via its own controls
                        try:
                            # connect floating visibility changes to the action's checked state
                            if hasattr(self, "floating") and self.floating is not None:
                                self.floating.visibilityChanged.connect(
                                    lambda visible, a=act: a.setChecked(visible)
                                )
                        except Exception:
                            pass
                        break
        except Exception:
            pass

    def _on_tray_activated(self, reason):
        """Handle tray activation; double-click toggles the floating window."""
        try:
            if reason == QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick:
                # toggle floating window
                visible = False
                if (
                    self.floating
                    and getattr(self.floating, "isVisible", lambda: False)()
                ):
                    # currently visible -> hide
                    self.floating.hide()
                    visible = False
                else:
                    # show or create
                    if not self.floating:
                        self.floating = FloatingWindow(getattr(self, "token", ""))
                        screen = self.primaryScreen().availableGeometry()
                        x = screen.right() - self.floating.width() - 20
                        y = screen.top() + 40
                        self.floating.move(x, y)
                    self.floating.show()
                    self.floating.raise_()
                    visible = True

                # sync tray menu action
                try:
                    if (
                        hasattr(self, "show_float_act")
                        and self.show_float_act is not None
                    ):
                        self.show_float_act.setChecked(visible)
                except Exception:
                    pass
        except Exception:
            pass
