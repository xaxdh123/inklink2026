import sys

from PySide6.QtWidgets import QApplication

from comb.oneCom import OneComb

if __name__ == '__main__':
    app = QApplication(sys.argv)
    OneComb().show()
    sys.exit(app.exec())
