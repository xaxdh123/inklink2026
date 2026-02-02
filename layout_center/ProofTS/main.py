import sys

from PySide6.QtWidgets import QApplication
from comb.oneCom import OneComb
from manual.slowCom import SlowCom

if __name__ == "__main__":
    # log_file = open("output.log", "a", encoding="utf-8")
    # sys.stdout = log_file
    # sys.stderr = log_file
    app = QApplication(sys.argv)
    win1 = OneComb()
    win2 = SlowCom()
    win1.move(1200, 200)
    win1.show()
    win2.move(1200, 520)  # 设置 SlowCom 窗口偏移显示
    win2.show()
    sys.exit(app.exec())
