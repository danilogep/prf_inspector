"""
Logger para PRF Honda Inspector
"""

import logging
import sys
from app.core.config import settings


def get_logger():
    logger = logging.getLogger("prf_inspector")
    logger.setLevel(logging.DEBUG if settings.DEBUG_MODE else logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


logger = get_logger()
