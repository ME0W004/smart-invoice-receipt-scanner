import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config.settings import get_settings
from src.core.logger import app_logger
from src.core.exceptions import ScannerBaseException
from src.parser.preprocessor import SUPPORTED_EXTENSIONS, wait_for_file_readiness
from src.parser.docling_engine import DoclingEngine
from src.extractor.instructor_client import FinancialExtractor
from src.services.file_manager import FileManager
from src.services.excel_exporter import ExcelExporter
from src.services.webhook_dispatcher import WebhookDispatcher


class DocumentConsumptionHandler(FileSystemEventHandler):
    """
    Handles new document events in the consume folder, executing
    the full parsing, extraction, archiving, and webhook pipeline.
    """

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.file_manager = FileManager()
        self.parser = DoclingEngine()
        self.extractor = FinancialExtractor()
        self.excel_exporter = ExcelExporter()
        self.webhook_dispatcher = WebhookDispatcher()
        self._processing_files = set()

    def process_file(self, file_path: Path):
        """Execute full industrial pipeline on a consumed file."""
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return

        resolved_path = str(file_path.resolve())
        if resolved_path in self._processing_files:
            return

        self._processing_files.add(resolved_path)
        app_logger.info(f"===> Processing consumed file: {file_path.name}")

        try:
            # 1. Wait for file upload/write completion
            wait_for_file_readiness(file_path, timeout=self.settings.WATCHER_DEBOUNCE_SECONDS * 3)

            # 2. Parse layout and tables with Docling
            markdown_content, metadata = self.parser.parse_document(file_path)

            # 3. Extract and validate schema with Instructor & LLM
            extracted_doc = self.extractor.extract_from_markdown(
                markdown_content=markdown_content,
                document_filename=file_path.name
            )

            # 4. Generate structured JSON output
            if self.settings.ENABLE_JSON_EXPORT:
                self.file_manager.save_json_output(
                    data=extracted_doc.model_dump(),
                    original_filename=file_path.name
                )

            # 5. Generate formatted Excel workbook
            if self.settings.ENABLE_EXCEL_EXPORT:
                self.excel_exporter.export_to_excel(
                    document=extracted_doc,
                    original_filename=file_path.name
                )

            # 6. Dispatch Webhook to n8n / downstream ERP
            self.webhook_dispatcher.dispatch(
                document=extracted_doc,
                original_filename=file_path.name,
                parsing_metadata=metadata
            )

            # 7. Move file to Archive
            self.file_manager.archive_document(file_path)
            app_logger.success(f"===> Successfully processed and archived: {file_path.name}")

        except ScannerBaseException as sbe:
            app_logger.error(f"Pipeline error processing {file_path.name}: {sbe.message}")
            self.file_manager.quarantine_error(file_path, error_message=sbe.message, details=sbe.details)

        except Exception as e:
            app_logger.error(f"Unexpected error processing {file_path.name}: {str(e)}")
            self.file_manager.quarantine_error(file_path, error_message=str(e))

        finally:
            self._processing_files.discard(resolved_path)

    def on_created(self, event):
        if not event.is_directory:
            time.sleep(self.settings.WATCHER_DEBOUNCE_SECONDS)
            self.process_file(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            time.sleep(self.settings.WATCHER_DEBOUNCE_SECONDS)
            self.process_file(Path(event.dest_path))


class FolderWatcherService:
    """
    Long-running service monitoring the consumption directory.
    Employs watchdog with periodic sweep fallback.
    """

    def __init__(self):
        self.settings = get_settings()
        self.settings.ensure_directories()
        self.handler = DocumentConsumptionHandler()
        self.observer = Observer()

    def sweep_existing_files(self):
        """Process any files already present in consume directory upon startup."""
        consume_dir = self.settings.STORAGE_CONSUME_DIR
        app_logger.info(f"Scanning consume directory for pending files: {consume_dir}")
        for file_path in consume_dir.glob("*"):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                self.handler.process_file(file_path)

    def start(self):
        """Start the directory watcher loop."""
        consume_dir = str(self.settings.STORAGE_CONSUME_DIR.resolve())
        app_logger.info(f"Starting Folder Watcher on directory: {consume_dir}")
        
        # Initial sweep
        self.sweep_existing_files()

        self.observer.schedule(self.handler, path=consume_dir, recursive=False)
        self.observer.start()

        try:
            while True:
                time.sleep(self.settings.WATCHER_POLL_INTERVAL)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the directory observer."""
        app_logger.info("Stopping Folder Watcher...")
        self.observer.stop()
        self.observer.join()
