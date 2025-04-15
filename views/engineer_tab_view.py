from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QGraphicsScene, QPushButton, QVBoxLayout, 
                           QHBoxLayout, QWidget, QComboBox, 
                           QStatusBar)
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
        
        # # Initialize with proper state
        # self.view_state_changed(self.ui_view_states.currentText())
        
    def setup_ui(self):
        """Initialize the engineer tab interface."""
        # Create main layout
        self.layout = QVBoxLayout(self)
        
        # Graphics view for displaying images
        self.graphics_view = GraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.scene)
        self.pixmap_item = None  # Placeholder for the image item
        self.layout.addWidget(self.graphics_view)

        # Button layout for engineer controls
        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)

        ##### UI States ####
        self.ui_view_states = QComboBox()
        self.ui_view_states.addItems(["live", "paused orig", "paused thres", "paused contours"])
        self.ui_view_states.currentTextChanged.connect(self.view_state_changed)
        self.ui_view_states.setCurrentIndex(1)  # "paused orig" is index 1

        ##### Control buttons ####

        self.ui_reconnect_button = QPushButton("Reconnect Camera", self)
        self.ui_reconnect_button.clicked.connect(self.controller.reconnect_camera)

        self.ui_capture_button = QPushButton("Process Image", self)
        self.ui_capture_button.clicked.connect(self.controller.update_frame)

        self.ui_save_frame_button = QPushButton("Save Frame", self)
        self.ui_save_frame_button.clicked.connect(self.controller.save_current_frame)
        
        self.ui_move_to_capture = QPushButton("Capture 1 Only", self)
        self.ui_move_to_capture.clicked.connect(lambda: self.controller.process_section(1, capture_only=True))

        self.ui_move_to_capture_tmp = QPushButton("Capture 2 Only", self)
        self.ui_move_to_capture_tmp.clicked.connect(lambda: self.controller.process_section(2, capture_only=True))

        self.ui_process_section = QPushButton("Process Section 1", self)
        self.ui_process_section.clicked.connect(lambda: self.controller.process_section(1))

        self.ui_where_button = QPushButton("Where", self)
        # TODO

        # Add engineer mode widgets
        self.button_layout.addWidget(self.ui_reconnect_button)
        self.button_layout.addWidget(self.ui_capture_button)
        self.button_layout.addWidget(self.ui_view_states)
        self.button_layout.addWidget(self.ui_save_frame_button)
        self.button_layout.addWidget(self.ui_move_to_capture)
        self.button_layout.addWidget(self.ui_move_to_capture_tmp)
        self.button_layout.addWidget(self.ui_process_section)
        self.button_layout.addWidget(self.ui_where_button)
        
        # Status bar layout
        self.status_layout = QHBoxLayout()
        self.layout.addLayout(self.status_layout)

        # Status bar for application messages
        self.status_bar = QStatusBar()
        self.status_layout.addWidget(self.status_bar)
        
        # Status bar for robot messages
        self.robot_status_bar = QStatusBar()
        self.status_layout.addWidget(self.robot_status_bar)
        
        # Connect to controller's robot status signal
        self.controller.robot_status_message.connect(self.update_robot_status)
    
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