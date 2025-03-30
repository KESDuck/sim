from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QSpinBox, QComboBox, QMenuBar, QAction, QTabWidget, QLabel
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
        self.setup_ui()

        self.disp_frame = None

        # Timer for updating frames
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_image)

        self.screen_timer = QTimer()
        self.screen_timer.timeout.connect(self.update_screen)

        # Connect signals from controller
        self.controller.cell_index_changed.connect(self.ui_cell_spinbox.setValue)
        self.controller.cell_max_changed.connect(self.ui_cell_spinbox.setMaximum)
        
        # Handle Ctrl+C to safe close app
        signal.signal(signal.SIGINT, lambda signal_received, frame: self.close())
        
        self.start_timers()
        
        # pause state right after starting
        self.ui_view_states.setCurrentIndex(1)
        self.capture_image()
        
        logger.info("Press R Key to note current cross position")
        
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

        ##### Cell index spinbox #####
        self.ui_cell_spinbox = QSpinBox() # stores the selected cell index
        self.ui_cell_spinbox.setRange(-1, 0)
        self.ui_cell_spinbox.valueChanged.connect(self.on_cell_spinbox_changed)

        ##### UI States #####
        self.ui_view_states = QComboBox()
        self.ui_view_states.addItems(["live", "paused orig", "paused thres", "paused contours"])
        self.ui_view_states.currentTextChanged.connect(self.view_state_changed)

        ##### Control buttons #####
        self.ui_capture_button = QPushButton("Process", self)
        self.ui_capture_button.clicked.connect(self.capture_image)

        self.ui_save_frame_button = QPushButton("Save Frame", self)
        self.ui_save_frame_button.clicked.connect(self.on_save_frame)
        
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

        # Create User tab
        user_tab = QWidget()
        user_layout = QVBoxLayout(user_tab)
        # Add placeholder for user interface
        user_layout.addWidget(QLabel("User Interface Coming Soon..."))
        
        # Add tabs to tab widget
        self.tabs.addTab(engineer_tab, "Engineer")
        self.tabs.addTab(user_tab, "User")
        
        # Set the main layout
        self.setLayout(self.main_layout)

    def view_state_changed(self, state):
        logger.info(f"View state: {state}")
        self.start_timers()

    def start_timers(self):
        """Start the timers based on the current state."""
        self.screen_timer.start(100)  # overlay remains active in paused states

        if self.ui_view_states.currentText() == "live":
            self.capture_timer.start(1000)  # live updates
        else:
            self.capture_timer.stop() # use stored image to display

    def on_cell_spinbox_changed(self, value):
        """Handle cell index change from UI"""
        self.controller.set_cell_index(value)

    def toggle_batch_insert(self):
        """Toggle batch insertion mode"""
        self.controller.toggle_pause_insert()
        button_text = "Resume Batch" if self.controller.pause_insert else "Pause Batch"
        self.ui_insert_batch_button.setText(button_text)

    def capture_image(self):
        """Trigger image capture and processing"""
        cur_state = self.ui_view_states.currentText()

        # capture image, process if needed
        if cur_state == "live":
            self.controller.live_capture()
        else:
            if not self.controller.capture_and_process():
                logger.error("Process image failure")

    def update_screen(self):
        """Update the display based on current view state"""
        if not hasattr(self, 'ui_view_states') or self.ui_view_states is None:
            logger.error("UI components have been deleted.")
            return

        cur_state = self.ui_view_states.currentText()

        # Get frame from controller based on view state
        self.disp_frame = self.controller.get_frame_for_display(cur_state)

        if self.disp_frame is None:
            # warning if there is no processed screen
            if cur_state == "live":
                logger.warning("Skipped frame")
            else: # processed state
                logger.warning("Nothing to display, please capture and process first")
            return
        else:
            # Make a copy to avoid modifying original frame
            self.disp_frame = self.disp_frame.copy()

        if cur_state != "live": # processed state
            # Draw points on processed frames
            self.disp_frame = draw_points(
                self.disp_frame, 
                self.controller.cells_img_xy, 
                self.controller.cell_index, 
                size=10
            )

        # Draw cross at cursor position
        cross_x, cross_y = self.controller.cross_cam_xy
        self.disp_frame = draw_cross(self.disp_frame, cross_x, cross_y)

        # Convert to QImage for display
        if len(self.disp_frame.shape) == 3:
            h, w, c = self.disp_frame.shape
            qimg = QImage(self.disp_frame.data, w, h, w * c, QImage.Format_RGB888) 
        else:
            h, w = self.disp_frame.shape
            qimg = QImage(self.disp_frame.data, w, h, w, QImage.Format_Grayscale8)

        # Update display
        pixmap = QPixmap.fromImage(qimg)
        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(pixmap)
        else:
            self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(0, 0, w, h)

    def on_save_frame(self):
        """Save current frame"""
        self.controller.save_current_frame()

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        key = event.key()
        
        # Handle cursor movement with arrow keys
        if key == Qt.Key_Left:
            self.controller.shift_cross(dx=-10)
        elif key == Qt.Key_Right:
            self.controller.shift_cross(dx=10)
        elif key == Qt.Key_Up:
            self.controller.shift_cross(dy=-10)
        elif key == Qt.Key_Down:
            self.controller.shift_cross(dy=10)
        # Print current position
        elif key == Qt.Key_R:
            self.controller.print_cross_position()
        # Pass other keys to parent
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle application closing"""
        self.controller.close()
        super().closeEvent(event) 