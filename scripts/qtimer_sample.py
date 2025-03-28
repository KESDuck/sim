"""
A simple PyQt5 application demonstrating QTimer usage:
- Creates a window with a button and progress label
- When button is clicked, simulates a task with progress updates every 50ms
- Shows how to use QTimer for periodic updates in PyQt applications
"""

from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QPushButton, QWidget
from PyQt5.QtCore import QTimer

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("QTimer Example")
        self.resize(300, 200)

        self.layout = QVBoxLayout()
        self.label = QLabel("Click the button to start a task.")
        self.layout.addWidget(self.label)

        self.button = QPushButton("Start Task")
        self.button.clicked.connect(self.start_task)
        self.layout.addWidget(self.button)

        self.setLayout(self.layout)

        self.progress = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)

    def start_task(self):
        self.progress = 0
        self.label.setText("Processing...")
        self.timer.start(50)  # Call update_progress every 50 ms

    def update_progress(self):
        if self.progress < 100:
            self.progress += 1
            self.label.setText(f"Progress: {self.progress}%")
        else:
            self.timer.stop()
            self.label.setText("Task Completed!")


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
