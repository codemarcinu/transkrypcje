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

    def log(self, message):
        logging.info(message)
        if self.log_callback:
            self.log_callback(message)

    def set_callback(self, callback):
        self.log_callback = callback
