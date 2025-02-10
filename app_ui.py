from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QSpinBox, QComboBox
from PyQt5.QtGui import QImage, QPixmap, QBrush, QColor
import signal

from logger_config import get_logger
from graphics_view import GraphicsView
from tools import draw_cross, save_image, draw_points
from app_manager import AppManager

# Configure the logger
logger = get_logger("UI")

class AppUI(QWidget):
    """
    Handles UI logic: buttons, scene, mouse events, keyboard events
    States: view_states
    """
    def __init__(self):
        super().__init__()
        self.app_manager = AppManager()
        self.setup_ui()

        self.disp_frame = None

        # Timer for updating frames
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_image)

        self.screen_timer = QTimer()
        self.screen_timer.timeout.connect(self.update_screen)

        self.start_timers()
        
        # Handle Ctrl+C to safe close app
        signal.signal(signal.SIGINT, lambda signal_received, frame: self.close())
        
        logger.info("Press R Key to note current cross position")

        # pause state right after starting
        self.ui_view_states.setCurrentIndex(1)
        self.capture_image()
        

    def setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Image Viewer with Robot Control")
        self.setGeometry(50, 50, 1000, 700)

        # Graphics view for displaying images
        self.graphics_view = GraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.scene)
        self.pixmap_item = None  # Placeholder for the image item

        ##### Cell index spinbox #####
        self.ui_cell_spinbox = QSpinBox() # stores the selected cell index
        self.ui_cell_spinbox.setRange(-1, 0)
        self.app_manager.cell_max_changed.connect(self.ui_cell_spinbox.setMaximum)
        self.app_manager.cell_index_changed.connect(self.ui_cell_spinbox.setValue) # sync spin box with cell value
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
        self.ui_move_to_capture.clicked.connect(self.app_manager.position_and_capture)

        self.ui_insert_single_button = QPushButton("Insert Single", self)
        self.ui_insert_single_button.clicked.connect(lambda: self.app_manager.cell_action(action="insert"))

        self.ui_insert_batch_button = QPushButton("Insert Batch", self)
        self.ui_insert_batch_button.clicked.connect(self.toggle_batch_insert)

        self.ui_echo_button = QPushButton("Echo", self)
        self.ui_echo_button.clicked.connect(self.app_manager.echo_test)

        ##### Layout #####
        layout = QVBoxLayout()
        layout.addWidget(self.graphics_view)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ui_capture_button)
        button_layout.addWidget(self.ui_view_states)
        button_layout.addWidget(self.ui_save_frame_button)
        button_layout.addWidget(self.ui_cell_spinbox)
        button_layout.addWidget(self.ui_move_to_capture)
        button_layout.addWidget(self.ui_insert_single_button)
        button_layout.addWidget(self.ui_insert_batch_button)
        button_layout.addWidget(self.ui_echo_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def view_state_changed(self, state):
        logger.info(f"View state: {state}")
        self.start_timers()

    def start_timers(self):
        """Start the timers based on the current state.
        screen_timer should be responsive
        capture_timer only needs to be on during live, and can be slower
        """
        self.screen_timer.start(100)  # overlay remains active in paused states

        if self.ui_view_states.currentText() == "live":
            self.capture_timer.start(1000)  # live updates
        else:
            self.capture_timer.stop() # use stored image to display

    def capture_image(self):
        """
        Based on the view state, capture and process frame and store in self.disp_frame
        Decoupled from update screen
        Triggers when process button is clicked, should not trigger otherwise
        Capture only if previous capture task is done
        TODO: to fix - process image does not work if view_states is live
        """
        cur_state = self.ui_view_states.currentText()

        # capture image, process if needed
        if cur_state == "live":
            self.app_manager.capture_and_process(process=False)
        else:
            if self.app_manager.capture_and_process(process=True):
                pass
            else:
                logger.error("Process image failure")

    def update_screen(self):
        """
        Update frame to display on the view, should be done with little computation power
        for UI to be responsive. Therefore, camera capture is not done in this function.

        Display frame based on current state
        Make a copy and draw cross
        Works for both grayscale or RGB frame
        """
        cur_state = self.ui_view_states.currentText()

        # store captured image
        if cur_state == "live":
            self.disp_frame = self.app_manager.vision.frame_camera_live
        elif cur_state == "paused orig":
            self.disp_frame = self.app_manager.vision.frame_camera_stored
        elif cur_state == "paused thres":
            self.disp_frame = self.app_manager.vision.frame_threshold
        elif cur_state == "paused contours":
            self.disp_frame = self.app_manager.vision.frame_contour
        else:
            logger.error("Bad state")
            return

        if self.disp_frame is None:
            # warning if there is no processed screen
            if cur_state == "live":
                logger.warning("Skipped frame")
            else: # processed state
                logger.warning("Nothing to display, please capture and process first")
            return
        else:
            # copy the frame away from vision manager (so later can be saved?) TODO: improve comment 
            self.disp_frame = self.disp_frame.copy()

        if cur_state != "live": # processed state
            frame = draw_points(self.disp_frame, self.app_manager.cells_img_xy, self.app_manager.cell_index, size=10)
        else:
            frame = self.disp_frame

        x, y = self.app_manager.cross_cam_xy
        frame = draw_cross(frame, x, y, size=30)

        # # Convert frame to QImage
        # if len(frame.shape) == 2:  # Grayscale frame, likely not needed draw_cross convert to color
        #     height, width = frame.shape
        #     bytes_per_line = width
        #     q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        # else:  # RGB frame
        height, width, channels = frame.shape
        bytes_per_line = channels * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

        # Update the pixmap in the scene
        pixmap = QPixmap.fromImage(q_img)
        if self.pixmap_item is None:
            # Add the image to the scene for the first time
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.pixmap_item)

            self.scene.setBackgroundBrush(QBrush(QColor(0, 128, 128)))  # set background

            # Fit the image to the view initially and set the minimum scale
            self.graphics_view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            self.graphics_view.set_min_scale(self.scene.itemsBoundingRect())
        else:
            # Update the image without resetting the zoom
            self.pixmap_item.setPixmap(pixmap)

        # TODO: need?
        # del self.frame

    def on_cell_spinbox_changed(self, value):
        self.app_manager.set_cell_index(value)

    def on_save_frame(self):
        save_image(self.disp_frame, "save/")

    def toggle_batch_insert(self):
        self.app_manager.toggle_pause_insert()
        if not self.app_manager.pause_insert:
            self.ui_insert_batch_button.setText("Pause Insert")
            self.app_manager.insert_all_in_view() # TODO: change to insert_batch for capturing
        else:
            self.ui_insert_batch_button.setText("Insert Batch")
            

    def update_cross_position(self, scene_pos):
        """
        Called by mouse click (in graphics_view.py)
        Get clicked scene position. Stored position in AppManager

        Args:
            scene_pos (QPointF): The clicked position in scene coordinates.
        """
        if self.pixmap_item is not None:
            # Map scene coordinates to image coordinates
            pixmap_rect = self.pixmap_item.pixmap().rect()
            image_width = pixmap_rect.width()
            image_height = pixmap_rect.height()

            # Scene coordinates are relative to the pixmap; map accordingly
            x = int(scene_pos.x())
            y = int(scene_pos.y())

            # Bounds check to ensure valid image coordinates
            x = max(0, min(x, image_width - 1))
            y = max(0, min(y, image_height - 1))

            self.app_manager.set_cross_position(x, y)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Left:      self.app_manager.shift_cross(dx=-1)
        elif key == Qt.Key_Right:   self.app_manager.shift_cross(dx=1)
        elif key == Qt.Key_Up:      self.app_manager.shift_cross(dy=-1)
        elif key == Qt.Key_Down:    self.app_manager.shift_cross(dy=1)
        elif key == Qt.Key_A:       self.app_manager.shift_cross(dx=-10)
        elif key == Qt.Key_D:       self.app_manager.shift_cross(dx=10)
        elif key == Qt.Key_W:       self.app_manager.shift_cross(dy=-10)
        elif key == Qt.Key_S:       self.app_manager.shift_cross(dy=10)
        elif key == Qt.Key_R:       self.app_manager.print_cross_position()

    def closeEvent(self, event):
        """
        Stop the camera, timer, and robot connection when the window is closed.

        Args:
            event (QCloseEvent): The close event triggered when the window is closed.
        """
        logger.info(f"Closing application...")

        # Stop the timer for frame update
        if self.capture_timer.isActive():
            self.capture_timer.stop()

        if self.screen_timer.isActive():
            self.screen_timer.stop()

        # Close the robot socket connection and camera
        self.app_manager.close()

        # Accept the event to close the application
        event.accept()