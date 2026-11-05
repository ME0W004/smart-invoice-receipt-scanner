import time
from pathlib import Path
from src.core.logger import app_logger
from src.core.exceptions import UnsupportedFileFormatError, ScannerBaseException


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def validate_file(file_path: Path) -> Path:
    """
    Validate that file exists, format is supported, and size is within limits.
    """
    if not file_path.exists():
        raise ScannerBaseException(f"File not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileFormatError(
            f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    file_size = file_path.stat().st_size
    if file_size == 0:
        raise ScannerBaseException(f"File is empty (0 bytes): {file_path}")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ScannerBaseException(
            f"File size ({file_size / (1024*1024):.2f} MB) exceeds maximum allowed size (50 MB)"
        )

    return file_path


def wait_for_file_readiness(file_path: Path, timeout: float = 10.0, check_interval: float = 0.5) -> bool:
    """
    Check if a file has finished being written by another process (e.g. scanner or FTP transfer).
    Compares file size across short intervals until it stabilizes.
    """
    start_time = time.time()
    last_size = -1

    while time.time() - start_time < timeout:
        try:
            current_size = file_path.stat().st_size
            if current_size == last_size and current_size > 0:
                # File size is stable and non-zero
                return True
            last_size = current_size
        except (OSError, PermissionError):
            pass

        time.sleep(check_interval)

    app_logger.warning(f"File readiness check timed out for {file_path}. Proceeding with caution.")
    return True
