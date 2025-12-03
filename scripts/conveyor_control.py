import sys
import socket
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer


PLC_IP = "192.168.0.10"
PLC_PORT = 8501


# ---------------------------------------------
# Minimal PLC Communication Helper
# ---------------------------------------------
class PLCClient:
    def __init__(self, host=PLC_IP, port=PLC_PORT, timeout=0.2):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_cmd(self, cmd: str) -> str:
        """Sends ASCII command (e.g. 'WR R500 0001') and returns PLC response."""
        try:
            msg = (cmd + "\r").encode("ascii")
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall(msg)
                resp = s.recv(1024)
                return resp.decode(errors="ignore").strip()
        except Exception as e:
            return f"ERR: {e}"

    def write_reg(self, reg: str, value: int):
        return self.send_cmd(f"WR {reg} {value:04d}")

    def read_reg(self, reg: str) -> int:
        resp = self.send_cmd(f"RD {reg}")
        digits = "".join(c for c in resp if c.isdigit())
        if digits:
            return int(digits[-4:])
        return -1  # error


# ---------------------------------------------
# Background Sensor Polling Thread
# ---------------------------------------------
class SensorThread(QThread):
    sensor_update = pyqtSignal(int, int, int)  # emits (R000, R500, R510) status

    def __init__(self, plc: PLCClient, parent=None):
        super().__init__(parent)
        self.plc = plc
        self.running = True

    def run(self):
        while self.running:
            val_r000 = self.plc.read_reg("R000")
            val_r500 = self.plc.read_reg("R500")
            val_r510 = self.plc.read_reg("R510")
            self.sensor_update.emit(val_r000, val_r500, val_r510)
            self.msleep(50)  # 20 Hz polling


# ---------------------------------------------
# Main PyQt5 GUI
# ---------------------------------------------
class ConveyorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Conveyor Control GUI")

        self.plc = PLCClient()

        # --- UI Elements ---
        self.label_sensor = QLabel("Sensor (R000): ---")
        self.label_sensor.setStyleSheet("font-size: 20px;")
        
        self.label_motor = QLabel("Motor (R500): ---")
        self.label_motor.setStyleSheet("font-size: 20px;")
        
        self.label_solenoid = QLabel("Solenoid (R510): ---")
        self.label_solenoid.setStyleSheet("font-size: 20px;")

        btn_start = QPushButton("Start Motor (R500=1)")
        btn_stop = QPushButton("Stop Motor (R500=0)")
        btn_sol_on = QPushButton("Solenoid ON (R510=1)")
        btn_sol_off = QPushButton("Solenoid OFF (R510=0)")

        btn_start.clicked.connect(lambda: self.write_motor(1))
        btn_stop.clicked.connect(lambda: self.write_motor(0))
        btn_sol_on.clicked.connect(lambda: self.write_solenoid(1))
        btn_sol_off.clicked.connect(lambda: self.write_solenoid(0))

        layout = QVBoxLayout()
        layout.addWidget(self.label_sensor)
        layout.addWidget(self.label_motor)
        layout.addWidget(self.label_solenoid)
        layout.addWidget(btn_start)
        layout.addWidget(btn_stop)

        sol_layout = QHBoxLayout()
        sol_layout.addWidget(btn_sol_on)
        sol_layout.addWidget(btn_sol_off)
        layout.addLayout(sol_layout)

        self.setLayout(layout)

        # --- Start sensor polling thread ---
        self.sensor_thread = SensorThread(self.plc)
        self.sensor_thread.sensor_update.connect(self.update_sensor_label)
        self.sensor_thread.start()

    # -------------------------------------------------
    # Motor Controls
    # -------------------------------------------------
    def write_motor(self, value):
        resp = self.plc.write_reg("R500", value)
        print("Motor write:", resp)

    def write_solenoid(self, value):
        resp = self.plc.write_reg("R510", value)
        print("Solenoid write:", resp)

    # -------------------------------------------------
    # UI Update
    # -------------------------------------------------
    def update_sensor_label(self, val_r000, val_r500, val_r510):
        # Update R000 sensor
        txt_r000 = f"Sensor (R000): {val_r000}"
        self.label_sensor.setText(txt_r000)
        if val_r000 == 1:
            self.label_sensor.setStyleSheet("background: lightgreen; font-size: 20px;")
        else:
            self.label_sensor.setStyleSheet("background: none; font-size: 20px;")
        
        # Update R500 motor
        txt_r500 = f"Motor (R500): {val_r500}"
        self.label_motor.setText(txt_r500)
        if val_r500 == 1:
            self.label_motor.setStyleSheet("background: lightblue; font-size: 20px;")
        else:
            self.label_motor.setStyleSheet("background: none; font-size: 20px;")
        
        # Update R510 solenoid
        txt_r510 = f"Solenoid (R510): {val_r510}"
        self.label_solenoid.setText(txt_r510)
        if val_r510 == 1:
            self.label_solenoid.setStyleSheet("background: lightyellow; font-size: 20px;")
        else:
            self.label_solenoid.setStyleSheet("background: none; font-size: 20px;")

    # -------------------------------------------------
    # Proper shutdown
    # -------------------------------------------------
    def closeEvent(self, event):
        self.sensor_thread.running = False
        self.sensor_thread.wait()
        event.accept()


# ---------------------------------------------
# Run Application
# ---------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ConveyorGUI()
    gui.resize(400, 300)
    gui.show()
    sys.exit(app.exec_())
