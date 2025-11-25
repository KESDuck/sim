from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QPushButton, QVBoxLayout, 
                           QHBoxLayout, QWidget, 
                           QSpinBox, QLabel, QGroupBox, QButtonGroup,
                           QGraphicsView, QGraphicsScene, QTextEdit, QScrollArea)
from PyQt5.QtGui import QImage, QPixmap, QFont

from utils.logger_config import get_logger

logger = get_logger("EngineerView")

class EngineerTabView(QWidget):
    """
    View component for the Engineer tab.
    Handles UI elements and interactions specific to the engineering interface.
    Based on A1 layout with frame controls, zoom, calibration tools, and robot controls.
    """
    def __init__(self, controller, font_medium, font_normal, app_view=None):
        super().__init__()
        self.controller = controller
        self.font_medium = font_medium
        self.font_normal = font_normal
        self.app_view = app_view  # Store reference to app_view for accessing vision_view
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
        frame_group = QGroupBox("Frame view controls")
        frame_group.setFont(self.font_medium)
        frame_layout = QVBoxLayout()
        frame_layout.setSpacing(15)
        
        # Frame type buttons
        frame_type_layout = QHBoxLayout()
        frame_type_label = QLabel("Frame:")
        frame_type_label.setFont(self.font_medium)
        frame_type_layout.addWidget(frame_type_label)
        
        self.frame_type_button_group = QButtonGroup()
        self.frame_type_original_btn = QPushButton("🖼️ Original")
        self.frame_type_original_btn.setFont(self.font_medium)
        self.frame_type_original_btn.setCheckable(True)
        self.frame_type_original_btn.setChecked(True)
        self.frame_type_original_btn.setMinimumHeight(35)
        self.frame_type_original_btn.setMinimumWidth(100)
        self.frame_type_original_btn.clicked.connect(lambda: self.on_frame_type_changed("paused orig"))
        
        self.frame_type_threshold_btn = QPushButton("🔲 Threshold")
        self.frame_type_threshold_btn.setFont(self.font_medium)
        self.frame_type_threshold_btn.setCheckable(True)
        self.frame_type_threshold_btn.setMinimumHeight(35)
        self.frame_type_threshold_btn.setMinimumWidth(100)
        self.frame_type_threshold_btn.clicked.connect(lambda: self.on_frame_type_changed("paused thres"))
        
        self.frame_type_contours_btn = QPushButton("📐 Contours")
        self.frame_type_contours_btn.setFont(self.font_medium)
        self.frame_type_contours_btn.setCheckable(True)
        self.frame_type_contours_btn.setMinimumHeight(35)
        self.frame_type_contours_btn.setMinimumWidth(100)
        self.frame_type_contours_btn.clicked.connect(lambda: self.on_frame_type_changed("paused contours"))
        
        self.frame_type_button_group.addButton(self.frame_type_original_btn, 0)
        self.frame_type_button_group.addButton(self.frame_type_threshold_btn, 1)
        self.frame_type_button_group.addButton(self.frame_type_contours_btn, 2)
        
        frame_type_layout.addWidget(self.frame_type_original_btn)
        frame_type_layout.addWidget(self.frame_type_threshold_btn)
        frame_type_layout.addWidget(self.frame_type_contours_btn)
        frame_type_layout.addStretch()
        frame_layout.addLayout(frame_type_layout)
        
        # Show centroids and bounding boxes
        centroids_layout = QHBoxLayout()
        centroids_label = QLabel("Show:")
        centroids_label.setFont(self.font_medium)
        centroids_layout.addWidget(centroids_label)
        
        self.show_centroids_btn = QPushButton("📍 Centroids")
        self.show_centroids_btn.setFont(self.font_medium)
        self.show_centroids_btn.setCheckable(True)
        self.show_centroids_btn.setChecked(True)
        self.show_centroids_btn.setMinimumHeight(35)
        self.show_centroids_btn.setMinimumWidth(120)
        self.show_centroids_btn.clicked.connect(self.on_centroids_toggled)
        
        self.show_bbox_btn = QPushButton("📦 Bounding Boxes")
        self.show_bbox_btn.setFont(self.font_medium)
        self.show_bbox_btn.setCheckable(True)
        self.show_bbox_btn.setChecked(True)
        self.show_bbox_btn.setMinimumHeight(35)
        self.show_bbox_btn.setMinimumWidth(120)
        self.show_bbox_btn.clicked.connect(self.on_bbox_toggled)
        
        centroids_layout.addWidget(self.show_centroids_btn)
        centroids_layout.addWidget(self.show_bbox_btn)
        centroids_layout.addStretch()
        frame_layout.addLayout(centroids_layout)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(10)
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_in_button.setFont(self.font_medium)
        self.zoom_in_button.setMinimumHeight(35)
        self.zoom_in_button.clicked.connect(self.on_zoom_in)
        
        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_out_button.setFont(self.font_medium)
        self.zoom_out_button.setMinimumHeight(35)
        self.zoom_out_button.clicked.connect(self.on_zoom_out)
        
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.setFont(self.font_medium)
        self.reset_view_button.setMinimumHeight(35)
        self.reset_view_button.clicked.connect(self.on_reset_view)
        
        self.save_image_button = QPushButton("Save image")
        self.save_image_button.setFont(self.font_medium)
        self.save_image_button.setMinimumHeight(35)
        self.save_image_button.clicked.connect(self.controller.save_current_frame)
        
        zoom_layout.addWidget(self.zoom_in_button)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.reset_view_button)
        zoom_layout.addWidget(self.save_image_button)
        zoom_layout.addStretch()
        frame_layout.addLayout(zoom_layout)
        
        frame_group.setLayout(frame_layout)
        layout.addWidget(frame_group)
        
        # Calibration tools
        calib_group = QGroupBox("Calibration tools")
        calib_group.setFont(self.font_medium)
        calib_layout = QVBoxLayout()
        calib_layout.setSpacing(15)
        
        # Capture image button
        self.capture_image_button = QPushButton("Capture image")
        self.capture_image_button.setFont(self.font_medium)
        self.capture_image_button.setMinimumHeight(35)
        self.capture_image_button.clicked.connect(self.on_capture_image)
        calib_layout.addWidget(self.capture_image_button)
        
        # Secondary frame for captured image
        secondary_frame_group = QGroupBox("Captured image")
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
        
        # Click history
        history_group = QGroupBox("Click History")
        history_group.setFont(self.font_medium)
        history_layout = QVBoxLayout()
        self.history_text = QTextEdit()
        self.history_text.setFont(self.font_normal)
        self.history_text.setReadOnly(False)
        self.history_text.setMinimumHeight(150)
        self.history_text.setMaximumHeight(200)
        self.history_text.setPlaceholderText("Click history will appear here...")
        history_layout.addWidget(self.history_text)
        history_group.setLayout(history_layout)
        calib_layout.addWidget(history_group)
        
        # Robot move controls
        move_group = QGroupBox("Robot move to point")
        move_group.setFont(self.font_medium)
        move_layout = QVBoxLayout()
        move_layout.setSpacing(10)
        
        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("X:"))
        self.x_spinbox = QSpinBox()
        self.x_spinbox.setFont(self.font_medium)
        self.x_spinbox.setRange(-10000, 10000)
        self.x_spinbox.setValue(0)
        self.x_spinbox.setMinimumHeight(35)
        coord_layout.addWidget(self.x_spinbox)
        
        coord_layout.addWidget(QLabel("Y:"))
        self.y_spinbox = QSpinBox()
        self.y_spinbox.setFont(self.font_medium)
        self.y_spinbox.setRange(-10000, 10000)
        self.y_spinbox.setValue(0)
        self.y_spinbox.setMinimumHeight(35)
        coord_layout.addWidget(self.y_spinbox)
        
        coord_layout.addWidget(QLabel("Z:"))
        self.z_spinbox = QSpinBox()
        self.z_spinbox.setFont(self.font_medium)
        self.z_spinbox.setRange(-10000, 10000)
        self.z_spinbox.setValue(0)
        self.z_spinbox.setMinimumHeight(35)
        coord_layout.addWidget(self.z_spinbox)
        move_layout.addLayout(coord_layout)
        
        self.move_button = QPushButton("Move")
        self.move_button.setFont(self.font_medium)
        self.move_button.setMinimumHeight(35)
        self.move_button.clicked.connect(self.on_move_robot)
        move_layout.addWidget(self.move_button)
        
        move_group.setLayout(move_layout)
        layout.addWidget(move_group)
        
        layout.addStretch()
        
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
        self.max_history = 20
    
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
        # This is handled in controller's frame preparation
        pass
    
    def on_bbox_toggled(self):
        """Handle bounding boxes toggle"""
        # This is handled in controller's frame preparation
        pass
    
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
    
    def on_capture_image(self):
        """Capture latest frame from camera and show in secondary frame"""
        # Get latest frame from camera
        frame = None
        try:
            # Try to get frame from camera directly (gets latest frame)
            if hasattr(self.controller, 'vision') and hasattr(self.controller.vision, 'camera'):
                frame = self.controller.vision.camera.get_frame()
            
            # If that fails, try to get the stored frame
            if frame is None and hasattr(self.controller, 'vision'):
                frame = self.controller.vision.frame_camera_stored
            
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
    
    def on_move_robot(self):
        """Move robot to specified coordinates"""
        x = self.x_spinbox.value()
        y = self.y_spinbox.value()
        z = self.z_spinbox.value()
        # TODO: Implement robot move command
        logger.info(f"Move robot to ({x}, {y}, {z})")
    
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
