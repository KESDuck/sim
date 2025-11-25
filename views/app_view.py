from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QWidget, QTabWidget, 
                             QSplitter, QFrame, QLabel)
from PyQt5.QtGui import QFont
import signal

from utils.logger_config import get_logger
from views.engineer_tab_view import EngineerTabView
from views.user_tab_view import UserTabView
from views.graphics_view import GraphicsView

# Configure the logger
logger = get_logger("View")

class AppView(QWidget):
    """
    Main view component that handles UI presentation.
    Manages tabs and coordinates between different view components.
    Uses A1 layout: splitter with left panel (tabs) and right panel (vision + status).
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        # Touch-optimized font sizes
        self.font_large = QFont()
        self.font_large.setPointSize(24)
        self.font_medium = QFont()
        self.font_medium.setPointSize(18)
        self.font_normal = QFont()
        self.font_normal.setPointSize(14)
        
        # Setup UI components
        self.setup_ui()
        
        # Connect signals from controller to view methods
        self.controller.frame_updated.connect(self.engineer_tab.update_display)
        self.controller.status_message.connect(self.update_status_message)
        self.controller.section_changed.connect(self.engineer_tab.update_section_display)
        self.controller.robot_status_message.connect(self.update_robot_status)
        self.controller.position_updated.connect(self.engineer_tab.update_position_info)
        self.controller.state_mode_updated.connect(self.update_state_mode)
        
        # Handle Ctrl+C to safely close app
        signal.signal(signal.SIGINT, lambda signal_received, frame: self.close())

    def setup_ui(self):
        """Initialize the user interface."""
        from PyQt5.QtWidgets import QGraphicsScene
        
        self.setWindowTitle("Vision Control Interface")
        self.setGeometry(100, 100, 1600, 1000)

        # Create shared scene for vision display (before creating tabs)
        self.vision_scene = QGraphicsScene(self)

        # Create main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create splitter for left/right division
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left side: Tab widget
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right side: Vision display + status
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions (40% left, 60% right)
        splitter.setSizes([500, 1100])
        
        # Connect engineer tab's scene to shared vision scene
        self.engineer_tab.scene = self.vision_scene
    
    def create_left_panel(self):
        """Create left panel with tabs"""
        tab_widget = QTabWidget()
        tab_widget.setFont(self.font_medium)
        self.tab_widget = tab_widget
        
        # Create tabs (pass app_view reference to engineer_tab for vision_view access)
        self.engineer_tab = EngineerTabView(self.controller, self.font_medium, self.font_normal, app_view=self)
        self.user_tab = UserTabView(self.controller, self.font_medium, self.font_normal)
        
        tab_widget.addTab(self.user_tab, "Operator")
        tab_widget.addTab(self.engineer_tab, "Engineer")
        
        # Connect tab change signal
        tab_widget.currentChanged.connect(self.on_tab_changed)
        
        return tab_widget
    
    def create_right_panel(self):
        """Create right panel with vision display and status"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Vision display - shared between tabs (uses self.vision_scene created in setup_ui)
        self.vision_view = GraphicsView(self)
        self.vision_view.main_window = self  # Store reference for click handling
        self.vision_view.setScene(self.vision_scene)
        layout.addWidget(self.vision_view)
        
        # Status strip
        status_strip = QFrame()
        status_strip.setFrameShape(QFrame.StyledPanel)
        status_strip.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        status_strip.setMinimumHeight(80)
        status_layout = QVBoxLayout(status_strip)
        status_layout.setContentsMargins(15, 10, 15, 10)
        status_layout.setSpacing(5)
        
        # Status row
        status_row = QHBoxLayout()
        self.current_status = QLabel("Status: Ready")
        self.current_status.setFont(self.font_medium)
        self.state_mode_label = QLabel("State: IDLE | Mode: IDLE MODE")
        self.state_mode_label.setFont(self.font_medium)
        status_row.addWidget(self.current_status)
        status_row.addStretch()
        status_row.addWidget(self.state_mode_label)
        status_layout.addLayout(status_row)
        
        # Action row
        action_row = QHBoxLayout()
        self.robot_status = QLabel("Robot: Idle")
        self.robot_status.setFont(self.font_medium)
        self.vision_status = QLabel("Vision: Ready")
        self.vision_status.setFont(self.font_medium)
        self.general_status = QLabel("General: OK")
        self.general_status.setFont(self.font_medium)
        
        action_row.addWidget(self.robot_status)
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        action_row.addWidget(separator1)
        action_row.addWidget(self.vision_status)
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        action_row.addWidget(separator2)
        action_row.addWidget(self.general_status)
        action_row.addStretch()
        
        status_layout.addLayout(action_row)
        layout.addWidget(status_strip)
        
        return panel

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
    
    def update_robot_status(self, message):
        """Update the robot status label"""
        self.robot_status.setText(f"Robot: {message}")
    
    def update_status_message(self, message):
        """Update general status from controller status messages"""
        self.general_status.setText(f"General: {message}")
    
    def update_state_mode(self, state, mode):
        """Update state and mode labels"""
        self.state_mode_label.setText(f"State: {state} | Mode: {mode}")
        # Update status based on state
        if state == "IDLE":
            self.current_status.setText("Status: Ready")
        elif state in ["INSERTING", "TESTING", "QUEUEING"]:
            self.current_status.setText(f"Status: {state}")
        else:
            self.current_status.setText(f"Status: {state}")
    
    def update_status_labels(self, status=None, state=None, mode=None, vision=None, general=None):
        """Update status labels"""
        if status:
            self.current_status.setText(f"Status: {status}")
        if state and mode:
            self.state_mode_label.setText(f"State: {state} | Mode: {mode}")
        if vision:
            self.vision_status.setText(f"Vision: {vision}")
        if general:
            self.general_status.setText(f"General: {general}")

    def keyPressEvent(self, event):
        """Handle keyboard events and pass to active tab if needed"""
        # Force exit with Ctrl+Q
        if event.key() == Qt.Key_Q and event.modifiers() & Qt.ControlModifier:
            logger.warning("Emergency application exit triggered with Ctrl+Q")
            import os
            os._exit(0)  # Force quit the application
            
        # Only handle keys in Engineer tab (index 1)
        if self.tab_widget.currentIndex() == 1:  # Engineer tab
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
        tab_name = self.tab_widget.tabText(index)
        self.controller.set_current_tab(tab_name)
        
        # Update vision view behavior based on tab
        if index == 1:  # Engineer tab
            self.vision_view.set_pan_enabled(True)
            self.vision_view.set_zoom_enabled(True)
            self.vision_view.set_click_enabled(True)
        else:  # Operator tab
            self.vision_view.set_pan_enabled(False)
            self.vision_view.set_zoom_enabled(False)
            self.vision_view.set_click_enabled(False)
            self.vision_view.reset_view() 
        