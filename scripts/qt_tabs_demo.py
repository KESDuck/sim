"""
A PyQt5 application demonstrating QTabWidget usage:
- Creates a window with multiple tabs
- Each tab contains different widgets and layouts
- Shows how to organize content using tabs
"""

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, 
                           QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                           QSpinBox, QComboBox, QTextEdit)
from PyQt5.QtCore import Qt
import sys

class TabDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt Tabs Demo")
        self.setGeometry(100, 100, 600, 400)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Create different tabs
        tabs.addTab(self.create_basic_tab(), "Basic")
        tabs.addTab(self.create_controls_tab(), "Controls")
        tabs.addTab(self.create_text_tab(), "Text")
        
        # Add a close button to the last tab
        tabs.addTab(self.create_closeable_tab(), "Closeable")
        
    def create_basic_tab(self):
        """Create a basic tab with simple widgets"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Add some labels
        layout.addWidget(QLabel("This is a basic tab"))
        layout.addWidget(QLabel("It contains simple widgets"))
        
        # Add a button
        button = QPushButton("Click Me!")
        button.clicked.connect(lambda: print("Button clicked!"))
        layout.addWidget(button)
        
        # Add stretch to push widgets to top
        layout.addStretch()
        
        return tab
    
    def create_controls_tab(self):
        """Create a tab with various control widgets"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Add a spin box
        spin_layout = QHBoxLayout()
        spin_layout.addWidget(QLabel("Number:"))
        spin_box = QSpinBox()
        spin_box.setRange(0, 100)
        spin_layout.addWidget(spin_box)
        layout.addLayout(spin_layout)
        
        # Add a combo box
        combo_layout = QHBoxLayout()
        combo_layout.addWidget(QLabel("Select:"))
        combo = QComboBox()
        combo.addItems(["Option 1", "Option 2", "Option 3"])
        combo_layout.addWidget(combo)
        layout.addLayout(combo_layout)
        
        # Add some buttons
        button_layout = QHBoxLayout()
        button1 = QPushButton("Button 1")
        button2 = QPushButton("Button 2")
        button_layout.addWidget(button1)
        button_layout.addWidget(button2)
        layout.addLayout(button_layout)
        
        layout.addStretch()
        return tab
    
    def create_text_tab(self):
        """Create a tab with text editing capabilities"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Add a text editor
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("Enter some text here...")
        layout.addWidget(text_edit)
        
        # Add buttons for text manipulation
        button_layout = QHBoxLayout()
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(text_edit.clear)
        button_layout.addWidget(clear_button)
        
        layout.addLayout(button_layout)
        return tab
    
    def create_closeable_tab(self):
        """Create a tab that can be closed"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Add a label
        layout.addWidget(QLabel("This tab can be closed!"))
        
        # Add a close button
        close_button = QPushButton("Close Tab")
        close_button.clicked.connect(lambda: self.close_tab(tab))
        layout.addWidget(close_button)
        
        layout.addStretch()
        return tab
    
    def close_tab(self, tab):
        """Close the specified tab"""
        # Find the tab widget
        tab_widget = self.findChild(QTabWidget)
        if tab_widget:
            index = tab_widget.indexOf(tab)
            if index >= 0:
                tab_widget.removeTab(index)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TabDemo()
    window.show()
    sys.exit(app.exec_()) 