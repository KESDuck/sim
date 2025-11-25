from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGroupBox, QButtonGroup, QGridLayout)
from PyQt5.QtGui import QFont

from utils.logger_config import get_logger

logger = get_logger("UserView")

class UserTabView(QWidget):
    """
    View component for the User/Operator tab.
    Handles UI elements for operator interface with section selection, speed control, and basic operations.
    Based on A1 operator tab layout.
    """
    def __init__(self, controller, font_medium, font_normal):
        super().__init__()
        self.controller = controller
        self.font_medium = font_medium
        self.font_normal = font_normal
        self.selected_section = 1
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the user tab interface."""
        layout = QVBoxLayout(self)
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
        self.speed_slow_button.clicked.connect(lambda: self.on_speed_selected("slow"))
        
        self.speed_normal_button = QPushButton("Normal")
        self.speed_normal_button.setFont(self.font_medium)
        self.speed_normal_button.setCheckable(True)
        self.speed_normal_button.setChecked(True)  # Default selection
        self.speed_normal_button.setMinimumHeight(50)
        self.speed_normal_button.setMinimumWidth(80)
        self.speed_normal_button.clicked.connect(lambda: self.on_speed_selected("normal"))
        
        self.speed_fast_button = QPushButton("Fast")
        self.speed_fast_button.setFont(self.font_medium)
        self.speed_fast_button.setCheckable(True)
        self.speed_fast_button.setMinimumHeight(50)
        self.speed_fast_button.setMinimumWidth(80)
        self.speed_fast_button.clicked.connect(lambda: self.on_speed_selected("fast"))
        
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
    
    def on_section_selected(self, section):
        """Handle section button selection"""
        self.selected_section = section
        self.controller.set_display_section(section)
    
    def on_go_to_section(self):
        """Handle go to section button click"""
        # TODO: Implement go to section functionality
        logger.info(f"Go to section {self.selected_section}")
        # Could call controller method to move robot to section position
    
    def on_insert_section(self):
        """Handle insert section button click"""
        self.controller.insert_section(self.selected_section)
    
    def on_speed_selected(self, speed):
        """Handle speed selection"""
        # Map speed names to percentages
        speed_map = {"slow": 20, "normal": 50, "fast": 80}
        speed_percent = speed_map.get(speed, 50)
        self.controller.change_speed(speed_percent)
    
    def on_start_all_clicked(self):
        """Handle start all button click"""
        # TODO: Implement start all functionality
        logger.info("Start all clicked")
        # Could start a full operation sequence
    
    def on_stop_insertion_clicked(self):
        """Handle stop insertion button click"""
        self.controller.stop_all()
