from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QSpinBox
from PyQt5.QtGui import QImage, QPixmap
import numpy as np
import signal
from graphics_view import GraphicsView
from camera import CameraHandler
from robot import RobotSocketClient
from image_processing import undistort_image, draw_cross, map_image_to_world, find_centroids, draw_points, save_image
from config import CAMERA_MATRIX, DIST_COEFFS, HOMO_MATRIX, SAVE_FOLDER, CAM_NUM
from logger_config import get_logger

# Configure the logger
logger = get_logger("UI")

class VisionApp(QWidget):
    def __init__(self):
        super().__init__()
        logger.info("Press R Key to record current cross position")
        self.setup_ui()
        self.setup_robot_conn()
        self.camera = CameraHandler(cam_num=CAM_NUM)

        # Handle Ctrl+C to safe close app
        signal.signal(signal.SIGINT, lambda signal_received, frame: self.close())

        # Timer for updating frames
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(100) # in ms

        # start at camera's focal point
        self.cam_cross_pos = np.array([int(CAMERA_MATRIX[0][2]), int(CAMERA_MATRIX[1][2])])
        self.robo_cross_pos = None
        self.is_pause = False
        self.view_state = "live" # live, live_clear, paused_orig, paused_thres, paused_contours
        self.save_next_frame = False

        # frame and points, (all being saved during process_image)
        self.frame_saved = None # right after undistort
        self.frame_threshold = None # right after threshold
        self.frame_contour = None # with contour
        self.centroids = None # list of cenrtroids

        # robot last point
        self.robot_last_point = None

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
        self.insert_button = QPushButton("Insert", self)
        self.echo_button = QPushButton("Echo", self)

        # Connect control to functions
        self.capture_button.clicked.connect(self.process_image)
        self.cycle_vision_button.clicked.connect(self.cycle_vision)
        self.save_frame_button.clicked.connect(self.on_save_frame)
        self.jump_xy_button.clicked.connect(self.jump_xy)
        self.insert_button.clicked.connect(self.insert_cell)
        self.echo_button.clicked.connect(self.echo_test)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.graphics_view)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.capture_button)
        button_layout.addWidget(self.cycle_vision_button)
        button_layout.addWidget(self.save_frame_button)
        button_layout.addWidget(self.cell_index)
        button_layout.addWidget(self.jump_xy_button)
        button_layout.addWidget(self.insert_button)
        button_layout.addWidget(self.echo_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def setup_robot_conn(self):
        self.robot_client = RobotSocketClient('192.168.0.1', 8501)
        self.robot_client.connect()

    def echo_test(self):
        self.robot_client.send_command(f"echo 0 1 2 3")

    def jump_xy(self):
        if self.robo_cross_pos is not None:
            x, y = self.robo_cross_pos
            self.robot_client.send_command(f"jump {x:.2f} {y:.2f} -75 180")
            self.robot_last_point = [x, y, -75, 180]

    def insert_cell(self):
        if self.robo_cross_pos is not None:
            x, y = self.robo_cross_pos
            self.robot_client.send_command(f"insert {x:.2f} {y:.2f} -140 180")
            self.robot_last_point = None

    def process_image(self):
        """Capture the current frame and save it to a file.
        Also process the image to find centroids
        Reset centroid index
        """
        self.cell_index.setValue(-1)

        image = self.camera.get_frame()
        if image is None:
            return
        
        # process image
        process_dict = find_centroids(image)

        self.frame_saved = image
        self.frame_threshold = process_dict["threshold"]
        self.frame_contour = process_dict["contour_overlay"]
        self.centroids = process_dict["centroids"]
        
        self.cell_index.setMaximum(len(self.centroids) - 1)

        logger.info(f"Total centroids found: {len(self.centroids)}")
        self.next_centroid()
        
    def cycle_vision(self):
        """Cycle different states"""
        if self.view_state == "live":
            self.view_state = "paused_orig"
        elif self.view_state == "paused_orig":
            self.view_state = "paused_thres"
        elif self.view_state == "paused_thres":
            self.view_state = "paused_contours"
        elif self.view_state == "paused_contours":
            self.view_state = "live_clear"
        elif self.view_state == "live_clear":
            self.view_state = "live"

        self.cycle_vision_button.setText(self.view_state)
        logger.info(f"View state: {self.view_state}")
    
    def on_save_frame(self):
        self.save_next_frame = True
    
    def next_centroid(self):
        """Point self.cam_cross_pos to the next centroid in self.centroids"""
        # TODO: If finish, return none
        if not self.centroids:
            logger.error("No centroids found")
            return
        
        self.cell_index.setValue(self.cell_index.value() + 1) # increment cell index

        if self.cell_index.value() < len(self.centroids):
            x, y = self.centroids[self.cell_index.value()]
            self.set_cross_position(x, y)
            logger.info(f"Centroid #{self.cell_index.value()}: {x}, {y}")
        else:
            logger.info("No more centroids to go next")

    def update_frame(self):
        """Update frame to display on the view"""

        if self.view_state == "live" or self.view_state == "live_clear":
            frame = self.camera.get_frame()
        elif self.view_state == "paused_orig":
            frame = self.frame_saved
        elif self.view_state == "paused_thres":
            frame = self.frame_threshold
        elif self.view_state == "paused_contours":
            frame = self.frame_contour

        if frame is None:
            # logger.info("No frame update")
            return
        frame = frame.copy()

        if self.centroids and self.view_state != "live_clear":
            draw_points(frame, self.centroids, self.cell_index.value())
        draw_cross(frame, self.cam_cross_pos[0], self.cam_cross_pos[1])
        if self.save_next_frame:
            save_image(frame)
            self.save_next_frame = False


        # Convert frame to QImage
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

        del frame

    def update_cross_position(self, scene_pos):
        """
        Update cam_cross_pos based on the clicked scene position.
        This function is used in graphics_view.py

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

            # Update cam_cross_pos and redraw
            self.set_cross_position(x, y)
            # self.cam_cross_pos = np.array([x, y])
            # logger.info(f"New cross position: {self.cam_cross_pos}")
            # self.update_frame()
        
    def set_cross_position(self, x, y):
        self.cam_cross_pos = np.array([x, y])
        self.robo_cross_pos = map_image_to_world(self.cam_cross_pos, HOMO_MATRIX)
        # logger.info(f"Camera: {self.cam_cross_pos}, Robot: {self.robo_cross_pos}")

    def record_pos_info(self):
        """For fine tuning homography use.
        Will print out:
            - Last command's robot position
            - Current cross position
        Save at least 9 robot position and current cross position pair to recalibrate
        (img_x(px), img_y, robo_x(mm), robo_y)
        """
        if self.robot_last_point:
            img_x, img_y = self.cam_cross_pos
            robo_x, robo_y, _, _ = self.robot_last_point
            logger.info(f"        ({img_x}, {img_y}, {robo_x}, {robo_y})")
        else:
            img_x, img_y = self.cam_cross_pos
            logger.info(f"        ({img_x}, {img_y}, robo_x, robo_y)")

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
            self.record_pos_info()
        elif key == Qt.Key_C:
            self.cycle_vision()

        self.set_cross_position(self.cam_cross_pos[0] + x_shift, self.cam_cross_pos[1] + y_shift)

    def closeEvent(self, event):
        """
        Stop the camera, timer, and robot connection when the window is closed.

        Args:
            event (QCloseEvent): The close event triggered when the window is closed.
        """
        logger.info("Closing application...")

        # Stop the timer
        if self.timer.isActive():
            self.timer.stop()

        # Release the camera
        if hasattr(self.camera, 'release') and callable(self.camera.release):
            self.camera.release()

        # Close the robot socket connection
        if self.robot_client is not None:
            self.robot_client.close()

        # Accept the event to close the application
        event.accept()

