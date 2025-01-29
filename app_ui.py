from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QSpinBox
from PyQt5.QtGui import QImage, QPixmap
import signal

from logger_config import get_logger
from graphics_view import GraphicsView
from tools import draw_cross
from app_manager import AppManager

# Configure the logger
logger = get_logger("UI")

class AppUI(QWidget):
    """
    Handles UI: buttons, scene, mouse events, keyboard events
    States: view_state, frame
    """
    def __init__(self):
        super().__init__()
        self.app_manager = AppManager()
        self.setup_ui()

        # Handle Ctrl+C to safe close app
        signal.signal(signal.SIGINT, lambda signal_received, frame: self.close())

        # Timer for updating frames
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_frame)

        self.screen_timer = QTimer()
        self.screen_timer.timeout.connect(self.update_screen)

        self.view_state = "live" # live, live_clear, paused_orig, paused_thres, paused_contours
        self.start_timers()

        logger.info("Press R Key to note current cross position")

    def setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Image Viewer with Robot Control")
        self.setGeometry(50, 50, 1000, 700)

        # Graphics view for displaying images
        self.graphics_view = GraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.scene)
        self.pixmap_item = None  # Placeholder for the image item

        # stores the selected cell index
        self.cell_index = QSpinBox()
        self.cell_index.setRange(-1, 0)

        # Control buttons and spin box
        self.capture_button = QPushButton("Process", self)
        self.cycle_vision_button = QPushButton("Live", self)
        self.save_frame_button = QPushButton("Save Frame", self)
        self.jump_xy_button = QPushButton("Jump XY", self)
        self.insert_single_button = QPushButton("Insert Single", self)
        self.insert_view_button = QPushButton("Insert View", self)
        self.echo_button = QPushButton("Echo", self)

        # Connect control to functions
        self.capture_button.clicked.connect(self.app_manager.capture_and_process)
        self.cycle_vision_button.clicked.connect(self.cycle_vision)
        self.save_frame_button.clicked.connect(self.app_manager.on_save_frame)
        self.jump_xy_button.clicked.connect(self.app_manager.jump_xy)
        self.insert_single_button.clicked.connect(self.app_manager.insert_single)
        self.insert_view_button.clicked.connect(self.app_manager.insert_all_in_view)
        self.echo_button.clicked.connect(self.app_manager.echo_test)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.graphics_view)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.capture_button)
        button_layout.addWidget(self.cycle_vision_button)
        button_layout.addWidget(self.save_frame_button)
        button_layout.addWidget(self.cell_index)
        button_layout.addWidget(self.jump_xy_button)
        button_layout.addWidget(self.insert_single_button)
        button_layout.addWidget(self.insert_view_button)
        button_layout.addWidget(self.echo_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def cycle_vision(self):
        """
        Cycle different states
        Stop updatting frame if is in a paused state
        """
        if self.view_state == "live":
            self.view_state = "paused_orig"
        elif self.view_state == "paused_orig":
            self.view_state = "paused_thres"
            self.capture_timer.stop()
        elif self.view_state == "paused_thres":
            self.view_state = "paused_contours"
        elif self.view_state == "paused_contours":
            self.view_state = "live_clear"
            self.capture_timer.start(2000)
        elif self.view_state == "live_clear":
            self.view_state = "live"

        self.cycle_vision_button.setText(self.view_state)
        self.start_timers()
        logger.info(f"View state: {self.view_state}") 

    def start_timers(self):
        """Start the timers based on the current state."""
        if self.view_state == "live":
            print("started live timer")
            self.capture_timer.start(200)  # 1000ms for live updates
            self.screen_timer.start(100)  # 100ms for overlay responsiveness
        else:
            self.capture_timer.stop()
            self.screen_timer.start(100)  # Only overlay remains active in paused states


    def capture_frame(self):
        self.app_manager.capture_and_process()

    def update_screen(self):
        """Update frame to display on the view"""
        
        if self.app_manager.vision.frame_camera is None:
            return
        frame = self.app_manager.vision.frame_camera

        x, y = self.app_manager.cam_xy_cross
        print( x, y)
        frame = draw_cross(frame, x, y)

        # Convert frame to QImage
        if len(frame.shape) == 2:  # Grayscale frame
            height, width = frame.shape
            bytes_per_line = width
            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        else:  # RGB frame
            height, width, channels = frame.shape
            bytes_per_line = channels * width
            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

        # Update the pixmap in the scene
        pixmap = QPixmap.fromImage(q_img)
        if self.pixmap_item is None:
            # Add the image to the scene for the first time
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.pixmap_item)

            # Fit the image to the view initially and set the minimum scale
            self.graphics_view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            self.graphics_view.set_min_scale(self.scene.itemsBoundingRect())
        else:
            # Update the image without resetting the zoom
            self.pixmap_item.setPixmap(pixmap)

        # TODO: need?
        # del self.frame

    def update_overlay(self):
        pass

    def update_cross_position(self, scene_pos):
        """
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
            logger.info(f'Clicked on {x}, {y}')


    # def update_cross_position(self, scene_pos):
    #     """
    #     Update cam_cross_pos based on the clicked scene position.

    #     Args:
    #         scene_pos (QPointF): The clicked position in scene coordinates.
    #     """
    #     if self.pixmap_item is not None:
    #         # Map scene coordinates to image coordinates
    #         pixmap_rect = self.pixmap_item.pixmap().rect()
    #         image_width = pixmap_rect.width()
    #         image_height = pixmap_rect.height()

    #         # Scene coordinates are relative to the pixmap; map accordingly
    #         x = int(scene_pos.x())
    #         y = int(scene_pos.y())

    #         # Bounds check to ensure valid image coordinates
    #         x = max(0, min(x, image_width - 1))
    #         y = max(0, min(y, image_height - 1))

    #         print(x, y)

            # Update cam_cross_pos and redraw
            # self.set_cross_position(x, y)
            # self.cam_cross_pos = np.array([x, y])
            # logger.info(f"New cross position: {self.cam_cross_pos}")
            # self.update_frame()

    def keyPressEvent(self, event):
        key = event.key()
        x_shift, y_shift = 0, 0
        # TODO: check for boundaries of the cross
        if key == Qt.Key_Left:
            x_shift = -1
        elif key == Qt.Key_Right:
            x_shift = 1
        elif key == Qt.Key_Up:
            y_shift = -1
        elif key == Qt.Key_Down:
            y_shift = 1
        elif key == Qt.Key_A:
            x_shift = -10
        elif key == Qt.Key_D:
            x_shift = 10
        elif key == Qt.Key_W:
            y_shift = -10
        elif key == Qt.Key_S:
            y_shift = 10
        elif key == Qt.Key_R:
            self.app_manager.print_pos_info()
        elif key == Qt.Key_C:
            self.cycle_vision()

        # self.set_cross_position(self.cam_cross_pos[0] + x_shift, self.cam_cross_pos[1] + y_shift)

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