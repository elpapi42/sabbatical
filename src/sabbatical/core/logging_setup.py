"""Centralized logging configuration for Sabbatical."""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(level: str, file_path: str) -> None:
    """Configure logging for the Sabbatical application.

    Args:
        level: Log level (e.g. "INFO", "DEBUG")
        file_path: Path to log file (supports ~ expansion)
    """
    fmt = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    # Get or create root logger for sabbatical namespace
    root = logging.getLogger("sabbatical")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # File handler with rotation (10 MB × 5 backups)
    path = Path(file_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        path, maxBytes=10_000_000, backupCount=5
    )
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Stderr handler for WARNING+ (surfaces errors in terminal)
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(formatter)
    root.addHandler(sh)
