"""Logging configuration for Agent Gateway that integrates with Jupyter."""

import logging
from pathlib import Path
from datetime import datetime


def setup_logging(debug: bool = False, log_to_file: bool = True) -> None:
    """
    Setup logging for Agent Gateway.

    This function integrates with Jupyter's logging system while optionally
    adding file logging for debugging purposes.

    Args:
        debug: Enable debug logging level
        log_to_file: Whether to also write logs to a file (default True)
    """
    # Get the root logger for this extension
    top_logger = logging.getLogger("jupyter_agents_gateway")

    # Set level based on debug flag
    level = logging.DEBUG if debug else logging.INFO
    top_logger.setLevel(level)

    top_logger.propagate = True

    # Only add file handler if requested and not already added
    if log_to_file and not _has_file_handler(top_logger):
        _add_file_handler(top_logger, level)

    # Reduce noise from verbose libraries (these affect root logger)
    _configure_third_party_logging(level)

def _has_file_handler(logger: logging.Logger) -> bool:
    """Check if logger already has a file handler."""
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            return True
    return False


def _get_default_log_path() -> Path:
    """Get default log file path under extension directory."""
    current_dir = Path(__file__).resolve().parent.parent.parent

    # Create logs directory
    logs_dir = current_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Generate log file name with date
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"jupydeep_{date_str}.log"

    return log_file


def _add_file_handler(logger: logging.Logger, level: int) -> None:
    """Add a rotating file handler to the logger."""

    try:
        from logging.handlers import RotatingFileHandler

        log_path = _get_default_log_path()

        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
            delay=False,
        )
        file_handler.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Fall back to console only
        # import traceback
        # traceback.print_exc()
        logger.warning(f"Failed to add file handler: {e}")


def _configure_third_party_logging(level: int) -> None:
    """Configure logging for third-party libraries to reduce noise."""
    # Only suppress if not debug mode
    if level > logging.DEBUG:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("tornado").setLevel(logging.WARNING)
        logging.getLogger("traitlets").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance under jupydeep namespace
    """
    prefix = "jupydeep"
    if "/" in name or "\\" in name:
        name = Path(name).stem

    if name.startswith(prefix):
        full_name = name
    else:
        full_name = f"{prefix}.{name}"
    return logging.getLogger(full_name)

