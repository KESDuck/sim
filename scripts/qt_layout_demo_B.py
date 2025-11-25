"""
PyQt5 Layout Demo B - Modern HMI Design
A completely new design with card-based layout for:
- Operator controls
- Status monitoring
- Calibration tools
"""

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QSpinBox, 
                             QComboBox, QTextEdit, QGraphicsView, QGraphicsScene,
                             QCheckBox, QGroupBox, QFrame, QGridLayout, QDoubleSpinBox,
                             QSplitter, QTabWidget, QGraphicsPixmapItem)
from PyQt5.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QColor, QPen, QBrush, QPainter, QFont


class ZoomableGraphicsView(QGraphicsView):
    """Graphics view with zoom and click handling"""
    image_clicked = pyqtSignal(float, float)  # Emits (x, y) in scene coordinates
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 10.0
        
    def wheelEvent(self, event):
        """Handle mouse wheel zoom"""
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        
        new_scale = self.scale_factor * zoom_factor
        if self.min_scale <= new_scale <= self.max_scale:
            self.scale(zoom_factor, zoom_factor)
            self.scale_factor = new_scale
    
    def mousePressEvent(self, event):
        """Handle mouse click for calibration"""
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self.image_clicked.emit(scene_pos.x(), scene_pos.y())
        super().mousePressEvent(event)
    
    def reset_zoom(self):
        """Reset zoom to fit view"""
        self.resetTransform()
        self.scale_factor = 1.0
        if self.scene() and self.scene().items():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)


class LayoutDemoB(QMainWindow):
    """Main application window with modern card-based layout"""
    
    def __init__(self):
        super().__init__()
        self.is_inserting = False
        self.current_status = "Ready"
        self.current_state = "IDLE"
        self.current_mode = "IDLE MODE"
        self.current_frame_type = "original"
        self.show_centroids = True
        self.last_click_pos = None
        self.captured_image = None
        self.clicked_points = []  # List of (img_x, img_y, robot_x, robot_y) tuples
        
        # Demo data
        self.demo_centroids = []
        self.demo_contours = []
        
        self.init_ui()
        self.setup_demo_data()
        self.update_display()
    
    def init_ui(self):
        """Initialize UI components"""
        self.setWindowTitle("HMI Layout Demo B - Modern Design")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Apply modern styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            QSpinBox, QDoubleSpinBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                background-color: white;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #3498db;
            }
            QComboBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox {
                font-size: 13px;
                color: #2c3e50;
            }
            QLabel {
                color: #2c3e50;
                font-size: 13px;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Create splitter for left/right division
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left side: Control panels
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right side: Vision display
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions (35% left, 65% right)
        splitter.setSizes([500, 1100])
    
    def create_left_panel(self):
        """Create left panel with tabs"""
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                color: #2c3e50;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #3498db;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #d5dbdb;
            }
        """)
        
        # Create tabs
        operator_tab = self.create_operator_tab()
        status_tab = self.create_status_tab()
        calibration_tab = self.create_calibration_tab()
        
        tab_widget.addTab(operator_tab, "Operator")
        tab_widget.addTab(status_tab, "Status")
        tab_widget.addTab(calibration_tab, "Calibration")
        
        return tab_widget
    
    def create_operator_tab(self):
        """Create Operator tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Start all button
        self.start_all_btn = QPushButton("▶ Start All")
        self.start_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                font-size: 14px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.start_all_btn.clicked.connect(self.on_start_all)
        layout.addWidget(self.start_all_btn)
        
        # Section selection
        section_layout = QHBoxLayout()
        section_layout.addWidget(QLabel("Section:"))
        self.section_spinbox = QSpinBox()
        self.section_spinbox.setRange(1, 9)
        self.section_spinbox.setValue(1)
        self.section_spinbox.setEnabled(not self.is_inserting)
        section_layout.addWidget(self.section_spinbox)
        section_layout.addStretch()
        layout.addLayout(section_layout)
        
        # Go to section button
        self.go_to_section_btn = QPushButton("Go to Section")
        self.go_to_section_btn.clicked.connect(self.on_go_to_section)
        layout.addWidget(self.go_to_section_btn)
        
        # Insert section button
        self.insert_section_btn = QPushButton("Insert Section Only")
        self.insert_section_btn.clicked.connect(self.on_insert_section)
        layout.addWidget(self.insert_section_btn)
        
        # Robot speed
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Robot Speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["Slow", "Normal", "Fast"])
        self.speed_combo.setCurrentText("Normal")
        self.speed_combo.currentTextChanged.connect(self.on_speed_changed)
        speed_layout.addWidget(self.speed_combo)
        speed_layout.addStretch()
        layout.addLayout(speed_layout)
        
        # Stop insertion button
        self.stop_insertion_btn = QPushButton("⏹ Stop Insertion")
        self.stop_insertion_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                font-size: 14px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.stop_insertion_btn.clicked.connect(self.on_stop_insertion)
        layout.addWidget(self.stop_insertion_btn)
        
        # Current frame display label
        frame_label = QLabel("Current Frame (Inserting):")
        frame_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(frame_label)
        
        # Frame display area
        self.operator_frame_view = ZoomableGraphicsView()
        self.operator_frame_scene = QGraphicsScene()
        self.operator_frame_view.setScene(self.operator_frame_scene)
        self.operator_frame_view.setMinimumHeight(200)
        self.operator_frame_view.setMaximumHeight(200)
        layout.addWidget(self.operator_frame_view)
        
        layout.addStretch()
        return tab
    
    def create_status_tab(self):
        """Create Status monitoring tab - now just has Save Image button"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Save image button
        self.save_image_btn = QPushButton("💾 Save Image")
        self.save_image_btn.clicked.connect(self.on_save_image)
        layout.addWidget(self.save_image_btn)
        
        layout.addStretch()
        return tab
    
    def create_calibration_tab(self):
        """Create Calibration tools tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_in_btn = QPushButton("🔍+ Zoom In")
        zoom_in_btn.clicked.connect(self.on_zoom_in)
        zoom_out_btn = QPushButton("🔍- Zoom Out")
        zoom_out_btn.clicked.connect(self.on_zoom_out)
        reset_zoom_btn = QPushButton("↺ Reset Zoom")
        reset_zoom_btn.clicked.connect(self.on_reset_zoom)
        zoom_layout.addWidget(zoom_in_btn)
        zoom_layout.addWidget(zoom_out_btn)
        zoom_layout.addWidget(reset_zoom_btn)
        layout.addLayout(zoom_layout)
        
        # Frame type selection
        frame_type_layout = QHBoxLayout()
        frame_type_layout.addWidget(QLabel("Frame Type:"))
        self.frame_type_combo = QComboBox()
        self.frame_type_combo.addItems(["Original", "Threshold", "Contours"])
        self.frame_type_combo.currentTextChanged.connect(self.on_frame_type_changed)
        frame_type_layout.addWidget(self.frame_type_combo)
        frame_type_layout.addStretch()
        layout.addLayout(frame_type_layout)
        
        # Show centroids toggle
        self.show_centroids_check = QCheckBox("Show Centroids & Bounding Boxes")
        self.show_centroids_check.setChecked(True)
        self.show_centroids_check.stateChanged.connect(self.on_centroids_toggled)
        layout.addWidget(self.show_centroids_check)
        
        # Click info display - textbox with list of clicked coordinates
        click_label = QLabel("Image XY and Robot XY (clicked points):")
        click_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(click_label)
        
        self.click_info_textbox = QTextEdit()
        self.click_info_textbox.setReadOnly(True)
        self.click_info_textbox.setMaximumHeight(150)
        self.click_info_textbox.setPlaceholderText("Click on frame to add coordinates...")
        self.click_info_textbox.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.click_info_textbox)
        
        # Capture image button
        self.capture_image_btn = QPushButton("📷 Capture Image")
        self.capture_image_btn.clicked.connect(self.on_capture_image)
        layout.addWidget(self.capture_image_btn)
        
        # Captured image frame (moved under capture button)
        captured_label = QLabel("Captured Image:")
        captured_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(captured_label)
        
        self.secondary_view = ZoomableGraphicsView()
        self.secondary_scene = QGraphicsScene()
        self.secondary_view.setScene(self.secondary_scene)
        self.secondary_view.setMinimumHeight(200)
        self.secondary_view.setMaximumHeight(200)
        layout.addWidget(self.secondary_view)
        
        # Robot movement controls
        robot_move_label = QLabel("Robot Move to Point:")
        robot_move_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(robot_move_label)
        
        # X coordinate
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("X:"))
        self.robot_x_spinbox = QDoubleSpinBox()
        self.robot_x_spinbox.setRange(-1000, 1000)
        self.robot_x_spinbox.setValue(0.0)
        self.robot_x_spinbox.setDecimals(2)
        x_layout.addWidget(self.robot_x_spinbox)
        x_layout.addStretch()
        layout.addLayout(x_layout)
        
        # Y coordinate
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Y:"))
        self.robot_y_spinbox = QDoubleSpinBox()
        self.robot_y_spinbox.setRange(-1000, 1000)
        self.robot_y_spinbox.setValue(0.0)
        self.robot_y_spinbox.setDecimals(2)
        y_layout.addWidget(self.robot_y_spinbox)
        y_layout.addStretch()
        layout.addLayout(y_layout)
        
        # Z coordinate
        z_layout = QHBoxLayout()
        z_layout.addWidget(QLabel("Z:"))
        self.robot_z_spinbox = QDoubleSpinBox()
        self.robot_z_spinbox.setRange(-1000, 1000)
        self.robot_z_spinbox.setValue(0.0)
        self.robot_z_spinbox.setDecimals(2)
        z_layout.addWidget(self.robot_z_spinbox)
        z_layout.addStretch()
        layout.addLayout(z_layout)
        
        # Move button
        self.robot_move_btn = QPushButton("🤖 Move Robot")
        self.robot_move_btn.clicked.connect(self.on_robot_move)
        layout.addWidget(self.robot_move_btn)
        
        layout.addStretch()
        return tab
    
    def create_right_panel(self):
        """Create right panel with vision display and status"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Status section (above main frame)
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 10, 10, 10)
        status_layout.setSpacing(8)
        
        # Current status
        status_layout.addWidget(QLabel("Current Status:"))
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                color: #27ae60;
            }
        """)
        status_layout.addWidget(self.status_label)
        
        # Current state
        status_layout.addWidget(QLabel("Current State:"))
        self.state_label = QLabel("IDLE")
        self.state_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                color: #3498db;
            }
        """)
        status_layout.addWidget(self.state_label)
        
        # Current mode
        status_layout.addWidget(QLabel("Current Mode:"))
        self.mode_label = QLabel("IDLE MODE")
        self.mode_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                color: #9b59b6;
            }
        """)
        status_layout.addWidget(self.mode_label)
        
        layout.addWidget(status_frame)
        
        # Main vision display
        self.vision_view = ZoomableGraphicsView()
        self.vision_view.image_clicked.connect(self.on_image_clicked)
        self.vision_scene = QGraphicsScene()
        self.vision_view.setScene(self.vision_scene)
        layout.addWidget(self.vision_view)
        
        return panel
    
    def setup_demo_data(self):
        """Setup demo centroids and contours"""
        # Create some demo centroids
        for i in range(5):
            x = 200 + i * 150
            y = 200 + (i % 2) * 100
            self.demo_centroids.append((x, y))
        
        # Create demo contours (bounding boxes)
        for i, (cx, cy) in enumerate(self.demo_centroids):
            self.demo_contours.append({
                'bbox': (cx - 30, cy - 30, cx + 30, cy + 30),
                'centroid': (cx, cy)
            })
    
    def update_display(self):
        """Update all displays with current frame"""
        # Create demo frame (light background, no dark mode)
        width, height = 800, 600
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(240, 240, 240))
        
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        
        # Draw frame type indicator
        frame_type_colors = {
            "original": QColor(100, 150, 255),
            "threshold": QColor(200, 200, 200),
            "contours": QColor(255, 200, 100)
        }
        color = frame_type_colors.get(self.current_frame_type.lower(), QColor(255, 255, 255))
        painter.setPen(QPen(color, 3))
        painter.drawRect(10, 10, width - 20, height - 20)
        
        # Draw centroids and bounding boxes if enabled
        if self.show_centroids:
            for contour in self.demo_contours:
                bbox = contour['bbox']
                centroid = contour['centroid']
                
                # Draw bounding box
                painter.setPen(QPen(QColor(0, 255, 0), 2))
                painter.drawRect(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
                
                # Draw centroid
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.setBrush(QBrush(QColor(255, 0, 0)))
                painter.drawEllipse(int(centroid[0]) - 5, int(centroid[1]) - 5, 10, 10)
        
        # Draw cross if clicked
        if self.last_click_pos:
            x, y = self.last_click_pos
            painter.setPen(QPen(QColor(255, 255, 0), 2))
            painter.drawLine(int(x) - 20, int(y), int(x) + 20, int(y))
            painter.drawLine(int(x), int(y) - 20, int(x), int(y) + 20)
        
        painter.end()
        
        # Update main vision view
        self.vision_scene.clear()
        self.vision_scene.addPixmap(pixmap)
        self.vision_view.fitInView(QRectF(0, 0, width, height), Qt.KeepAspectRatio)
        
        # Update operator frame view
        self.operator_frame_scene.clear()
        self.operator_frame_scene.addPixmap(pixmap.scaled(400, 200, Qt.KeepAspectRatio))
        
        # Update secondary view if captured (now in calibration tab)
        if hasattr(self, 'secondary_scene') and self.captured_image:
            self.secondary_scene.clear()
            self.secondary_scene.addPixmap(self.captured_image)
            self.secondary_view.fitInView(self.secondary_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
    
    # Event handlers
    def on_start_all(self):
        """Handle start all button"""
        self.is_inserting = True
        self.section_spinbox.setEnabled(False)
        self.current_status = "Running"
        self.current_state = "INSERTING"
        self.current_mode = "INSERT MODE"
        self.update_status_display()
        self.update_display()
    
    def on_go_to_section(self):
        """Handle go to section button"""
        section = self.section_spinbox.value()
        self.current_status = f"Moving to Section {section}"
        self.update_status_display()
    
    def on_insert_section(self):
        """Handle insert section only button"""
        section = self.section_spinbox.value()
        self.is_inserting = True
        self.section_spinbox.setEnabled(False)
        self.current_status = f"Inserting Section {section}"
        self.current_state = "INSERTING"
        self.current_mode = "INSERT MODE"
        self.update_status_display()
        self.update_display()
    
    def on_speed_changed(self, speed):
        """Handle speed change"""
        self.current_status = f"Speed set to {speed}"
        self.update_status_display()
    
    def on_stop_insertion(self):
        """Handle stop insertion button"""
        self.is_inserting = False
        self.section_spinbox.setEnabled(True)
        self.current_status = "Stopped"
        self.current_state = "IDLE"
        self.current_mode = "IDLE MODE"
        self.update_status_display()
        self.update_display()
    
    def on_save_image(self):
        """Handle save image button"""
        self.current_status = "Image saved"
        self.update_status_display()
    
    def on_frame_type_changed(self, text):
        """Handle frame type change"""
        self.current_frame_type = text.lower()
        self.update_display()
    
    def on_centroids_toggled(self, state):
        """Handle centroids toggle"""
        self.show_centroids = (state == Qt.Checked)
        self.update_display()
    
    def on_image_clicked(self, x, y):
        """Handle image click"""
        self.last_click_pos = (x, y)
        # Simulate robot coordinates (in real app, use homography matrix)
        robot_x = x * 0.1
        robot_y = y * 0.1
        
        # Add to clicked points list
        self.clicked_points.append((x, y, robot_x, robot_y))
        
        # Update textbox with all clicked points
        text = "Image XY\t\tRobot XY\n"
        text += "-" * 40 + "\n"
        for i, (img_x, img_y, rob_x, rob_y) in enumerate(self.clicked_points, 1):
            text += f"{i}. ({img_x:.1f}, {img_y:.1f})\t({rob_x:.2f}, {rob_y:.2f})\n"
        
        self.click_info_textbox.setPlainText(text)
        self.update_display()
    
    def on_capture_image(self):
        """Handle capture image button"""
        # Capture current frame
        if self.vision_scene.items():
            item = self.vision_scene.items()[0]
            if isinstance(item, QGraphicsPixmapItem):
                self.captured_image = item.pixmap()
            else:
                # Create a pixmap from scene
                rect = self.vision_scene.itemsBoundingRect()
                pixmap = QPixmap(int(rect.width()), int(rect.height()))
                pixmap.fill(QColor(240, 240, 240))
                painter = QPainter(pixmap)
                self.vision_scene.render(painter)
                painter.end()
                self.captured_image = pixmap
        
        # Update secondary view in calibration tab
        if hasattr(self, 'secondary_scene') and self.captured_image:
            self.secondary_scene.clear()
            self.secondary_scene.addPixmap(self.captured_image)
            self.secondary_view.fitInView(self.secondary_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
    
    def on_robot_move(self):
        """Handle robot move button"""
        x = self.robot_x_spinbox.value()
        y = self.robot_y_spinbox.value()
        z = self.robot_z_spinbox.value()
        self.current_status = f"Moving robot to ({x:.2f}, {y:.2f}, {z:.2f})"
        self.update_status_display()
    
    def on_zoom_in(self):
        """Handle zoom in button"""
        if hasattr(self, 'vision_view'):
            self.vision_view.scale(1.2, 1.2)
    
    def on_zoom_out(self):
        """Handle zoom out button"""
        if hasattr(self, 'vision_view'):
            self.vision_view.scale(0.8, 0.8)
    
    def on_reset_zoom(self):
        """Handle reset zoom button"""
        if hasattr(self, 'vision_view'):
            self.vision_view.reset_zoom()
    
    def update_status_display(self):
        """Update status labels"""
        self.status_label.setText(self.current_status)
        self.state_label.setText(self.current_state)
        self.mode_label.setText(self.current_mode)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = LayoutDemoB()
    window.show()
    
    sys.exit(app.exec_())

