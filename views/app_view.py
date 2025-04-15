from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QTabWidget
import signal

from utils.logger_config import get_logger
from views.engineer_tab_view import EngineerTabView
from views.user_tab_view import UserTabView

# Configure the logger
logger = get_logger("View")

class AppView(QWidget):
    """
    Main view component that handles UI presentation.
    Manages tabs and coordinates between different view components.
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        # Setup UI components
        self.setup_ui()
        
        # Connect signals from controller to view methods
        self.controller.frame_updated.connect(self.engineer_tab.update_display)
        self.controller.status_message.connect(self.engineer_tab.update_status)
        
        # Handle Ctrl+C to safely close app
        signal.signal(signal.SIGINT, lambda signal_received, frame: self.close())

    def setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Image Viewer with Robot Control")
        self.setGeometry(50, 50, 1000, 700)

        # Create main layout
        self.main_layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.main_layout.addWidget(self.tabs)
        
        # Create Engineer tab
        self.engineer_tab = EngineerTabView(self.controller)
        
        # Create User tab
        self.user_tab = UserTabView(self.controller)
        
        # Add tabs to tab widget
        self.tabs.addTab(self.engineer_tab, "Engineer")
        self.tabs.addTab(self.user_tab, "User")
        
        # Set the main layout
        self.setLayout(self.main_layout)

    def update_cross_position(self, scene_pos):
        """
        Update the cross position when user clicks on the image.
        Called by GraphicsView when user clicks on the image.
        """
        # Convert QPointF to integer coordinates
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        
        # Update cross position in controller using shift_cross with absolute positioning
        self.controller.shift_cross(x, y)

    def keyPressEvent(self, event):
        """Handle keyboard events and pass to active tab if needed"""
        # Force exit with Ctrl+Q
        if event.key() == Qt.Key_Q and event.modifiers() & Qt.ControlModifier:
            logger.warning("Emergency application exit triggered with Ctrl+Q")
            import os
            os._exit(0)  # Force quit the application
            
        active_tab = self.tabs.currentWidget()
        
        if self.tabs.currentIndex() == 0:  # Engineer tab
            key = event.key()
            # Check if shift is pressed
            shift_pressed = event.modifiers() & Qt.ShiftModifier
            
            if key == Qt.Key_Left:
                self.controller.shift_cross(dx=-0.5 if shift_pressed else -1)
            elif key == Qt.Key_Right:
                self.controller.shift_cross(dx=0.5 if shift_pressed else 1)
            elif key == Qt.Key_Up:
                self.controller.shift_cross(dy=-0.5 if shift_pressed else -1)
            elif key == Qt.Key_Down:
                self.controller.shift_cross(dy=0.5 if shift_pressed else 1)
            elif key == Qt.Key_R:
                self.controller.handle_r_key()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle application closing"""
        self.controller.close()
        super().closeEvent(event)

    def on_tab_changed(self, index):
        """Handle tab change events"""
        tab_name = self.tabs.tabText(index)
        # logger.info(f"Tab changed to: {tab_name}")
        self.controller.set_current_tab(tab_name) 
        