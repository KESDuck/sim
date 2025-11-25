"""
PyQt5 Layout Demo - Vision Control Interface
A self-contained demo showcasing the main application layout:
- Split view: Left (tabs) and Right (vision + status)
- Operator tab: Simple controls for operation
- Engineer tab: Advanced vision and calibration tools
- Shared vision display with status strip
"""

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QSpinBox, 
                             QComboBox, QTextEdit, QTabWidget, QGraphicsView,
                             QGraphicsScene, QCheckBox, QGroupBox, QListWidget,
                             QSplitter, QFrame)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPixmap, QColor, QPen, QBrush


class VisionGraphicsView(QGraphicsView):
    """Enhanced GraphicsView for vision display with zoom and pan"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale_factor = 1.0
        self.min_scale = 1.0
        
    def wheelEvent(self, event):
        """Handle mouse wheel zoom"""
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
        """Handle mouse click for calibration point selection"""
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            # Call callback on main window
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'on_image_clicked'):
                self.main_window.on_image_clicked(scene_pos)
        super().mousePressEvent(event)


class LayoutDemo(QMainWindow):
    """Main application window with split layout"""
    
    def __init__(self):
        super().__init__()
        self.recorded_points = []
        self.live_view_active = False
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components"""
        self.setWindowTitle("Vision Control Interface Demo")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
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
        splitter.setSizes([400, 1000])
        
        # Setup demo image
        self.setup_demo_image()
    
    def create_left_panel(self):
        """Create left panel with tabs"""
        tab_widget = QTabWidget()
        
        # Create tabs
        operator_tab = self.create_operator_tab()
        engineer_tab = self.create_engineer_tab()
        
        tab_widget.addTab(operator_tab, "Operator")
        tab_widget.addTab(engineer_tab, "Engineer")
        
        return tab_widget
    
    def create_operator_tab(self):
        """Create Operator tab with simple controls"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Section selection
        section_group = QGroupBox("Section selection")
        section_layout = QHBoxLayout()
        section_layout.addWidget(QLabel("Section:"))
        self.section_spinbox = QSpinBox()
        self.section_spinbox.setRange(1, 9)
        self.section_spinbox.setValue(1)
        section_layout.addWidget(self.section_spinbox)
        section_layout.addStretch()
        section_group.setLayout(section_layout)
        layout.addWidget(section_group)
        
        # Robot speed
        speed_group = QGroupBox("Robot speed")
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["Slow", "Normal", "Fast"])
        self.speed_combo.setCurrentText("Normal")
        speed_layout.addWidget(self.speed_combo)
        speed_layout.addStretch()
        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start whole plate")
        self.start_button.clicked.connect(self.on_start_clicked)
        self.stop_button = QPushButton("Stop current process")
        self.stop_button.clicked.connect(self.on_stop_clicked)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)
        
        # Small preview
        preview_group = QGroupBox("Small preview")
        preview_layout = QVBoxLayout()
        preview_label = QLabel("Last processed frame")
        preview_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(preview_label)
        
        # Small preview graphics view
        self.preview_view = QGraphicsView()
        self.preview_scene = QGraphicsScene()
        self.preview_view.setScene(self.preview_scene)
        self.preview_view.setMinimumHeight(150)
        preview_layout.addWidget(self.preview_view)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Operation status
        status_group = QGroupBox("Operation status")
        status_layout = QVBoxLayout()
        self.operator_status = QTextEdit()
        self.operator_status.setReadOnly(True)
        self.operator_status.setMaximumHeight(100)
        self.operator_status.setPlainText("Ready. Waiting for start command...")
        status_layout.addWidget(self.operator_status)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        layout.addStretch()
        return tab
    
    def create_engineer_tab(self):
        """Create Engineer tab with advanced controls"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Frame view controls
        frame_group = QGroupBox("Frame view controls")
        frame_layout = QVBoxLayout()
        
        frame_type_layout = QHBoxLayout()
        frame_type_layout.addWidget(QLabel("Frame type:"))
        self.frame_type_combo = QComboBox()
        self.frame_type_combo.addItems(["Original", "Threshold", "Contours"])
        self.frame_type_combo.currentTextChanged.connect(self.on_frame_type_changed)
        frame_type_layout.addWidget(self.frame_type_combo)
        frame_type_layout.addStretch()
        frame_layout.addLayout(frame_type_layout)
        
        self.show_centroids_check = QCheckBox("Show centroids & bounding boxes")
        self.show_centroids_check.setChecked(True)
        self.show_centroids_check.stateChanged.connect(self.on_centroids_toggled)
        frame_layout.addWidget(self.show_centroids_check)
        
        self.live_view_button = QPushButton("Live view: OFF")
        self.live_view_button.setCheckable(True)
        self.live_view_button.clicked.connect(self.on_live_view_toggled)
        frame_layout.addWidget(self.live_view_button)
        
        frame_group.setLayout(frame_layout)
        layout.addWidget(frame_group)
        
        # Calibration tools
        calib_group = QGroupBox("Calibration tools")
        calib_layout = QVBoxLayout()
        
        calib_label = QLabel("Click image to set cross & show XY")
        calib_layout.addWidget(calib_label)
        
        calib_button_layout = QHBoxLayout()
        self.record_button = QPushButton("Record point (R)")
        self.record_button.setShortcut(Qt.Key_R)
        self.record_button.clicked.connect(self.on_record_point)
        self.clear_points_button = QPushButton("Clear points")
        self.clear_points_button.clicked.connect(self.on_clear_points)
        calib_button_layout.addWidget(self.record_button)
        calib_button_layout.addWidget(self.clear_points_button)
        calib_layout.addLayout(calib_button_layout)
        
        # Points list
        self.points_list = QListWidget()
        self.points_list.setMaximumHeight(150)
        calib_layout.addWidget(self.points_list)
        
        calib_group.setLayout(calib_layout)
        layout.addWidget(calib_group)
        
        # Robot test controls (optional)
        test_group = QGroupBox("Robot test controls")
        test_layout = QHBoxLayout()
        self.jump_button = QPushButton("Jump to cross")
        self.insert_button = QPushButton("Insert at cross")
        test_layout.addWidget(self.jump_button)
        test_layout.addWidget(self.insert_button)
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)
        
        layout.addStretch()
        return tab
    
    def create_right_panel(self):
        """Create right panel with vision display and status"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Vision display
        self.vision_view = VisionGraphicsView()
        self.vision_view.main_window = self  # Store reference to main window
        self.vision_scene = QGraphicsScene()
        self.vision_view.setScene(self.vision_scene)
        layout.addWidget(self.vision_view)
        
        # Status strip
        status_strip = QFrame()
        status_strip.setFrameShape(QFrame.StyledPanel)
        status_strip.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        status_layout = QHBoxLayout(status_strip)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        self.robot_status = QLabel("Robot: Idle")
        self.vision_status = QLabel("Vision: Ready")
        self.general_status = QLabel("General: OK")
        
        status_layout.addWidget(self.robot_status)
        status_layout.addWidget(QFrame())  # Separator
        status_layout.addWidget(self.vision_status)
        status_layout.addWidget(QFrame())  # Separator
        status_layout.addWidget(self.general_status)
        status_layout.addStretch()
        
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
        
        # Also set to preview
        self.preview_scene.clear()
        self.preview_scene.addPixmap(pixmap.scaled(200, 150, Qt.KeepAspectRatio))
    
    def on_image_clicked(self, scene_pos):
        """Handle image click for calibration"""
        x, y = scene_pos.x(), scene_pos.y()
        self.last_click_pos = scene_pos
        self.general_status.setText(f"General: Clicked at ({x:.1f}, {y:.1f})")
    
    def on_start_clicked(self):
        """Handle start button click"""
        section = self.section_spinbox.value()
        speed = self.speed_combo.currentText()
        self.operator_status.setPlainText(f"Starting section {section} at {speed} speed...")
        self.robot_status.setText("Robot: Running")
    
    def on_stop_clicked(self):
        """Handle stop button click"""
        self.operator_status.setPlainText("Stop command issued. Process stopping...")
        self.robot_status.setText("Robot: Stopping")
    
    def on_frame_type_changed(self, text):
        """Handle frame type change"""
        self.vision_status.setText(f"Vision: {text} mode")
    
    def on_centroids_toggled(self, state):
        """Handle centroids checkbox toggle"""
        if state == Qt.Checked:
            self.vision_status.setText("Vision: Centroids ON")
        else:
            self.vision_status.setText("Vision: Centroids OFF")
    
    def on_live_view_toggled(self, checked):
        """Handle live view toggle"""
        self.live_view_active = checked
        if checked:
            self.live_view_button.setText("Live view: ON")
            self.vision_status.setText("Vision: Live view active")
        else:
            self.live_view_button.setText("Live view: OFF")
            self.vision_status.setText("Vision: Live view inactive")
    
    def on_record_point(self):
        """Record current calibration point"""
        if hasattr(self, 'last_click_pos'):
            x, y = self.last_click_pos.x(), self.last_click_pos.y()
            point_text = f"Point {len(self.recorded_points) + 1}: ({x:.1f}, {y:.1f})"
            self.recorded_points.append((x, y))
            self.points_list.addItem(point_text)
            self.general_status.setText(f"General: Recorded {point_text}")
    
    def on_clear_points(self):
        """Clear all recorded points"""
        self.recorded_points.clear()
        self.points_list.clear()
        self.general_status.setText("General: Points cleared")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = LayoutDemo()
    window.show()
    
    sys.exit(app.exec_())

