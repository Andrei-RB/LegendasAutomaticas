import logging
from logging.handlers import RotatingFileHandler
import os
from pythonjsonlogger import jsonlogger
from app.core.config import settings

def setup_logging():
    logger = logging.getLogger("app")
    
    # Configure level based on env
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    logger.setLevel(level)

    # Prevent logs from propagating to the root logger to avoid duplicate msgs
    logger.propagate = False

    if not logger.handlers:
        # JSON Formatter for NIST compliant structured logging
        log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
        formatter = jsonlogger.JsonFormatter(log_format)

        # File Handler with rotation to prevent disk exhaustion
        log_file = os.path.join(settings.LOG_DIR, "app.log")
        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console Handler (standard output)
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger

logger = setup_logging()
