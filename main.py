#!/usr/bin/env python3
import os
import sys
import yaml
from PyQt5.QtWidgets import QApplication
from utils.logger_config import get_logger

from controllers.app_controller import AppController
from views.app_view import AppView

logger = get_logger("Main")

with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

if __name__ == "__main__":
    app = QApplication([])
    app.setStyle("Fusion")  # Match A1 demo styling
    
    # Force dark theme by setting palette (most reliable way to ignore system theme)
    # This overrides any system theme influence
    from PyQt5.QtGui import QPalette, QColor
    palette = QPalette()
    # Set all color roles to dark theme colors
    palette.setColor(QPalette.Window, QColor(53, 53, 53))           # Dark gray background
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))   # White text
    palette.setColor(QPalette.Base, QColor(35, 35, 35))            # Darker gray for input fields
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))  # Alternate dark gray
    palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))        # Black tooltip background
    palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255)) # White tooltip text
    palette.setColor(QPalette.Text, QColor(255, 255, 255))        # White text
    palette.setColor(QPalette.Button, QColor(53, 53, 53))          # Dark gray buttons
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))  # White button text
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))      # Red for bright text
    palette.setColor(QPalette.Link, QColor(42, 130, 218))          # Blue links
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))     # Blue highlight
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255)) # White highlighted text
    app.setPalette(palette)
    
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
    