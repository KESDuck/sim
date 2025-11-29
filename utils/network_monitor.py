"""
Network Monitor Utility
=======================
Provides ping functionality for checking device connectivity.
"""

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from ping3 import ping
from typing import Dict, Optional
import threading

from utils.logger_config import get_logger
import yaml

logger = get_logger("NetworkMonitor")

# Load device mapping from config
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)
    DEVICES = config.get("network_devices", {})

class NetworkMonitor(QObject):
    """
    Monitors network connectivity for multiple devices using ping.
    Emits signals when ping status changes.
    """
    ping_status_changed = pyqtSignal(str, bool)  # ip, is_online
    
    def __init__(self, ping_interval_ms=3000, devices=None):
        super().__init__()
        self.ping_interval_ms = ping_interval_ms
        self.devices = devices if devices is not None else DEVICES
        self.ping_status: Dict[str, bool] = {ip: False for ip in self.devices.keys()}
        
        # Timer for periodic ping checks
        self.ping_timer = QTimer()
        self.ping_timer.timeout.connect(self._check_all_devices)
        self.ping_timer.setInterval(ping_interval_ms)
        
    def start_monitoring(self):
        """Start periodic ping monitoring"""
        self.ping_timer.start()
        # Do initial check immediately
        self._check_all_devices()
    
    def stop_monitoring(self):
        """Stop periodic ping monitoring"""
        self.ping_timer.stop()
    
    def _check_all_devices(self):
        """Check connectivity for all devices in a separate thread"""
        for ip in self.devices.keys():
            threading.Thread(target=self._check_device, args=(ip,), daemon=True).start()
    
    def _check_device(self, ip: str):
        """Check connectivity for a single device"""
        try:
            response = ping(ip, timeout=0.5)
            is_online = response is not None
        except Exception:
            is_online = False
        
        # Only emit if status changed
        if self.ping_status.get(ip) != is_online:
            self.ping_status[ip] = is_online
            self.ping_status_changed.emit(ip, is_online)
    
    def get_status(self, ip: str) -> bool:
        """Get current ping status for a device"""
        return self.ping_status.get(ip, False)
    
    def get_all_statuses(self) -> Dict[str, bool]:
        """Get current ping status for all devices"""
        return self.ping_status.copy()

