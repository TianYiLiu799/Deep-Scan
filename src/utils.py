"""Utility functions for Deep-Scan project."""

import logging
from typing import Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = 'INFO') -> None:
    """
    Configure logging for the project.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/deep_scan.log'),
            logging.StreamHandler()
        ]
    )


def ensure_directory(directory: str) -> None:
    """
    Ensure a directory exists, create if needed.

    Args:
        directory: Directory path
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")


def get_timestamp() -> str:
    """
    Get current timestamp.

    Returns:
        ISO format timestamp
    """
    return datetime.now().isoformat()


def validate_url(url: str) -> bool:
    """
    Validate URL format.

    Args:
        url: URL to validate

    Returns:
        True if valid, False otherwise
    """
    return url.startswith(('http://', 'https://'))
