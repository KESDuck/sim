from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QPushButton, QVBoxLayout, 
                           QHBoxLayout, QWidget, 
                           QSpinBox, QLabel, QGroupBox, QButtonGroup,
                           QGraphicsView, QGraphicsScene, QTextEdit, QScrollArea,
                           QGridLayout, QSlider)
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPalette

from utils.logger_config import get_logger
from utils.ui_styles import (
    group_box_primary, group_box_secondary, label_muted,
    button_toggle_blue, button_toggle_green, button_toggle_green_speed,
    button_action, button_save, button_capture, button_motor, button_move,
    button_reconnect, text_edit_dark, ping_table_widget_style, spinbox_dark
)

logger = get_logger("EngineerView")

class EngineerTabView(QWidget):
    """
    View component for the Engineer tab.
    Handles UI elements and interactions specific to the engineering interface.
    Based on A1 layout with frame controls, zoom, calibration tools, and robot controls.
    
    TODO: header labels are same as button label, hard to differentiate
    """
    def __init__(self, controller, font_medium, font_normal, app_view=None):
        super().__init__()
        self.controller = controller
        self.font_medium = font_medium
        self.font_normal = font_normal
        self.app_view = app_view  # Store reference to app_view for accessing vision_view
        
        # Create additional fonts for better hierarchy
        self.font_large = QFont()
        self.font_large.setPointSize(20)
        self.font_large.setBold(True)
        
        self.font_small = QFont()
        self.font_small.setPointSize(12)
        
        self.font_label = QFont()
        self.font_label.setPointSize(13)
        self.font_label.setBold(False)
        
        self.setup_ui()
        
        # Initialize with proper state
        self.view_state_changed("paused orig")
        
    def setup_ui(self):
        """Initialize the engineer tab interface."""
        # Create scroll area
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create content widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)
        
        # Frame view controls
        frame_group = QGroupBox("📷 Frame View Controls")
        frame_group.setFont(self.font_large)
        frame_group.setStyleSheet(group_box_primary('#4A9EFF'))
        frame_layout = QVBoxLayout()
        frame_layout.setSpacing(12)
        
        # Frame type buttons - labels in first row, buttons in second row
        frame_type_label_row = QHBoxLayout()
        frame_type_label = QLabel("Frame Type:")
        frame_type_label.setFont(self.font_label)
        frame_type_label.setStyleSheet(label_muted())
        frame_type_label_row.addWidget(frame_type_label)
        frame_type_label_row.addStretch()
        frame_layout.addLayout(frame_type_label_row)
        
        frame_type_button_row = QHBoxLayout()
        frame_type_button_row.setSpacing(10)
        self.frame_type_button_group = QButtonGroup()
        self.frame_type_original_btn = QPushButton("🖼️ Original")
        self.frame_type_original_btn.setFont(self.font_normal)
        self.frame_type_original_btn.setCheckable(True)
        self.frame_type_original_btn.setChecked(True)
        self.frame_type_original_btn.setMinimumHeight(38)
        self.frame_type_original_btn.setMinimumWidth(110)
        self.frame_type_original_btn.setStyleSheet(button_toggle_blue())
        self.frame_type_original_btn.clicked.connect(lambda: self.on_frame_type_changed("paused orig"))
        
        self.frame_type_threshold_btn = QPushButton("🔲 Threshold")
        self.frame_type_threshold_btn.setFont(self.font_normal)
        self.frame_type_threshold_btn.setCheckable(True)
        self.frame_type_threshold_btn.setMinimumHeight(38)
        self.frame_type_threshold_btn.setMinimumWidth(110)
        self.frame_type_threshold_btn.setStyleSheet(button_toggle_blue())
        self.frame_type_threshold_btn.clicked.connect(lambda: self.on_frame_type_changed("paused thres"))
        
        self.frame_type_contours_btn = QPushButton("📐 Contours")
        self.frame_type_contours_btn.setFont(self.font_normal)
        self.frame_type_contours_btn.setCheckable(True)
        self.frame_type_contours_btn.setMinimumHeight(38)
        self.frame_type_contours_btn.setMinimumWidth(110)
        self.frame_type_contours_btn.setStyleSheet(button_toggle_blue())
        self.frame_type_contours_btn.clicked.connect(lambda: self.on_frame_type_changed("paused contours"))
        
        self.frame_type_button_group.addButton(self.frame_type_original_btn, 0)
        self.frame_type_button_group.addButton(self.frame_type_threshold_btn, 1)
        self.frame_type_button_group.addButton(self.frame_type_contours_btn, 2)
        
        frame_type_button_row.addWidget(self.frame_type_original_btn)
        frame_type_button_row.addWidget(self.frame_type_threshold_btn)
        frame_type_button_row.addWidget(self.frame_type_contours_btn)
        frame_type_button_row.addStretch()
        frame_layout.addLayout(frame_type_button_row)
        
        # Show centroids and bounding boxes - labels in first row, buttons in second row
        centroids_label_row = QHBoxLayout()
        centroids_label = QLabel("Display Options:")
        centroids_label.setFont(self.font_label)
        centroids_label.setStyleSheet(label_muted())
        centroids_label_row.addWidget(centroids_label)
        centroids_label_row.addStretch()
        frame_layout.addLayout(centroids_label_row)
        
        centroids_button_row = QHBoxLayout()
        centroids_button_row.setSpacing(10)
        self.show_centroids_btn = QPushButton("📍 Centroids")
        self.show_centroids_btn.setFont(self.font_normal)
        self.show_centroids_btn.setCheckable(True)
        self.show_centroids_btn.setChecked(True)
        self.show_centroids_btn.setMinimumHeight(38)
        self.show_centroids_btn.setMinimumWidth(130)
        self.show_centroids_btn.setStyleSheet(button_toggle_green())
        self.show_centroids_btn.clicked.connect(self.on_centroids_toggled)
        
        self.show_bbox_btn = QPushButton("📦 Bounding Boxes")
        self.show_bbox_btn.setFont(self.font_normal)
        self.show_bbox_btn.setCheckable(True)
        self.show_bbox_btn.setChecked(True)
        self.show_bbox_btn.setMinimumHeight(38)
        self.show_bbox_btn.setMinimumWidth(150)
        self.show_bbox_btn.setStyleSheet(button_toggle_green())
        self.show_bbox_btn.clicked.connect(self.on_bbox_toggled)
        
        centroids_button_row.addWidget(self.show_centroids_btn)
        centroids_button_row.addWidget(self.show_bbox_btn)
        centroids_button_row.addStretch()
        frame_layout.addLayout(centroids_button_row)
        
        # Zoom controls - labels in first row, buttons in second row
        zoom_label_row = QHBoxLayout()
        zoom_label = QLabel("View Controls:")
        zoom_label.setFont(self.font_label)
        zoom_label.setStyleSheet(label_muted())
        zoom_label_row.addWidget(zoom_label)
        zoom_label_row.addStretch()
        frame_layout.addLayout(zoom_label_row)
        
        zoom_button_row = QHBoxLayout()
        zoom_button_row.setSpacing(10)
        self.zoom_in_button = QPushButton("🔍+ Zoom In")
        self.zoom_in_button.setFont(self.font_normal)
        self.zoom_in_button.setMinimumHeight(38)
        self.zoom_in_button.setMinimumWidth(120)
        self.zoom_in_button.setStyleSheet(button_action())
        self.zoom_in_button.clicked.connect(self.on_zoom_in)
        
        self.zoom_out_button = QPushButton("🔍- Zoom Out")
        self.zoom_out_button.setFont(self.font_normal)
        self.zoom_out_button.setMinimumHeight(38)
        self.zoom_out_button.setMinimumWidth(120)
        self.zoom_out_button.setStyleSheet(button_action())
        self.zoom_out_button.clicked.connect(self.on_zoom_out)
        
        self.reset_view_button = QPushButton("↺ Reset View")
        self.reset_view_button.setFont(self.font_normal)
        self.reset_view_button.setMinimumHeight(38)
        self.reset_view_button.setMinimumWidth(120)
        self.reset_view_button.setStyleSheet(button_action())
        self.reset_view_button.clicked.connect(self.on_reset_view)
        
        zoom_button_row.addWidget(self.zoom_in_button)
        zoom_button_row.addWidget(self.zoom_out_button)
        zoom_button_row.addWidget(self.reset_view_button)
        zoom_button_row.addStretch()
        frame_layout.addLayout(zoom_button_row)
        
        # Save image button - separate row
        save_label_row = QHBoxLayout()
        save_label = QLabel("Save:")
        save_label.setFont(self.font_label)
        save_label.setStyleSheet(label_muted())
        save_label_row.addWidget(save_label)
        save_label_row.addStretch()
        frame_layout.addLayout(save_label_row)
        
        save_button_row = QHBoxLayout()
        save_button_row.setSpacing(10)
        self.save_image_button = QPushButton("💾 Save Image")
        self.save_image_button.setFont(self.font_normal)
        self.save_image_button.setMinimumHeight(38)
        self.save_image_button.setMinimumWidth(120)
        self.save_image_button.setStyleSheet(button_save())
        self.save_image_button.clicked.connect(self.controller.save_current_frame)
        save_button_row.addWidget(self.save_image_button)
        save_button_row.addStretch()
        frame_layout.addLayout(save_button_row)
        
        frame_group.setLayout(frame_layout)
        layout.addWidget(frame_group)
        
        # Calibration tools
        calib_group = QGroupBox("🔧 Calibration Tools")
        calib_group.setFont(self.font_large)
        calib_group.setStyleSheet(group_box_primary('#FFA500'))
        calib_layout = QVBoxLayout()
        calib_layout.setSpacing(12)
        
        # Exposure time slider
        exposure_label_row = QHBoxLayout()
        exposure_label = QLabel("Exposure Time:")
        exposure_label.setFont(self.font_label)
        exposure_label.setStyleSheet(label_muted())
        exposure_label_row.addWidget(exposure_label)
        
        self.exposure_value_label = QLabel("---")
        self.exposure_value_label.setFont(self.font_label)
        self.exposure_value_label.setStyleSheet(label_muted())
        self.exposure_value_label.setMinimumWidth(80)
        exposure_label_row.addWidget(self.exposure_value_label)
        exposure_label_row.addStretch()
        calib_layout.addLayout(exposure_label_row)
        
        exposure_slider_row = QHBoxLayout()
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setMinimum(100)  # 100 µs
        self.exposure_slider.setMaximum(300000)  # 300 ms
        self.exposure_slider.setMinimumHeight(30)
        self.exposure_slider.valueChanged.connect(self.on_exposure_time_changed)
        exposure_slider_row.addWidget(self.exposure_slider)
        calib_layout.addLayout(exposure_slider_row)
        
        # Initialize exposure time from camera (will set default if camera not available)
        self._update_exposure_time_from_camera()
        
        # Preview / capture buttons
        capture_button_row = QHBoxLayout()
        capture_button_row.setSpacing(10)
        self.preview_button = QPushButton("👁️ Preview")
        self.preview_button.setFont(self.font_normal)
        self.preview_button.setMinimumHeight(38)
        self.preview_button.setMinimumWidth(120)
        self.preview_button.setStyleSheet(button_action())
        self.preview_button.clicked.connect(self.on_preview_image)
        capture_button_row.addWidget(self.preview_button)

        self.capture_image_button = QPushButton("📸 Capture Image")
        self.capture_image_button.setFont(self.font_normal)
        self.capture_image_button.setMinimumHeight(38)
        self.capture_image_button.setMinimumWidth(150)
        self.capture_image_button.setStyleSheet(button_capture())
        self.capture_image_button.clicked.connect(self.on_capture_image)
        capture_button_row.addWidget(self.capture_image_button)
        capture_button_row.addStretch()
        calib_layout.addLayout(capture_button_row)
        
        # Secondary frame for captured image
        secondary_frame_group = QGroupBox("Captured Image")
        secondary_frame_group.setFont(self.font_label)
        secondary_frame_group.setStyleSheet(group_box_secondary())
        secondary_frame_layout = QVBoxLayout()
        self.secondary_view = QGraphicsView()
        self.secondary_scene = QGraphicsScene()
        self.secondary_view.setScene(self.secondary_scene)
        self.secondary_view.setMinimumHeight(150)
        secondary_frame_layout.addWidget(self.secondary_view)
        secondary_frame_group.setLayout(secondary_frame_layout)
        calib_layout.addWidget(secondary_frame_group)
        
        calib_group.setLayout(calib_layout)
        layout.addWidget(calib_group)

        # Robot motor control
        motor_group = QGroupBox("⚙️ Robot Motor Control")
        motor_group.setFont(self.font_large)
        motor_group.setStyleSheet(group_box_primary('#FF6B6B'))
        motor_layout = QVBoxLayout()
        motor_layout.setSpacing(12)
        
        # Motor toggle button
        self.motor_toggle_btn = QPushButton()
        self.motor_toggle_btn.setFont(self.font_normal)
        self.motor_toggle_btn.setCheckable(True)
        self.motor_toggle_btn.setMinimumHeight(45)
        self.motor_toggle_btn.setStyleSheet(button_motor())
        self.motor_toggle_btn.clicked.connect(self.on_motor_toggle_clicked)
        motor_layout.addWidget(self.motor_toggle_btn)
        
        # Speed control - label row
        speed_label_row = QHBoxLayout()
        speed_label = QLabel("Speed:")
        speed_label.setFont(self.font_label)
        speed_label.setStyleSheet(label_muted())
        speed_label_row.addWidget(speed_label)
        speed_label_row.addStretch()
        motor_layout.addLayout(speed_label_row)
        
        # Speed control - button row
        speed_button_row = QHBoxLayout()
        speed_button_row.setSpacing(10)
        self.speed_button_group = QButtonGroup()
        
        self.speed_slow_button = QPushButton("🐌 Slow")
        self.speed_slow_button.setFont(self.font_normal)
        self.speed_slow_button.setCheckable(True)
        self.speed_slow_button.setMinimumHeight(38)
        self.speed_slow_button.setMinimumWidth(100)
        self.speed_slow_button.setStyleSheet(button_toggle_green_speed())
        self.speed_slow_button.clicked.connect(lambda: self.on_speed_selected("slow"))
        
        self.speed_normal_button = QPushButton("⚡ Normal")
        self.speed_normal_button.setFont(self.font_normal)
        self.speed_normal_button.setCheckable(True)
        self.speed_normal_button.setChecked(True)  # Default selection
        self.speed_normal_button.setMinimumHeight(38)
        self.speed_normal_button.setMinimumWidth(100)
        self.speed_normal_button.setStyleSheet(button_toggle_green_speed())
        self.speed_normal_button.clicked.connect(lambda: self.on_speed_selected("normal"))
        
        self.speed_fast_button = QPushButton("🚀 Fast")
        self.speed_fast_button.setFont(self.font_normal)
        self.speed_fast_button.setCheckable(True)
        self.speed_fast_button.setMinimumHeight(38)
        self.speed_fast_button.setMinimumWidth(100)
        self.speed_fast_button.setStyleSheet(button_toggle_green_speed())
        self.speed_fast_button.clicked.connect(lambda: self.on_speed_selected("fast"))
        
        self.speed_button_group.addButton(self.speed_slow_button, 0)
        self.speed_button_group.addButton(self.speed_normal_button, 1)
        self.speed_button_group.addButton(self.speed_fast_button, 2)
        
        speed_button_row.addWidget(self.speed_slow_button)
        speed_button_row.addWidget(self.speed_normal_button)
        speed_button_row.addWidget(self.speed_fast_button)
        speed_button_row.addStretch()
        motor_layout.addLayout(speed_button_row)
        
        motor_group.setLayout(motor_layout)
        layout.addWidget(motor_group)
        initial_motor_state = False
        if hasattr(self.controller, "is_motor_enabled"):
            initial_motor_state = self.controller.is_motor_enabled()
        self._update_motor_button(initial_motor_state)
        
        # Click history
        history_group = QGroupBox("📋 Click History")
        history_group.setFont(self.font_label)
        history_group.setStyleSheet(group_box_secondary())
        history_layout = QVBoxLayout()
        self.history_text = QTextEdit()
        self.history_text.setFont(self.font_small)
        self.history_text.setReadOnly(False)
        self.history_text.setMinimumHeight(150)
        self.history_text.setMaximumHeight(200)
        self.history_text.setPlaceholderText("Click history will appear here...")
        self.history_text.setStyleSheet(text_edit_dark())
        history_layout.addWidget(self.history_text)
        history_group.setLayout(history_layout)
        calib_layout.addWidget(history_group)
        
        # Robot move controls
        move_group = QGroupBox("🤖 Robot Move to Point")
        move_group.setFont(self.font_large)
        move_group.setStyleSheet(group_box_primary('#9B59B6'))
        move_layout = QVBoxLayout()
        move_layout.setSpacing(12)
        
        # First row: X and Y
        coord_row1 = QHBoxLayout()
        coord_row1.setSpacing(8)
        
        x_label = QLabel("X:")
        x_label.setFont(self.font_label)
        x_label.setStyleSheet(label_muted() + " min-width: 30px;")
        coord_row1.addWidget(x_label)
        self.x_spinbox = QSpinBox()
        self.x_spinbox.setFont(self.font_normal)
        self.x_spinbox.setRange(-10000, 10000)
        self.x_spinbox.setValue(0)
        self.x_spinbox.setMinimumHeight(38)
        self.x_spinbox.setStyleSheet(spinbox_dark())
        coord_row1.addWidget(self.x_spinbox)
        
        y_label = QLabel("Y:")
        y_label.setFont(self.font_label)
        y_label.setStyleSheet(label_muted() + " min-width: 30px;")
        coord_row1.addWidget(y_label)
        self.y_spinbox = QSpinBox()
        self.y_spinbox.setFont(self.font_normal)
        self.y_spinbox.setRange(-10000, 10000)
        self.y_spinbox.setValue(0)
        self.y_spinbox.setMinimumHeight(38)
        self.y_spinbox.setStyleSheet(spinbox_dark())
        coord_row1.addWidget(self.y_spinbox)
        coord_row1.addStretch()
        move_layout.addLayout(coord_row1)
        
        # Second row: Z and U
        coord_row2 = QHBoxLayout()
        coord_row2.setSpacing(8)
        
        z_label = QLabel("Z:")
        z_label.setFont(self.font_label)
        z_label.setStyleSheet(label_muted() + " min-width: 30px;")
        coord_row2.addWidget(z_label)
        self.z_spinbox = QSpinBox()
        self.z_spinbox.setFont(self.font_normal)
        self.z_spinbox.setRange(-10000, 10000)
        self.z_spinbox.setValue(0)
        self.z_spinbox.setMinimumHeight(38)
        self.z_spinbox.setStyleSheet(spinbox_dark())
        coord_row2.addWidget(self.z_spinbox)
        
        u_label = QLabel("U:")
        u_label.setFont(self.font_label)
        u_label.setStyleSheet(label_muted() + " min-width: 30px;")
        coord_row2.addWidget(u_label)
        self.u_spinbox = QSpinBox()
        self.u_spinbox.setFont(self.font_normal)
        self.u_spinbox.setRange(-10000, 10000)
        self.u_spinbox.setValue(0)
        self.u_spinbox.setMinimumHeight(38)
        self.u_spinbox.setStyleSheet(spinbox_dark())
        coord_row2.addWidget(self.u_spinbox)
        coord_row2.addStretch()
        move_layout.addLayout(coord_row2)
        
        # Preload buttons row
        preload_button_row = QHBoxLayout()
        preload_button_row.setSpacing(10)
        
        # Button for section 1
        self.preload_section1_btn = QPushButton("📍 Section 1")
        self.preload_section1_btn.setFont(self.font_normal)
        self.preload_section1_btn.setMinimumHeight(38)
        self.preload_section1_btn.setMinimumWidth(100)
        self.preload_section1_btn.setStyleSheet(button_action())
        self.preload_section1_btn.clicked.connect(lambda: self._preload_section("1"))
        preload_button_row.addWidget(self.preload_section1_btn)
        
        # Button for section 2
        self.preload_section2_btn = QPushButton("📍 Section 2")
        self.preload_section2_btn.setFont(self.font_normal)
        self.preload_section2_btn.setMinimumHeight(38)
        self.preload_section2_btn.setMinimumWidth(100)
        self.preload_section2_btn.setStyleSheet(button_action())
        self.preload_section2_btn.clicked.connect(lambda: self._preload_section("2"))
        preload_button_row.addWidget(self.preload_section2_btn)
        
        # Button for section 3
        self.preload_section3_btn = QPushButton("📍 Section 3")
        self.preload_section3_btn.setFont(self.font_normal)
        self.preload_section3_btn.setMinimumHeight(38)
        self.preload_section3_btn.setMinimumWidth(100)
        self.preload_section3_btn.setStyleSheet(button_action())
        self.preload_section3_btn.clicked.connect(lambda: self._preload_section("3"))
        preload_button_row.addWidget(self.preload_section3_btn)
        
        preload_button_row.addStretch()
        move_layout.addLayout(preload_button_row)
        
        self.move_button = QPushButton("▶️ Move Robot")
        self.move_button.setFont(self.font_normal)
        self.move_button.setMinimumHeight(42)
        self.move_button.setStyleSheet(button_move())
        self.move_button.clicked.connect(self.on_move_robot)
        move_layout.addWidget(self.move_button)
        
        move_group.setLayout(move_layout)
        layout.addWidget(move_group)
        
        layout.addStretch()
        
        # Connection group (at the bottom)
        connect_group = QGroupBox("🔌 Connection Status")
        connect_group.setFont(self.font_large)
        connect_group.setStyleSheet(group_box_primary('#00CED1'))
        connect_layout = QVBoxLayout()
        connect_layout.setSpacing(12)
        
        # Ping table: labels row and status lights row
        devices = {}
        if hasattr(self.controller, 'get_network_devices'):
            devices = self.controller.get_network_devices()
        else:
            logger.warning("Controller missing get_network_devices method")
        
        ping_table_widget = QWidget()
        ping_table = QGridLayout(ping_table_widget)
        ping_table.setSpacing(15)
        ping_table.setContentsMargins(10, 10, 10, 10)
        
        # Add border styling
        ping_table_widget.setStyleSheet(ping_table_widget_style())
        
        # Row 0: Device labels
        col = 0
        self.ping_labels = {}
        for ip, name in devices.items():
            label = QLabel(name)
            label.setFont(self.font_label)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(label_muted() + " font-weight: bold;")
            ping_table.addWidget(label, 0, col)
            col += 1
        
        # Row 1: Status lights
        col = 0
        for ip in devices.keys():
            status_light = QLabel("●")
            status_light.setFont(QFont("Arial", 16))
            status_light.setAlignment(Qt.AlignCenter)
            status_light.setMinimumWidth(25)
            status_light.setStyleSheet("color: gray;")
            self.ping_labels[ip] = status_light
            ping_table.addWidget(status_light, 1, col)
            col += 1
        
        connect_layout.addWidget(ping_table_widget)
        
        # Robot reconnect row
        robot_row = QHBoxLayout()
        robot_row.setSpacing(12)
        robot_label = QLabel("Robot:")
        robot_label.setFont(self.font_label)
        robot_label.setStyleSheet(label_muted())
        robot_row.addWidget(robot_label)
        
        self.robot_status_light = QLabel("●")
        self.robot_status_light.setFont(QFont("Arial", 18))
        self.robot_status_light.setAlignment(Qt.AlignCenter)
        self.robot_status_light.setMinimumWidth(25)
        self.robot_status_light.setStyleSheet("color: gray;")
        robot_row.addWidget(self.robot_status_light)
        
        robot_row.addStretch()
        
        self.robot_reconnect_btn = QPushButton("🔄 Reconnect")
        self.robot_reconnect_btn.setFont(self.font_normal)
        self.robot_reconnect_btn.setMinimumHeight(35)
        self.robot_reconnect_btn.setMinimumWidth(120)
        self.robot_reconnect_btn.setStyleSheet(button_reconnect())
        self.robot_reconnect_btn.clicked.connect(self.on_robot_reconnect)
        robot_row.addWidget(self.robot_reconnect_btn)
        
        connect_layout.addLayout(robot_row)
        
        # Camera reconnect row
        camera_row = QHBoxLayout()
        camera_row.setSpacing(12)
        camera_label = QLabel("Camera:")
        camera_label.setFont(self.font_label)
        camera_label.setStyleSheet(label_muted())
        camera_row.addWidget(camera_label)
        
        self.camera_status_light = QLabel("●")
        self.camera_status_light.setFont(QFont("Arial", 18))
        self.camera_status_light.setAlignment(Qt.AlignCenter)
        self.camera_status_light.setMinimumWidth(25)
        self.camera_status_light.setStyleSheet("color: gray;")
        camera_row.addWidget(self.camera_status_light)
        
        camera_row.addStretch()
        
        self.camera_reconnect_btn = QPushButton("🔄 Reconnect")
        self.camera_reconnect_btn.setFont(self.font_normal)
        self.camera_reconnect_btn.setMinimumHeight(35)
        self.camera_reconnect_btn.setMinimumWidth(120)
        self.camera_reconnect_btn.setStyleSheet(button_reconnect())
        self.camera_reconnect_btn.clicked.connect(self.on_camera_reconnect)
        camera_row.addWidget(self.camera_reconnect_btn)
        
        connect_layout.addLayout(camera_row)
        
        connect_group.setLayout(connect_layout)
        layout.addWidget(connect_group)
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        
        # Create main layout for the tab and add scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        
        # Scene will be set by app_view (shared scene)
        self.scene = None
        self.pixmap_item = None
        self.click_history = []
        # Get max_history from controller if available, otherwise default
        self.max_history = getattr(self.controller, 'max_history', 20) if hasattr(self.controller, 'max_history') else 20
        
        # Setup network monitoring
        self._setup_network_monitoring()
    
    def on_frame_type_changed(self, state):
        """Handle frame type change"""
        self.view_state_changed(state)
        # Update button states
        if state == "paused orig":
            self.frame_type_original_btn.setChecked(True)
        elif state == "paused thres":
            self.frame_type_threshold_btn.setChecked(True)
        elif state == "paused contours":
            self.frame_type_contours_btn.setChecked(True)
    
    def on_centroids_toggled(self):
        """Handle centroids toggle"""
        enabled = self.show_centroids_btn.isChecked()
        if hasattr(self.controller, "set_show_centroids"):
            self.controller.set_show_centroids(enabled)
        else:
            logger.warning("Controller missing set_show_centroids")
    
    def on_bbox_toggled(self):
        """Handle bounding boxes toggle"""
        enabled = self.show_bbox_btn.isChecked()
        if hasattr(self.controller, "set_show_bounding_boxes"):
            self.controller.set_show_bounding_boxes(enabled)
        else:
            logger.warning("Controller missing set_show_bounding_boxes")
    
    def on_zoom_in(self):
        """Handle zoom in button"""
        if self.app_view and hasattr(self.app_view, 'vision_view'):
            vision_view = self.app_view.vision_view
            if vision_view.enable_zoom:
                vision_view.scale(1.2, 1.2)
                vision_view.scale_factor *= 1.2
    
    def on_zoom_out(self):
        """Handle zoom out button"""
        if self.app_view and hasattr(self.app_view, 'vision_view'):
            vision_view = self.app_view.vision_view
            if vision_view.enable_zoom:
                if vision_view.scale_factor > vision_view.min_scale:
                    vision_view.scale(1/1.2, 1/1.2)
                    vision_view.scale_factor /= 1.2
                    vision_view.scale_factor = max(vision_view.scale_factor, vision_view.min_scale)
    
    def on_reset_view(self):
        """Handle reset view button"""
        if self.app_view and hasattr(self.app_view, 'vision_view'):
            vision_view = self.app_view.vision_view
            vision_view.reset_view()
    
    def _update_exposure_time_from_camera(self):
        """Update exposure time slider and label from camera current value"""
        try:
            exposure_time = -1
            if hasattr(self.controller, 'get_exposure_time'):
                exposure_time = self.controller.get_exposure_time()
            
            if exposure_time > 0:
                # Clamp value to slider range
                exposure_time = max(self.exposure_slider.minimum(), 
                                  min(self.exposure_slider.maximum(), int(exposure_time)))
                self.exposure_slider.blockSignals(True)
                self.exposure_slider.setValue(int(exposure_time))
                self.exposure_slider.blockSignals(False)
                # Display in milliseconds
                exposure_ms = exposure_time / 1000.0
                self.exposure_value_label.setText(f"{exposure_ms:.2f} ms")
            else:
                # Camera not available or invalid value, set default
                default_value = 5000  # 5 ms default
                self.exposure_slider.blockSignals(True)
                self.exposure_slider.setValue(default_value)
                self.exposure_slider.blockSignals(False)
                self.exposure_value_label.setText(f"{default_value / 1000.0:.2f} ms")
        except Exception as e:
            logger.error(f"Error updating exposure time from camera: {e}")
            # Set default on error
            default_value = 5000
            self.exposure_slider.blockSignals(True)
            self.exposure_slider.setValue(default_value)
            self.exposure_slider.blockSignals(False)
            self.exposure_value_label.setText(f"{default_value / 1000.0:.2f} ms")
    
    def on_exposure_time_changed(self, value):
        """Handle exposure time slider value change"""
        try:
            # Update label (display in milliseconds)
            exposure_ms = value / 1000.0
            self.exposure_value_label.setText(f"{exposure_ms:.2f} ms")
            
            # Set camera exposure time (value is in microseconds)
            if hasattr(self.controller, 'set_exposure_time'):
                success = self.controller.set_exposure_time(float(value))
                if not success:
                    logger.warning(f"Failed to set exposure time to {value} µs")
        except Exception as e:
            logger.error(f"Error setting exposure time: {e}")
    
    def on_preview_image(self):
        """Capture latest frame from camera and show in secondary frame"""
        # Get latest frame from camera via controller
        frame = None
        try:
            if hasattr(self.controller, 'get_preview_frame'):
                frame = self.controller.get_preview_frame()
            
            if frame is None:
                logger.warning("No frame available from camera")
                return
            
            # Make a copy to ensure data is contiguous and safe
            import numpy as np
            frame = np.ascontiguousarray(frame)
            
            # Convert numpy array to QPixmap (same logic as update_display)
            if len(frame.shape) == 3:
                h, w, c = frame.shape
                qimg = QImage(frame.data, w, h, w * c, QImage.Format_RGB888)
            else:
                h, w = frame.shape
                qimg = QImage(frame.data, w, h, w, QImage.Format_Grayscale8)
            
            captured_pixmap = QPixmap.fromImage(qimg)
            
            # Display in secondary view
            self.secondary_scene.clear()
            self.secondary_scene.addPixmap(captured_pixmap)
            self.secondary_view.fitInView(self.secondary_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            
        except Exception as e:
            logger.error(f"Error capturing image: {e}")

    def on_capture_image(self):
        """Trigger capture/process and display on main view"""
        if hasattr(self.controller, "capture_process_frame"):
            success = self.controller.capture_process_frame()
            if not success:
                logger.error("Capture image failed")
        else:
            logger.error("Controller missing capture_process_frame")
    
    def on_motor_toggle_clicked(self):
        """Handle robot motor toggle button"""
        desired_state = self.motor_toggle_btn.isChecked()
        controller_has_method = hasattr(self.controller, "set_motor_power")
        if not controller_has_method:
            logger.error("Controller missing set_motor_power")
            self._update_motor_button(False)
            return
        try:
            success = self.controller.set_motor_power(desired_state)
        except Exception as exc:
            logger.error(f"Failed to toggle motor: {exc}")
            success = False
        if not success:
            desired_state = not desired_state
        final_state = desired_state
        if hasattr(self.controller, "is_motor_enabled"):
            final_state = self.controller.is_motor_enabled()
        self._update_motor_button(final_state)

    def _update_motor_button(self, enabled):
        """Update motor toggle button text/state"""
        self.motor_toggle_btn.blockSignals(True)
        self.motor_toggle_btn.setChecked(enabled)
        self.motor_toggle_btn.setText("Motor ON" if enabled else "Motor OFF")
        self.motor_toggle_btn.blockSignals(False)
    
    def on_move_robot(self):
        """Move robot to specified coordinates"""
        x = self.x_spinbox.value()
        y = self.y_spinbox.value()
        z = self.z_spinbox.value()
        u = self.u_spinbox.value()
        
        if hasattr(self.controller, 'move_robot_to_position'):
            self.controller.move_robot_to_position(x, y, z, u)
        else:
            logger.error("Controller missing move_robot_to_position method")
    
    def _preload_section(self, section_id):
        """Preload position values from section config into spinboxes"""
        if not hasattr(self.controller, 'get_section_capture_position'):
            logger.error("Controller does not have get_section_capture_position method")
            return
        
        position = self.controller.get_section_capture_position(section_id)
        if position is None or len(position) < 4:
            logger.warning(f"Section {section_id} does not have a valid capture_position")
            return
        
        self.x_spinbox.setValue(int(position[0]))
        self.y_spinbox.setValue(int(position[1]))
        self.z_spinbox.setValue(int(position[2]))
        self.u_spinbox.setValue(int(position[3]))
        logger.info(f"Preloaded position from section {section_id}: ({position[0]}, {position[1]}, {position[2]}, {position[3]})")
    
    def on_speed_selected(self, speed):
        """Handle speed selection"""
        if hasattr(self.controller, 'change_speed'):
            # Controller now handles speed name to percentage mapping
            self.controller.change_speed(speed)
        else:
            logger.warning("Controller missing change_speed method")
    
    def update_display(self, frame, draw_cells=True):
        """Update the display with the provided frame."""
        if frame is None or self.scene is None:
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
        
        # Adjust minimum scale of graphics view (if accessible)
        if self.app_view and hasattr(self.app_view, 'vision_view'):
            vision_view = self.app_view.vision_view
            vision_view.set_min_scale(self.scene.sceneRect())
    
    def update_status(self, message):
        """Update status message"""
        # Status is handled in app_view
        pass
    
    def update_position_info(self, img_x, img_y, robot_x, robot_y):
        """Update position labels and click history"""        
        # Add to history
        history_entry = f"Img ({img_x:.1f}, {img_y:.1f}) -> Robot ({robot_x:.2f}, {robot_y:.2f})"
        self.click_history.append(history_entry)
        if len(self.click_history) > self.max_history:
            self.click_history.pop(0)
        
        # Update history text box
        history_text_content = "\n".join(reversed(self.click_history))  # Most recent first
        self.history_text.setPlainText(history_text_content)
    
    def view_state_changed(self, state):
        """Handle view state change from UI"""
        self.controller.set_view_state(state)
    
    def update_section_display(self, section_id):
        """Update section display (no UI element, kept for compatibility)"""
        pass
    
    def _setup_network_monitoring(self):
        """Setup network monitoring connections"""
        if hasattr(self.controller, 'network_monitor'):
            self.controller.network_monitor.ping_status_changed.connect(self._on_ping_status_changed)
            self.controller.start_network_monitoring()
        
        # Connect to controller signals for connection status updates
        if hasattr(self.controller, 'robot_connection_status_changed'):
            self.controller.robot_connection_status_changed.connect(self._on_robot_connection_status_changed)
            # Emit initial status
            if hasattr(self.controller, 'is_robot_connected'):
                initial_status = self.controller.is_robot_connected()
                self._on_robot_connection_status_changed(initial_status)
        
        if hasattr(self.controller, 'camera_connection_status_changed'):
            self.controller.camera_connection_status_changed.connect(self._on_camera_connection_status_changed)
            # Emit initial status
            if hasattr(self.controller, 'is_camera_connected'):
                initial_status = self.controller.is_camera_connected()
                self._on_camera_connection_status_changed(initial_status)
    
    def _on_ping_status_changed(self, ip: str, is_online: bool):
        """Update ping status light for a device"""
        if ip in self.ping_labels:
            color = "green" if is_online else "red"
            self.ping_labels[ip].setStyleSheet(f"color: {color};")
    
    def _on_robot_connection_status_changed(self, is_connected: bool):
        """Update robot connection status UI"""
        color = "green" if is_connected else "red"
        self.robot_status_light.setStyleSheet(f"color: {color};")
    
    def _on_camera_connection_status_changed(self, is_connected: bool):
        """Update camera connection status UI"""
        color = "green" if is_connected else "red"
        self.camera_status_light.setStyleSheet(f"color: {color};")
        # Update exposure time when camera connects
        if is_connected:
            self._update_exposure_time_from_camera()
    
    def on_robot_reconnect(self):
        """Handle robot reconnect button click"""
        if hasattr(self.controller, 'reconnect_robot'):
            self.controller.reconnect_robot()
        else:
            logger.warning("Controller missing reconnect_robot method")
    
    def on_camera_reconnect(self):
        """Handle camera reconnect button click"""
        if hasattr(self.controller, 'reconnect_camera'):
            self.controller.reconnect_camera()
            # Update exposure time after reconnection
            self._update_exposure_time_from_camera()
        else:
            logger.warning("Controller missing reconnect_camera method")
