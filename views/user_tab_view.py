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
        
        # Initialize control states (IDLE state)
        self.update_control_states("IDLE", "IDLE MODE")
        
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
    
    def on_start_all_clicked(self):
        """Handle start all button click"""
        # TODO: Implement start all functionality
        logger.info("Start all clicked")
        # Could start a full operation sequence
    
    def on_stop_insertion_clicked(self):
        """Handle stop insertion button click"""
        self.controller.stop_all()
    
    def update_control_states(self, state, mode):
        """Update enabled/disabled state of controls based on current operation state"""
        # Operating means not in IDLE state
        is_operating = state != "IDLE"
        
        # Disable controls while operating
        self.start_all_button.setEnabled(not is_operating)
        
        # Disable section buttons while operating
        for btn in self.section_buttons:
            btn.setEnabled(not is_operating)
        
        # Disable go to section and insert section buttons while operating
        self.go_to_section_button.setEnabled(not is_operating)
        self.insert_section_button.setEnabled(not is_operating)
        
        # Stop button is always enabled (no need to change, already enabled by default)
