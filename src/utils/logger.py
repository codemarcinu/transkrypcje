import logging
import threading

class Logger:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            filename="app_debug.log",
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )

    def log(self, message, level=logging.INFO):
        if level == logging.DEBUG:
            logging.debug(message)
        elif level == logging.INFO:
            logging.info(message)
        elif level == logging.WARNING:
            logging.warning(message)
        elif level == logging.ERROR:
            logging.error(message)
        elif level == logging.CRITICAL:
            logging.critical(message)
        
        if self.log_callback:
            self.log_callback(message)

    def debug(self, message): self.log(message, logging.DEBUG)
    def info(self, message): self.log(message, logging.INFO)
    def warning(self, message): self.log(message, logging.WARNING)
    def error(self, message): self.log(message, logging.ERROR)
    def critical(self, message): self.log(message, logging.CRITICAL)

    def set_callback(self, callback):
        self.log_callback = callback

def setup_logger():
    return Logger()

# Global logger instance
logger = setup_logger()
