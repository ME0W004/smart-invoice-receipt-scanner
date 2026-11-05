import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse

from config.settings import get_settings
from src.core.logger import app_logger
from src.core.exceptions import ScannerBaseException
from src.api.schemas import ScanResponse, AsyncJobResponse, HealthResponse
from src.parser.preprocessor import SUPPORTED_EXTENSIONS
from src.parser.docling_engine import DoclingEngine
from src.extractor.instructor_client import FinancialExtractor
from src.services.file_manager import FileManager
from src.services.excel_exporter import ExcelExporter
from src.services.webhook_dispatcher import WebhookDispatcher


router = APIRouter(prefix="/api/v1", tags=["Invoice & Receipt Scanner"])
settings = get_settings()

docling_engine = DoclingEngine()
extractor = FinancialExtractor()
file_manager = FileManager()
excel_exporter = ExcelExporter()
webhook_dispatcher = WebhookDispatcher()


@router.get("/health", response_model=HealthResponse)
def health_check():
    """System health check and environmental telemetry."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL_NAME,
        docling_table_mode=settings.DOCLING_TABLE_MODE,
        storage_directories_ready=all(
            p.exists() for p in [
                settings.STORAGE_CONSUME_DIR,
                settings.STORAGE_ARCHIVE_DIR,
                settings.STORAGE_ERROR_DIR,
                settings.STORAGE_OUTPUT_DIR
            ]
        )
    )


@router.post("/scan", response_model=ScanResponse)
async def scan_document_synchronous(file: UploadFile = File(...)):
    """
    Synchronous scanning endpoint:
    Upload a PDF invoice or receipt image, run Docling layout parsing,
    validate with Instructor/LLM, and return structured JSON + export links.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Save temporary file
    temp_path = settings.STORAGE_CONSUME_DIR / f"api_upload_{file.filename}"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1. Parse document with Docling
        markdown_text, metadata = docling_engine.parse_document(temp_path)

        # 2. Extract with Instructor
        extracted_doc = extractor.extract_from_markdown(markdown_text, document_filename=file.filename)

        # 3. Export to JSON
        json_path = None
        if settings.ENABLE_JSON_EXPORT:
            json_path = file_manager.save_json_output(extracted_doc.model_dump(), file.filename)

        # 4. Export to Excel
        excel_path = None
        if settings.ENABLE_EXCEL_EXPORT:
            excel_path = excel_exporter.export_to_excel(extracted_doc, file.filename)

        # 5. Dispatch to n8n webhook
        webhook_ok = webhook_dispatcher.dispatch(
            document=extracted_doc,
            original_filename=file.filename,
            parsing_metadata=metadata
        )

        # 6. Archive input file
        file_manager.archive_document(temp_path)

        return ScanResponse(
            status="success",
            filename=file.filename,
            document=extracted_doc,
            metadata=metadata,
            excel_file=excel_path.name if excel_path else None,
            json_file=json_path.name if json_path else None,
            webhook_dispatched=webhook_ok
        )

    except ScannerBaseException as sbe:
        if temp_path.exists():
            file_manager.quarantine_error(temp_path, error_message=sbe.message, details=sbe.details)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=sbe.message)

    except Exception as e:
        if temp_path.exists():
            file_manager.quarantine_error(temp_path, error_message=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/scan/async", response_model=AsyncJobResponse)
async def scan_document_async(file: UploadFile = File(...)):
    """
    Asynchronous ingestion endpoint (Paperless-ngx pattern):
    Saves document to consumption directory; Folder Watcher will process it in background.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{ext}'."
        )

    target_path = settings.STORAGE_CONSUME_DIR / file.filename
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    app_logger.info(f"Queued file '{file.filename}' to consume directory.")
    return AsyncJobResponse(
        status="queued",
        filename=file.filename,
        message="Document queued in consumption folder for automated pipeline processing."
    )


@router.get("/download/{filename}")
def download_generated_file(filename: str):
    """Download generated Excel (.xlsx) or JSON file from storage/output."""
    file_path = settings.STORAGE_OUTPUT_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested file not found.")

    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if filename.endswith(".xlsx") else "application/json"
    return FileResponse(path=file_path, filename=filename, media_type=media_type)
