import sys
from PyQt5.QtWidgets import QApplication
from app_ui import AppUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AppUI()
    win.show()
    sys.exit(app.exec_())
    