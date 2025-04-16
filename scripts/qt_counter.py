"""
A simple PyQt5 counter application demonstrating QTimer and QSpinBox:
- Creates a window with a number input box and start/pause button
- When started, automatically increments the number every 500ms
- Shows how to use QTimer for continuous updates and QSpinBox for number input
"""

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QSpinBox
from PyQt5.QtCore import QTimer

class CounterApp(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Counter App")
        self.resize(300, 150)

        self.layout = QVBoxLayout()

        self.number_box = QSpinBox()
        self.number_box.setRange(0, 1000)  # Set a reasonable range
        self.layout.addWidget(self.number_box)

        self.start_pause_button = QPushButton("Start")
        self.start_pause_button.clicked.connect(self.toggle_timer)
        self.layout.addWidget(self.start_pause_button)

        self.timer = QTimer()
        self.timer.timeout.connect(self.increment_number)

        self.setLayout(self.layout)

    def toggle_timer(self):
        if self.timer.isActive():
            self.timer.stop()
            self.start_pause_button.setText("Start")
        else:
            self.timer.start(5)  # 1000 ms = 1 second
            self.start_pause_button.setText("Pause")

    def increment_number(self):
        current_value = self.number_box.value()
        self.number_box.setValue(current_value + 1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CounterApp()
    window.show()
    sys.exit(app.exec_())
