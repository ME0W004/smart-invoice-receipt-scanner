import sys
import logging
from pathlib import Path

try:
    from loguru import logger as _loguru_logger
    _HAS_LOGURU = True
except ImportError:
    _HAS_LOGURU = False

from config.settings import get_settings


def setup_logger():
    """
    Configure enterprise structured logging using Loguru if available,
    or standard Python logging as a seamless fallback.
    """
    settings = get_settings()
    log_dir = Path("./storage/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    if _HAS_LOGURU:
        _loguru_logger.remove()
        _loguru_logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                   "<level>{message}</level>",
            colorize=True
        )
        _loguru_logger.add(
            log_dir / "scanner_{time:YYYY-MM-DD}.log",
            level="DEBUG",
            rotation="50 MB",
            retention="30 days",
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            encoding="utf-8"
        )
        return _loguru_logger

    # Standard logging fallback
    std_logger = logging.getLogger("smart_invoice_scanner")
    std_logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    if not std_logger.handlers:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"))
        std_logger.addHandler(ch)

        # File handler
        fh = logging.FileHandler(log_dir / "scanner.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"))
        std_logger.addHandler(fh)

    # Add helper success method if missing
    if not hasattr(std_logger, "success"):
        setattr(std_logger, "success", std_logger.info)

    return std_logger


# Initialize and export logger instance
app_logger = setup_logger()
