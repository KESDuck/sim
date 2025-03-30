#!/usr/bin/env python3
from PyQt5.QtWidgets import QApplication
import sys
import yaml
from utils.logger_config import get_logger

from controllers.app_controller import AppController
from views.app_view import AppView

logger = get_logger("Main")

with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

if __name__ == "__main__":
    app = QApplication([])
    
    # Create controller first
    controller = AppController()
    
    # Create view and connect it to controller signals
    view = AppView(controller)
    
    # No longer need to set the view on the controller
    # The controller signals will notify the view of updates
    
    # Show the view
    view.show()
    
    # Run the application
    exit_code = app.exec_()
    
    # Cleanup resources
    controller.close()
    
    sys.exit(exit_code)
    