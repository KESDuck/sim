from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QGraphicsScene, QPushButton, QVBoxLayout, 
                           QHBoxLayout, QWidget, QComboBox, 
                           QStatusBar, QSpinBox, QLabel, QGroupBox)
from PyQt5.QtGui import QImage, QPixmap
import numpy as np

from utils.logger_config import get_logger
from views.graphics_view import GraphicsView

logger = get_logger("EngineerView")

class EngineerTabView(QWidget):
    """
    View component for the Engineer tab.
    Handles UI elements and interactions specific to the engineering interface.
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setup_ui()
        
        # Initialize with proper state
        self.view_state_changed(self.ui_view_states.currentText())
        
    def setup_ui(self):
        """Initialize the engineer tab interface."""
        # Create main layout as vertical container
        self.main_layout = QVBoxLayout(self)
        
        # Create horizontal layout for content (graphics + controls)
        self.layout = QHBoxLayout()
        self.main_layout.addLayout(self.layout)
        
        # Graphics view for displaying images (left side)
        self.graphics_view = GraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.scene)
        self.pixmap_item = None  # Placeholder for the image item
        self.layout.addWidget(self.graphics_view, 4)  # Give graphics view 4 parts of space

        # Controls panel (right side)
        self.controls_panel = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_panel)
        self.controls_panel.setFixedWidth(200)  # Set fixed width to make panel narrower
        self.layout.addWidget(self.controls_panel, 1)  # Give controls panel 1 part of space

        # Selection spinner
        self.selection_group = QWidget()
        self.selection_layout = QHBoxLayout(self.selection_group)
        self.selection_layout.addWidget(QLabel("Section:"))
        self.ui_selection_dropdown = QComboBox()
        self.ui_selection_dropdown.addItems(["1", "2", "3", "4", "5", "6", "7", "8", "9"])
        self.ui_selection_dropdown.setCurrentText("5")  # Set default to 5
        self.ui_selection_dropdown.currentTextChanged.connect(self.section_changed)
        self.selection_layout.addWidget(self.ui_selection_dropdown)
        self.controls_layout.addWidget(self.selection_group)

        # View state dropdown
        self.view_state_group = QWidget()
        self.view_state_layout = QHBoxLayout(self.view_state_group)
        self.ui_view_states = QComboBox()
        self.ui_view_states.addItems(["live", "paused orig", "paused thres", "paused contours"])
        self.ui_view_states.currentTextChanged.connect(self.view_state_changed)
        self.view_state_layout.addWidget(self.ui_view_states)
        self.controls_layout.addWidget(self.view_state_group)

        # Capture and process button
        self.ui_capture_button = QPushButton("Capture and Process", self)
        self.ui_capture_button.clicked.connect(self.handle_capture_button)
        self.controls_layout.addWidget(self.ui_capture_button)

        # Execute capture button
        self.ui_execute_capture_button = QPushButton("Execute Capture", self)
        self.ui_execute_capture_button.clicked.connect(self.handle_execute_capture_button)
        self.controls_layout.addWidget(self.ui_execute_capture_button)

        # Save frame button
        self.ui_save_frame_button = QPushButton("Save Frame", self)
        self.ui_save_frame_button.clicked.connect(self.controller.save_current_frame)
        self.controls_layout.addWidget(self.ui_save_frame_button)

        # Test button
        self.ui_test_button = QPushButton("Test", self)
        self.ui_test_button.clicked.connect(self.handle_test_button)
        self.controls_layout.addWidget(self.ui_test_button)

        # Insert button
        self.ui_insert_button = QPushButton("Insert", self)
        self.ui_insert_button.clicked.connect(self.handle_insert_button)
        self.controls_layout.addWidget(self.ui_insert_button)

        # Stop button
        self.ui_stop_button = QPushButton("Stop", self)
        self.ui_stop_button.clicked.connect(self.controller.stop_all)
        self.controls_layout.addWidget(self.ui_stop_button)

        # Speed control buttons
        self.speed_group = QGroupBox("Speed Control")
        self.speed_layout = QHBoxLayout(self.speed_group)
        self.speed_layout.setContentsMargins(2, 2, 2, 2)  # Reduce margins (left, top, right, bottom)
        self.speed_layout.setSpacing(2)  # Reduce spacing between buttons
        
        speeds = ["10%", "20%", "30%", "40%"]
        self.speed_buttons = []
        for speed in speeds:
            btn = QPushButton(speed)
            speed_value = int(speed.strip('%'))
            btn.clicked.connect(lambda checked, s=speed_value: self.set_speed(s))
            self.speed_layout.addWidget(btn)
            self.speed_buttons.append(btn)
            
        self.controls_layout.addWidget(self.speed_group)
        
        # Add spacer to push controls to the top
        self.controls_layout.addStretch()
        
        # Status bar layout
        self.status_layout = QHBoxLayout()
        self.main_layout.addLayout(self.status_layout)

        # Status bar for application messages
        self.status_bar = QStatusBar()
        self.status_layout.addWidget(self.status_bar)
        
        # Status bar for robot messages
        self.robot_status_bar = QStatusBar()
        self.status_layout.addWidget(self.robot_status_bar)
        
        # Connect to controller's robot status signal
        self.controller.robot_status_message.connect(self.update_robot_status)
    
    def set_speed(self, speed_percent):
        """Set the speed percentage."""
        logger.info(f"Setting speed to {speed_percent}%")
        # Call controller's method to set speed if implemented

        self.controller.change_speed(speed_percent)
    
    def update_display(self, frame, draw_cells=True):
        """Update the display with the provided frame."""
        if frame is None:
            return
            
        # Convert to QImage
        if len(frame.shape) == 3:
            h, w, c = frame.shape
            qimg = QImage(frame.data, w, h, w * c, QImage.Format_RGB888)
        else:
            h, w = frame.shape
            qimg = QImage(frame.data, w, h, w, QImage.Format_Grayscale8)
        
        # Update display
        pixmap = QPixmap.fromImage(qimg)
        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(pixmap)
        else:
            self.pixmap_item.setPixmap(pixmap)
        
        # Set scene rect to match image size
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        
        # Adjust minimum scale of graphics view
        self.graphics_view.set_min_scale(self.scene.sceneRect())
    
    def update_status(self, message):
        """Update the status bar with a message."""
        self.status_bar.showMessage(message)
    
    def update_robot_status(self, message):
        """Update the robot status bar with a message."""
        self.robot_status_bar.showMessage(message)
    
    def view_state_changed(self, state):
        """Handle view state change from UI"""
        # logger.info(f"View state: {state}")
        self.controller.set_view_state(state)
    
    def section_changed(self, section_id):
        """Handle section change from UI dropdown"""
        logger.info(f"Section changed to: {section_id}")
        self.controller.set_display_section(section_id)
    
    def update_section_display(self, section_id):
        """Update UI dropdown when section changes programmatically"""
        # Temporarily disconnect signal to avoid infinite loop
        self.ui_selection_dropdown.currentTextChanged.disconnect()
        self.ui_selection_dropdown.setCurrentText(section_id)
        # Reconnect signal
        self.ui_selection_dropdown.currentTextChanged.connect(self.section_changed)
    
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
    
    def handle_test_button(self):
        """Handle test button click by using the current section"""
        section_id = int(self.ui_selection_dropdown.currentText())
        self.controller.test_section(section_id)
    
    def handle_insert_button(self):
        """Handle insert button click by using the current section"""
        section_id = int(self.ui_selection_dropdown.currentText())
        self.controller.insert_section(section_id)
    
    def handle_capture_button(self):
        """Handle capture button click by using the current section"""
        section_id = int(self.ui_selection_dropdown.currentText())
        self.controller.capture_section(section_id)
    
    def handle_execute_capture_button(self):
        """Handle execute capture button click"""
        self.controller.execute_capture(no_robot=True) 