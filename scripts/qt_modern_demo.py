"""
Modern PyQt5 Demo Application
A self-contained demo showcasing modern UI design with:
- Stylized components with custom QSS
- Card-based layout
- Interactive widgets
- Clean, maintainable code structure
"""

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QProgressBar,
                             QSlider, QSpinBox, QFrame, QGridLayout)
from PyQt5.QtCore import Qt, QTimer


class CardWidget(QFrame):
    """Reusable card component for grouping widgets"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)
        
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("cardTitle")
            self.layout.addWidget(title_label)
    
    def add_widget(self, widget):
        """Add widget to card"""
        self.layout.addWidget(widget)


class ModernDemo(QMainWindow):
    """Main application window with modern styling"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.apply_styles()
        self.setup_timer()
    
    def init_ui(self):
        """Initialize UI components"""
        self.setWindowTitle("Modern Qt Demo")
        self.setGeometry(100, 100, 900, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Content grid
        content_grid = QGridLayout()
        content_grid.setSpacing(20)
        
        # Create cards
        content_grid.addWidget(self.create_stats_card(), 0, 0)
        content_grid.addWidget(self.create_controls_card(), 0, 1)
        content_grid.addWidget(self.create_progress_card(), 1, 0)
        content_grid.addWidget(self.create_interactive_card(), 1, 1)
        
        main_layout.addLayout(content_grid)
        main_layout.addStretch()
    
    def create_header(self):
        """Create header section"""
        header = QWidget()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("Modern Qt Demo")
        title.setObjectName("headerTitle")
        layout.addWidget(title)
        
        layout.addStretch()
        
        status = QLabel("● Active")
        status.setObjectName("statusLabel")
        layout.addWidget(status)
        
        return header
    
    def create_stats_card(self):
        """Create statistics card"""
        card = CardWidget("Statistics")
        
        # Stat items
        self.value_label = QLabel("0")
        self.value_label.setObjectName("statValue")
        card.add_widget(self.value_label)
        
        desc_label = QLabel("Current Value")
        desc_label.setObjectName("statDesc")
        card.add_widget(desc_label)
        
        return card
    
    def create_controls_card(self):
        """Create controls card"""
        card = CardWidget("Controls")
        
        # Spin box
        spin_layout = QHBoxLayout()
        spin_layout.addWidget(QLabel("Value:"))
        self.spin_box = QSpinBox()
        self.spin_box.setRange(0, 100)
        self.spin_box.setValue(50)
        self.spin_box.valueChanged.connect(self.on_value_changed)
        spin_layout.addWidget(self.spin_box)
        card.layout.addLayout(spin_layout)
        
        # Slider
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Slider:"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(self.on_slider_changed)
        slider_layout.addWidget(self.slider)
        card.layout.addLayout(slider_layout)
        
        # Sync spin box and slider
        self.spin_box.valueChanged.connect(lambda v: self.slider.setValue(v))
        self.slider.valueChanged.connect(lambda v: self.spin_box.setValue(v))
        
        return card
    
    def create_progress_card(self):
        """Create progress card"""
        card = CardWidget("Progress")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        card.add_widget(self.progress_bar)
        
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.toggle_progress)
        button_layout.addWidget(self.start_btn)
        
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_progress)
        button_layout.addWidget(reset_btn)
        
        card.layout.addLayout(button_layout)
        
        return card
    
    def create_interactive_card(self):
        """Create interactive card"""
        card = CardWidget("Interactive")
        
        self.counter_label = QLabel("0")
        self.counter_label.setObjectName("counterValue")
        card.add_widget(self.counter_label)
        
        button_layout = QHBoxLayout()
        inc_btn = QPushButton("+")
        inc_btn.clicked.connect(self.increment_counter)
        button_layout.addWidget(inc_btn)
        
        dec_btn = QPushButton("-")
        dec_btn.clicked.connect(self.decrement_counter)
        button_layout.addWidget(dec_btn)
        
        card.layout.addLayout(button_layout)
        
        return card
    
    def setup_timer(self):
        """Setup timer for progress animation"""
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_value = 0
    
    def on_value_changed(self, value):
        """Handle value changes"""
        self.value_label.setText(str(value))
    
    def on_slider_changed(self, value):
        """Handle slider changes"""
        self.value_label.setText(str(value))
    
    def toggle_progress(self):
        """Toggle progress animation"""
        if self.progress_timer.isActive():
            self.progress_timer.stop()
            self.start_btn.setText("Start")
        else:
            self.progress_timer.start(50)
            self.start_btn.setText("Pause")
    
    def update_progress(self):
        """Update progress bar"""
        if self.progress_value < 100:
            self.progress_value += 1
            self.progress_bar.setValue(self.progress_value)
        else:
            self.progress_timer.stop()
            self.start_btn.setText("Start")
            self.progress_value = 0
    
    def reset_progress(self):
        """Reset progress bar"""
        self.progress_timer.stop()
        self.progress_value = 0
        self.progress_bar.setValue(0)
        self.start_btn.setText("Start")
    
    def increment_counter(self):
        """Increment counter"""
        current = int(self.counter_label.text())
        self.counter_label.setText(str(current + 1))
    
    def decrement_counter(self):
        """Decrement counter"""
        current = int(self.counter_label.text())
        self.counter_label.setText(str(current - 1))
    
    def apply_styles(self):
        """Apply modern styling"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            
            #header {
                background-color: #2c3e50;
                border-radius: 8px;
                padding: 15px 20px;
            }
            
            #headerTitle {
                color: white;
                font-size: 24px;
                font-weight: bold;
            }
            
            #statusLabel {
                color: #2ecc71;
                font-size: 14px;
            }
            
            #card {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
            
            #cardTitle {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 10px;
            }
            
            #statValue {
                font-size: 48px;
                font-weight: bold;
                color: #3498db;
                padding: 10px 0;
            }
            
            #statDesc {
                color: #7f8c8d;
                font-size: 14px;
            }
            
            #counterValue {
                font-size: 48px;
                font-weight: bold;
                color: #e74c3c;
                text-align: center;
                padding: 10px 0;
            }
            
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #21618c;
            }
            
            QSpinBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
                background-color: white;
            }
            
            QSpinBox:focus {
                border-color: #3498db;
            }
            
            QSlider::groove:horizontal {
                border: 1px solid #bdc3c7;
                height: 8px;
                background: #ecf0f1;
                border-radius: 4px;
            }
            
            QSlider::handle:horizontal {
                background: #3498db;
                border: 2px solid white;
                width: 20px;
                height: 20px;
                border-radius: 10px;
                margin: -6px 0;
            }
            
            QSlider::handle:horizontal:hover {
                background: #2980b9;
            }
            
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                text-align: center;
                height: 30px;
                background-color: #ecf0f1;
            }
            
            QProgressBar::chunk {
                background-color: #2ecc71;
                border-radius: 4px;
            }
            
            QLabel {
                color: #2c3e50;
            }
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    window = ModernDemo()
    window.show()
    
    sys.exit(app.exec_())

