"""
PyQt5 Layout Demo A1 - Vision Control Interface (Touch Screen Optimized)
Enlarged UI elements for easier viewing and use on touch screens.
"""

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QSpinBox, 
                             QComboBox, QTabWidget, QGraphicsView,
                             QGraphicsScene, QCheckBox, QGroupBox, QListWidget,
                             QSplitter, QFrame, QFileDialog, QButtonGroup,
                             QGridLayout, QTextEdit)
from PyQt5.QtCore import Qt, QRectF, QLineF, QPointF
from PyQt5.QtGui import QPixmap, QColor, QPen, QBrush, QFont
from PyQt5.QtWidgets import QGraphicsLineItem


class VisionGraphicsView(QGraphicsView):
    """Enhanced GraphicsView for vision display with zoom and pan"""
    def __init__(self, parent=None, enable_pan=False):
        super().__init__(parent)
        self.enable_pan = enable_pan
        self.enable_zoom = True  # Enable zoom by default
        self.enable_click = True  # Enable click by default
        self.setDragMode(QGraphicsView.ScrollHandDrag if enable_pan else QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale_factor = 1.0
        self.min_scale = 1.0
        self.last_press_pos = None
        self.last_press_button = None
        
    def set_pan_enabled(self, enabled):
        """Enable or disable panning"""
        self.enable_pan = enabled
        self.setDragMode(QGraphicsView.ScrollHandDrag if enabled else QGraphicsView.NoDrag)
    
    def set_zoom_enabled(self, enabled):
        """Enable or disable zoom"""
        self.enable_zoom = enabled
    
    def set_click_enabled(self, enabled):
        """Enable or disable click handling"""
        self.enable_click = enabled
        
    def wheelEvent(self, event):
        """Handle mouse wheel zoom"""
        if not self.enable_zoom:
            return  # Disable zoom in operator tab
        
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor
        
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            if self.scale_factor > self.min_scale:
                zoom_factor = zoom_out_factor
            else:
                return
        
        self.scale(zoom_factor, zoom_factor)
        self.scale_factor *= zoom_factor
        self.scale_factor = max(self.scale_factor, self.min_scale)
    
    def mousePressEvent(self, event):
        """Handle mouse click for calibration point selection or pan"""
        if not self.enable_click:
            # Disable click handling in operator tab
            super().mousePressEvent(event)
            return
        
        if self.enable_pan and event.button() == Qt.LeftButton:
            # Store press position to detect if it's a click or drag
            self.last_press_pos = event.pos()
            self.last_press_button = event.button()
            # Allow panning to work
            super().mousePressEvent(event)
        elif not self.enable_pan and event.button() == Qt.LeftButton:
            # Pan disabled - direct click handling
            scene_pos = self.mapToScene(event.pos())
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'on_image_clicked'):
                self.main_window.on_image_clicked(scene_pos)
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release - detect clicks vs drags when pan is enabled"""
        if not self.enable_click:
            # Disable click handling in operator tab
            super().mouseReleaseEvent(event)
            return
        
        if self.enable_pan and event.button() == self.last_press_button == Qt.LeftButton and self.last_press_pos:
            # Check if this was a click (little movement) or a pan (significant movement)
            move_distance = (event.pos() - self.last_press_pos).manhattanLength() if self.last_press_pos else 0
            if move_distance < 5:  # Threshold: if moved less than 5 pixels, treat as click
                # It was a click, not a pan - handle calibration
                scene_pos = self.mapToScene(event.pos())
                if hasattr(self, 'main_window') and hasattr(self.main_window, 'on_image_clicked'):
                    self.main_window.on_image_clicked(scene_pos)
            self.last_press_pos = None
            self.last_press_button = None
        super().mouseReleaseEvent(event)


class LayoutDemo(QMainWindow):
    """Main application window with split layout"""
    
    def __init__(self):
        super().__init__()
        self.recorded_points = []
        self.live_view_active = False
        self.is_inserting = False
        self.current_state = "Idle"
        self.current_mode = "Normal"
        self.captured_image = None
        self.selected_section = 1
        self.click_history = []  # Store last N clicks
        self.max_history = 20  # Maximum number of history entries
        self.cross_marker = None  # Store reference to cross marker items
        
        # Touch-optimized font sizes
        self.font_large = QFont()
        self.font_large.setPointSize(24)
        self.font_medium = QFont()
        self.font_medium.setPointSize(18)
        self.font_normal = QFont()
        self.font_normal.setPointSize(14)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components"""
        self.setWindowTitle("Vision Control Interface Demo (Touch Optimized)")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
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
        
        # Setup demo image
        self.setup_demo_image()
        
        # Initialize control states
        self.update_control_states()
    
    def create_left_panel(self):
        """Create left panel with tabs"""
        tab_widget = QTabWidget()
        tab_widget.setFont(self.font_medium)
        self.tab_widget = tab_widget  # Store reference
        
        # Create tabs
        operator_tab = self.create_operator_tab()
        engineer_tab = self.create_engineer_tab()
        
        tab_widget.addTab(operator_tab, "Operator")
        tab_widget.addTab(engineer_tab, "Engineer")
        
        # Connect tab change signal to update pan mode
        tab_widget.currentChanged.connect(self.on_tab_changed)
        
        return tab_widget
    
    def create_operator_tab(self):
        """Create Operator tab with simple controls"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)
        
        # Section selection
        section_group = QGroupBox("Section selection")
        section_group.setFont(self.font_medium)
        section_layout = QVBoxLayout()
        section_layout.setSpacing(10)
        
        # Create 3x3 grid of section buttons
        section_grid = QGridLayout()
        section_grid.setSpacing(8)
        self.section_button_group = QButtonGroup()
        self.section_buttons = []
        
        # Create 9 buttons in a 3x3 grid
        for i in range(9):
            btn = QPushButton(str(i + 1))
            btn.setFont(self.font_medium)
            btn.setCheckable(True)
            btn.setMinimumHeight(50)
            btn.setMinimumWidth(70)
            row = i // 3
            col = i % 3
            section_grid.addWidget(btn, row, col)
            self.section_button_group.addButton(btn, i + 1)
            self.section_buttons.append(btn)
            btn.clicked.connect(lambda checked, s=i+1: self.on_section_selected(s))
        
        # Select first button by default
        self.section_buttons[0].setChecked(True)
        section_layout.addLayout(section_grid)
        
        section_button_layout = QHBoxLayout()
        section_button_layout.setSpacing(10)
        self.go_to_section_button = QPushButton("Go to section")
        self.go_to_section_button.setFont(self.font_medium)
        self.go_to_section_button.setMinimumHeight(35)
        self.go_to_section_button.clicked.connect(self.on_go_to_section)
        self.insert_section_button = QPushButton("Only insert the section")
        self.insert_section_button.setFont(self.font_medium)
        self.insert_section_button.setMinimumHeight(35)
        self.insert_section_button.clicked.connect(self.on_insert_section)
        section_button_layout.addWidget(self.go_to_section_button)
        section_button_layout.addWidget(self.insert_section_button)
        section_layout.addLayout(section_button_layout)
        
        section_group.setLayout(section_layout)
        layout.addWidget(section_group)
        
        # Robot speed
        speed_group = QGroupBox("Robot speed")
        speed_group.setFont(self.font_medium)
        speed_layout = QHBoxLayout()
        speed_layout.setSpacing(10)
        speed_label = QLabel("Speed:")
        speed_label.setFont(self.font_medium)
        speed_layout.addWidget(speed_label)
        
        # Create button group for speed selection
        self.speed_button_group = QButtonGroup()
        self.speed_slow_button = QPushButton("Slow")
        self.speed_slow_button.setFont(self.font_medium)
        self.speed_slow_button.setCheckable(True)
        self.speed_slow_button.setMinimumHeight(50)
        self.speed_slow_button.setMinimumWidth(80)
        
        self.speed_normal_button = QPushButton("Normal")
        self.speed_normal_button.setFont(self.font_medium)
        self.speed_normal_button.setCheckable(True)
        self.speed_normal_button.setChecked(True)  # Default selection
        self.speed_normal_button.setMinimumHeight(50)
        self.speed_normal_button.setMinimumWidth(80)
        
        self.speed_fast_button = QPushButton("Fast")
        self.speed_fast_button.setFont(self.font_medium)
        self.speed_fast_button.setCheckable(True)
        self.speed_fast_button.setMinimumHeight(50)
        self.speed_fast_button.setMinimumWidth(80)
        
        # Add buttons to group (mutually exclusive)
        self.speed_button_group.addButton(self.speed_slow_button, 0)
        self.speed_button_group.addButton(self.speed_normal_button, 1)
        self.speed_button_group.addButton(self.speed_fast_button, 2)
        
        speed_layout.addWidget(self.speed_slow_button)
        speed_layout.addWidget(self.speed_normal_button)
        speed_layout.addWidget(self.speed_fast_button)
        speed_layout.addStretch()
        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)
        
        # Control buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        self.start_all_button = QPushButton("Start all")
        self.start_all_button.setFont(self.font_medium)
        self.start_all_button.setMinimumHeight(35)
        self.start_all_button.clicked.connect(self.on_start_all_clicked)
        button_layout.addWidget(self.start_all_button)
        
        self.stop_insertion_button = QPushButton("Stop insertion")
        self.stop_insertion_button.setFont(self.font_medium)
        self.stop_insertion_button.setMinimumHeight(35)
        self.stop_insertion_button.clicked.connect(self.on_stop_insertion_clicked)
        button_layout.addWidget(self.stop_insertion_button)
        
        layout.addLayout(button_layout)
        
        layout.addStretch()
        return tab
    
    def create_engineer_tab(self):
        """Create Engineer tab with advanced controls"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)
        
        # Frame view controls
        frame_group = QGroupBox("Frame view controls")
        frame_group.setFont(self.font_medium)
        frame_layout = QVBoxLayout()
        frame_layout.setSpacing(15)
        
        frame_type_layout = QHBoxLayout()
        frame_type_label = QLabel("Frame:")
        frame_type_label.setFont(self.font_medium)
        frame_type_layout.addWidget(frame_type_label)
        
        # Create button group for frame type (3 buttons)
        self.frame_type_button_group = QButtonGroup()
        self.frame_type_original_btn = QPushButton("🖼️ Original ")
        self.frame_type_original_btn.setFont(self.font_medium)
        self.frame_type_original_btn.setCheckable(True)
        self.frame_type_original_btn.setChecked(True)
        self.frame_type_original_btn.setMinimumHeight(35)
        self.frame_type_original_btn.setMinimumWidth(100)
        self.frame_type_original_btn.clicked.connect(lambda: self.on_frame_type_changed("Original"))
        
        self.frame_type_threshold_btn = QPushButton("🔲 Threshold ")
        self.frame_type_threshold_btn.setFont(self.font_medium)
        self.frame_type_threshold_btn.setCheckable(True)
        self.frame_type_threshold_btn.setMinimumHeight(35)
        self.frame_type_threshold_btn.setMinimumWidth(100)
        self.frame_type_threshold_btn.clicked.connect(lambda: self.on_frame_type_changed("Threshold"))
        
        self.frame_type_contours_btn = QPushButton("📐 Contours")
        self.frame_type_contours_btn.setFont(self.font_medium)
        self.frame_type_contours_btn.setCheckable(True)
        self.frame_type_contours_btn.setMinimumHeight(35)
        self.frame_type_contours_btn.setMinimumWidth(100)
        self.frame_type_contours_btn.clicked.connect(lambda: self.on_frame_type_changed("Contours"))
        
        self.frame_type_button_group.addButton(self.frame_type_original_btn, 0)
        self.frame_type_button_group.addButton(self.frame_type_threshold_btn, 1)
        self.frame_type_button_group.addButton(self.frame_type_contours_btn, 2)
        
        frame_type_layout.addWidget(self.frame_type_original_btn)
        frame_type_layout.addWidget(self.frame_type_threshold_btn)
        frame_type_layout.addWidget(self.frame_type_contours_btn)
        frame_type_layout.addStretch()
        frame_layout.addLayout(frame_type_layout)
        
        # Show centroids and bounding boxes as buttons
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
        self.show_centroids_btn.clicked.connect(self.on_centroids_toggled_btn)
        
        self.show_bbox_btn = QPushButton("📦 Bounding Boxes")
        self.show_bbox_btn.setFont(self.font_medium)
        self.show_bbox_btn.setCheckable(True)
        self.show_bbox_btn.setChecked(True)
        self.show_bbox_btn.setMinimumHeight(35)
        self.show_bbox_btn.setMinimumWidth(120)
        self.show_bbox_btn.clicked.connect(self.on_bbox_toggled_btn)
        
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
        self.save_image_button.clicked.connect(self.on_save_image)
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

        self.img_xy_label = QLabel("Img XY: -")
        self.img_xy_label.setFont(self.font_normal)
        self.robot_xy_label = QLabel("Robot XY: -")
        self.robot_xy_label.setFont(self.font_normal)
        
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
        self.history_text.setReadOnly(False)  # Allow copying
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
        return tab
    
    def create_right_panel(self):
        """Create right panel with vision display and status"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Vision display
        # Enable pan for engineer tab (will be toggled based on active tab)
        self.vision_view = VisionGraphicsView(enable_pan=False)
        self.vision_view.main_window = self  # Store reference to main window
        self.vision_scene = QGraphicsScene()
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
        self.state_mode_label = QLabel(f"State: {self.current_state} | Mode: {self.current_mode}")
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
        
        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        action_row.addWidget(separator1)
        
        action_row.addWidget(self.vision_status)
        
        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        action_row.addWidget(separator2)
        
        action_row.addWidget(self.general_status)
        action_row.addStretch()
        
        status_layout.addLayout(action_row)
        
        layout.addWidget(status_strip)
        return panel
    
    def setup_demo_image(self):
        """Setup a demo image for the vision display"""
        # Create a simple demo image
        pixmap = QPixmap(800, 600)
        pixmap.fill(QColor(50, 50, 50))
        
        # Add some demo content
        from PyQt5.QtGui import QPainter
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawRect(100, 100, 600, 400)
        painter.drawText(350, 300, "Vision Display Area")
        painter.end()
        
        # Set to scene
        self.vision_scene.clear()
        self.vision_scene.addPixmap(pixmap)
        self.vision_view.fitInView(QRectF(0, 0, 800, 600), Qt.KeepAspectRatio)
        # Reset cross marker when scene is cleared
        self.cross_marker = None
        
    def snap_to_half_pixel(self, coord):
        """Snap coordinate to nearest integer or 0.5 position"""
        return round(coord * 2) / 2.0
        
    def draw_cross_marker(self, scene_pos, cross_size=20):
        """Draw a cross marker at the clicked position"""
        # Remove old cross marker if exists
        if self.cross_marker:
            for item in self.cross_marker:
                self.vision_scene.removeItem(item)
        
        img_x, img_y = scene_pos.x(), scene_pos.y()
        
        # Create cross using two lines (horizontal and vertical)
        # Horizontal line
        h_line = QGraphicsLineItem(
            QLineF(img_x - cross_size / 2, img_y,
                   img_x + cross_size / 2, img_y)
        )
        h_line.setPen(QPen(QColor(255, 0, 0), 1))  # Red cross, 2px width
        h_line.setZValue(1000)  # Draw on top
        
        # Vertical line
        v_line = QGraphicsLineItem(
            QLineF(img_x, img_y - cross_size / 2,
                   img_x, img_y + cross_size / 2)
        )
        v_line.setPen(QPen(QColor(255, 0, 0), 1))  # Red cross, 2px width
        v_line.setZValue(1000)  # Draw on top
        
        # Add both lines to scene
        self.vision_scene.addItem(h_line)
        self.vision_scene.addItem(v_line)
        
        # Store references (we'll need to remove both later)
        self.cross_marker = [h_line, v_line]
        
    def on_image_clicked(self, scene_pos):
        """Handle image click for calibration"""
        # Snap to nearest integer or 0.5 position
        snapped_x = self.snap_to_half_pixel(scene_pos.x())
        snapped_y = self.snap_to_half_pixel(scene_pos.y())
        
        # Create snapped position
        snapped_pos = QPointF(snapped_x, snapped_y)
        img_x, img_y = snapped_x, snapped_y
        self.last_click_pos = snapped_pos
        
        # Draw cross marker at snapped position
        self.draw_cross_marker(snapped_pos)
        
        # Simulate robot XY conversion (in real app, this would use homography)
        robot_x = img_x * 0.1  # Example conversion
        robot_y = img_y * 0.1
        self.img_xy_label.setText(f"Img XY: ({img_x:.1f}, {img_y:.1f})")
        self.robot_xy_label.setText(f"Robot XY: ({robot_x:.1f}, {robot_y:.1f})")
        self.general_status.setText(f"General: Clicked at img ({img_x:.1f}, {img_y:.1f}), robot ({robot_x:.1f}, {robot_y:.1f})")
        
        # Add to history
        history_entry = f"Img ({img_x:.1f}, {img_y:.1f}) -> Robot ({robot_x:.1f}, {robot_y:.1f})"
        self.click_history.append(history_entry)
        if len(self.click_history) > self.max_history:
            self.click_history.pop(0)
        
        # Update history text box (if it exists)
        if hasattr(self, 'history_text') and self.history_text:
            history_text_content = "\n".join(reversed(self.click_history))  # Most recent first
            self.history_text.setPlainText(history_text_content)
    
    def on_tab_changed(self, index):
        """Handle tab change - enable/disable pan, zoom, and click based on tab"""
        if index == 1:  # Engineer tab
            self.vision_view.set_pan_enabled(True)
            self.vision_view.set_zoom_enabled(True)
            self.vision_view.set_click_enabled(True)
            # Enable zoom buttons
            self.zoom_in_button.setEnabled(True)
            self.zoom_out_button.setEnabled(True)
            self.reset_view_button.setEnabled(True)
        else:  # Operator tab
            self.vision_view.set_pan_enabled(False)
            self.vision_view.set_zoom_enabled(False)
            self.vision_view.set_click_enabled(False)
            # Disable zoom buttons
            self.zoom_in_button.setEnabled(False)
            self.zoom_out_button.setEnabled(False)
            self.reset_view_button.setEnabled(False)
            self.on_reset_view()

    
    def update_control_states(self):
        """Update enabled/disabled state of controls based on current state"""
        is_running = self.current_state == "Running" or self.is_inserting
        is_idle = self.current_state == "Idle" and not self.is_inserting
        
        # Section buttons
        for btn in self.section_buttons:
            btn.setEnabled(not is_running)
        
        # Speed buttons
        self.speed_slow_button.setEnabled(not is_running)
        self.speed_normal_button.setEnabled(not is_running)
        self.speed_fast_button.setEnabled(not is_running)
        
        # Control buttons
        self.start_all_button.setEnabled(is_idle)
        self.go_to_section_button.setEnabled(is_idle)
        self.insert_section_button.setEnabled(is_idle)
        # Stop button always enabled
        self.stop_insertion_button.setEnabled(True)
        
        # Engineer tab controls (only enable when idle and not in calibration mode)
        engineer_enabled = is_idle and self.current_mode != "Calibration"
        self.frame_type_original_btn.setEnabled(engineer_enabled)
        self.frame_type_threshold_btn.setEnabled(engineer_enabled)
        self.frame_type_contours_btn.setEnabled(engineer_enabled)
        self.show_centroids_btn.setEnabled(engineer_enabled)
        self.show_bbox_btn.setEnabled(engineer_enabled)
        self.capture_image_button.setEnabled(not is_running)
        self.move_button.setEnabled(not is_running)
        self.x_spinbox.setEnabled(not is_running)
        self.y_spinbox.setEnabled(not is_running)
        self.z_spinbox.setEnabled(not is_running)
    
    def on_start_all_clicked(self):
        """Handle start all button click"""
        self.is_inserting = True
        self.current_status.setText("Status: Running")
        self.current_state = "Running"
        self.state_mode_label.setText(f"State: {self.current_state} | Mode: {self.current_mode}")
        self.robot_status.setText("Robot: Running")
        self.update_control_states()
    
    def on_stop_insertion_clicked(self):
        """Handle stop insertion button click"""
        self.is_inserting = False
        self.current_status.setText("Status: Stopped")
        self.current_state = "Idle"
        self.state_mode_label.setText(f"State: {self.current_state} | Mode: {self.current_mode}")
        self.robot_status.setText("Robot: Stopping")
        self.update_control_states()
    
    def on_section_selected(self, section):
        """Handle section button selection"""
        self.selected_section = section
    
    def on_go_to_section(self):
        """Handle go to section button click"""
        section = self.selected_section
        self.robot_status.setText(f"Robot: Moving to section {section}")
        self.general_status.setText(f"General: Moving to section {section}")
    
    def on_insert_section(self):
        """Handle insert section button click"""
        section = self.selected_section
        self.is_inserting = True
        self.update_control_states()
        self.current_status.setText(f"Status: Inserting section {section}")
        self.robot_status.setText(f"Robot: Inserting section {section}")
    
    def on_frame_type_changed(self, text):
        """Handle frame type change"""
        self.vision_status.setText(f"Vision: {text} mode")
    
    def on_centroids_toggled_btn(self):
        """Handle centroids button toggle"""
        if self.show_centroids_btn.isChecked():
            self.vision_status.setText("Vision: Centroids ON")
        else:
            self.vision_status.setText("Vision: Centroids OFF")
    
    def on_bbox_toggled_btn(self):
        """Handle bounding boxes button toggle"""
        if self.show_bbox_btn.isChecked():
            self.vision_status.setText("Vision: Bounding boxes ON")
        else:
            self.vision_status.setText("Vision: Bounding boxes OFF")
    
    def on_live_view_toggled(self, checked):
        """Handle live view toggle"""
        self.live_view_active = checked
        if checked:
            self.live_view_button.setText("Live view: ON")
            self.vision_status.setText("Vision: Live view active")
        else:
            self.live_view_button.setText("Live view: OFF")
            self.vision_status.setText("Vision: Live view inactive")
    
    def on_zoom_in(self):
        """Handle zoom in button"""
        if self.vision_view.enable_zoom:
            self.vision_view.scale(1.2, 1.2)
            self.vision_view.scale_factor *= 1.2
    
    def on_zoom_out(self):
        """Handle zoom out button"""
        if self.vision_view.enable_zoom:
            if self.vision_view.scale_factor > self.vision_view.min_scale:
                self.vision_view.scale(1/1.2, 1/1.2)
                self.vision_view.scale_factor /= 1.2
                self.vision_view.scale_factor = max(self.vision_view.scale_factor, self.vision_view.min_scale)
    
    def on_reset_view(self):
        """Handle reset view button - reset zoom and fit image to view"""
        if self.vision_scene.items():
            # Reset transformation
            self.vision_view.resetTransform()
            self.vision_view.scale_factor = 1.0
            # Fit image to view
            items_rect = self.vision_scene.itemsBoundingRect()
            if not items_rect.isEmpty():
                self.vision_view.fitInView(items_rect, Qt.KeepAspectRatio)
    
    def on_capture_image(self):
        """Capture current image and show in secondary frame"""
        if self.vision_scene.items():
            # Get the current pixmap from the scene
            pixmap_item = self.vision_scene.items()[0]
            if hasattr(pixmap_item, 'pixmap'):
                self.captured_image = pixmap_item.pixmap()
                self.secondary_scene.clear()
                self.secondary_scene.addPixmap(self.captured_image)
                self.secondary_view.fitInView(self.secondary_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                self.general_status.setText("General: Image captured")
    
    def on_move_robot(self):
        """Move robot to specified coordinates"""
        x = self.x_spinbox.value()
        y = self.y_spinbox.value()
        z = self.z_spinbox.value()
        self.robot_status.setText(f"Robot: Moving to ({x}, {y}, {z})")
        self.general_status.setText(f"General: Moving robot to ({x}, {y}, {z})")
    
    def on_save_image(self):
        """Save current image to file"""
        if self.vision_scene.items():
            pixmap_item = self.vision_scene.items()[0]
            if hasattr(pixmap_item, 'pixmap'):
                filename, _ = QFileDialog.getSaveFileName(
                    self, "Save Image", "", "Image Files (*.png *.jpg *.bmp)")
                if filename:
                    pixmap_item.pixmap().save(filename)
                    self.general_status.setText(f"General: Image saved to {filename}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = LayoutDemo()
    window.show()
    
    sys.exit(app.exec_())

