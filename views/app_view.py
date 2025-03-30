from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QSpinBox, QComboBox, QMenuBar, QAction, QTabWidget, QLabel, QStatusBar
from PyQt5.QtGui import QImage, QPixmap, QBrush, QColor
import signal
import numpy as np

from utils.logger_config import get_logger
from views.graphics_view import GraphicsView
from utils.tools import draw_cross, save_image, draw_points

# Configure the logger
logger = get_logger("View")

class AppView(QWidget):
    """
    View component that handles UI presentation.
    Manages UI elements and user interactions.
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        # Setup UI components
        self.setup_ui()
        
        # Connect signals from controller to view methods
        self.controller.frame_updated.connect(self.update_display)
        self.controller.status_message.connect(self.update_status)
        self.controller.cell_index_changed.connect(self.ui_cell_spinbox.setValue)
        self.controller.cell_max_changed.connect(self.ui_cell_spinbox.setMaximum)
        
        # Handle Ctrl+C to safely close app
        signal.signal(signal.SIGINT, lambda signal_received, frame: self.close())
        
        # Set initial view state (controller already defaults to "paused orig")
        self.ui_view_states.setCurrentIndex(1)  # "paused orig" is index 1
        
        # Initialize with proper state
        self.view_state_changed(self.ui_view_states.currentText())

    def setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Image Viewer with Robot Control")
        self.setGeometry(50, 50, 1000, 700)

        # Create main layout
        self.main_layout = QVBoxLayout()
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # Create Engineer tab
        engineer_tab = QWidget()
        engineer_layout = QVBoxLayout(engineer_tab)
        
        # Graphics view for displaying images
        self.graphics_view = GraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.scene)
        self.pixmap_item = None  # Placeholder for the image item
        engineer_layout.addWidget(self.graphics_view)

        # Button layout for engineer controls
        self.button_layout = QHBoxLayout()
        engineer_layout.addLayout(self.button_layout)

        ##### Cell index spinbox ####
        self.ui_cell_spinbox = QSpinBox()  # stores the selected cell index
        self.ui_cell_spinbox.setRange(-1, 0)
        self.ui_cell_spinbox.valueChanged.connect(self.on_cell_spinbox_changed)

        ##### UI States ####
        self.ui_view_states = QComboBox()
        self.ui_view_states.addItems(["live", "paused orig", "paused thres", "paused contours"])
        self.ui_view_states.currentTextChanged.connect(self.view_state_changed)

        ##### Control buttons ####
        self.ui_capture_button = QPushButton("Process", self)
        self.ui_capture_button.clicked.connect(self.controller.update_frame)

        self.ui_save_frame_button = QPushButton("Save Frame", self)
        self.ui_save_frame_button.clicked.connect(self.controller.save_current_frame)
        
        self.ui_move_to_capture = QPushButton("Go Capture", self)
        self.ui_move_to_capture.clicked.connect(self.controller.position_and_capture)

        self.ui_insert_single_button = QPushButton("Insert Single", self)
        self.ui_insert_single_button.clicked.connect(lambda: self.controller.cell_action(action="insert"))

        self.ui_insert_batch_button = QPushButton("Insert Batch", self)
        self.ui_insert_batch_button.clicked.connect(self.toggle_batch_insert)

        self.ui_echo_button = QPushButton("Echo", self)
        self.ui_echo_button.clicked.connect(self.controller.echo_test)

        # Add engineer mode widgets
        self.button_layout.addWidget(self.ui_capture_button)
        self.button_layout.addWidget(self.ui_view_states)
        self.button_layout.addWidget(self.ui_save_frame_button)
        self.button_layout.addWidget(self.ui_cell_spinbox)
        self.button_layout.addWidget(self.ui_move_to_capture)
        self.button_layout.addWidget(self.ui_insert_single_button)
        self.button_layout.addWidget(self.ui_insert_batch_button)
        self.button_layout.addWidget(self.ui_echo_button)

        # Status bar for messages
        self.status_bar = QStatusBar()
        engineer_layout.addWidget(self.status_bar)
        
        # Create User tab
        user_tab = QWidget()
        user_layout = QVBoxLayout(user_tab)
        user_layout.addWidget(QLabel("User Interface Coming Soon..."))
        
        # Add tabs to tab widget
        self.tabs.addTab(engineer_tab, "Engineer")
        self.tabs.addTab(user_tab, "User")
        
        # Set the main layout
        self.setLayout(self.main_layout)

    def update_display(self, frame):
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

    def on_cell_spinbox_changed(self, value):
        """Handle cell index change from UI"""
        self.controller.set_cell_index(value)

    def toggle_batch_insert(self):
        """Toggle batch insertion mode"""
        self.controller.toggle_pause_insert()
        button_text = "Resume Batch" if self.controller.pause_insert else "Pause Batch"
        self.ui_insert_batch_button.setText(button_text)

    def view_state_changed(self, state):
        """Handle view state change from UI"""
        logger.info(f"View state: {state}")
        self.controller.set_view_state(state)

    def update_cross_position(self, scene_pos):
        """
        Update the cross position when user clicks on the image.
        Called by GraphicsView when user clicks on the image.
        """
        # Convert QPointF to integer coordinates
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        
        # Update cross position in controller
        self.controller.set_cross_position(x, y)

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        key = event.key()
        if key == Qt.Key_Left:
            self.controller.shift_cross(dx=-1)
        elif key == Qt.Key_Right:
            self.controller.shift_cross(dx=1)
        elif key == Qt.Key_Up:
            self.controller.shift_cross(dy=-1)
        elif key == Qt.Key_Down:
            self.controller.shift_cross(dy=1)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle application closing"""
        self.controller.close()
        super().closeEvent(event) 