import sys
from PyQt5.QtWidgets import QApplication
from ui import VisionApp



if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VisionApp()
    win.show()
    sys.exit(app.exec_())
    