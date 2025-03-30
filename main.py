import sys
from PyQt5.QtWidgets import QApplication
from views.app_view import AppView
from controllers.app_controller import AppController

if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = AppController()
    view = AppView(controller)
    view.show()
    sys.exit(app.exec_())
    