import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from config.settings import get_settings
from src.core.logger import app_logger


class FileManager:
    """
    Manages document lifecycle inspired by Paperless-ngx consumption directory architecture:
    - Consume: incoming drop folder.
    - Archive: successfully extracted and validated files.
    - Error: quarantined files that failed parsing/validation with error metadata.
    - Output: generated JSON and Excel reports.
    """

    def __init__(self):
        self.settings = get_settings()
        self.settings.ensure_directories()

    def _generate_timestamped_name(self, original_name: str) -> str:
        """Create collision-resistant timestamped filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(original_name).stem
        suffix = Path(original_name).suffix
        return f"{timestamp}_{stem}{suffix}"

    def archive_document(self, file_path: Path) -> Path:
        """Move successfully processed file to the archive directory."""
        target_name = self._generate_timestamped_name(file_path.name)
        target_path = self.settings.STORAGE_ARCHIVE_DIR / target_name
        shutil.move(str(file_path), str(target_path))
        app_logger.info(f"Archived document '{file_path.name}' -> '{target_path}'")
        return target_path

    def quarantine_error(self, file_path: Path, error_message: str, details: Optional[dict] = None) -> Path:
        """
        Move failed document to the error directory and create an accompanying error log file.
        """
        target_name = self._generate_timestamped_name(file_path.name)
        target_path = self.settings.STORAGE_ERROR_DIR / target_name
        shutil.move(str(file_path), str(target_path))

        # Write error context file
        error_info = {
            "original_filename": file_path.name,
            "failed_at": datetime.now().isoformat(),
            "error": error_message,
            "details": details or {}
        }
        error_json_path = target_path.with_suffix(target_path.suffix + ".error.json")
        with open(error_json_path, "w", encoding="utf-8") as f:
            json.dump(error_info, f, indent=2, ensure_ascii=False)

        app_logger.warning(f"Quarantined document '{file_path.name}' to error storage: {target_path}")
        return target_path

    def save_json_output(self, data: dict, original_filename: str) -> Path:
        """Save extracted document as structured JSON in output folder."""
        stem = Path(original_filename).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.settings.STORAGE_OUTPUT_DIR / f"{timestamp}_{stem}.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        app_logger.info(f"Saved JSON output: {output_path}")
        return output_path
