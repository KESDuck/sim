import logging
import os
from datetime import datetime

class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def __init__(self, fmt, datefmt):
        super().__init__(fmt, datefmt)
        self.FORMATS = {
            logging.DEBUG: self.grey + fmt + self.reset,
            logging.INFO: self.grey + fmt + self.reset,
            logging.WARNING: self.yellow + fmt + self.reset,
            logging.ERROR: self.red + fmt + self.reset,
            logging.CRITICAL: self.bold_red + fmt + self.reset
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, self.datefmt)
        return formatter.format(record)

def get_logger(name):
    """Setup and return a logger with the given name."""
    logger = logging.getLogger(name)
    if not logger.hasHandlers():  # Avoid duplicate handlers
        # Create logs directory if it doesn't exist
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = os.path.join(logs_dir, f"app_{timestamp}.log")
        
        # Console handler with colors
        console_handler = logging.StreamHandler()
        fmt = '%(asctime)s.%(msecs)03d [%(levelname)s][%(name)s] %(message)s'
        datefmt = '%H:%M:%S'
        console_formatter = CustomFormatter(fmt, datefmt)
        console_handler.setFormatter(console_formatter)
        
        # File handler without colors
        file_handler = logging.FileHandler(log_filename)
        file_formatter = logging.Formatter(fmt, datefmt)
        file_handler.setFormatter(file_formatter)
        
        # Add both handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
    return logger
