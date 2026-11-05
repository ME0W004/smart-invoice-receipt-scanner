import sys
import threading
from pathlib import Path
import typer
import uvicorn

from config.settings import get_settings
from src.core.logger import app_logger
from src.parser.docling_engine import DoclingEngine
from src.extractor.instructor_client import FinancialExtractor
from src.services.file_manager import FileManager
from src.services.excel_exporter import ExcelExporter
from src.services.webhook_dispatcher import WebhookDispatcher
from src.watcher.folder_watcher import FolderWatcherService


cli_app = typer.Typer(
    name="Smart Invoice & Receipt Scanner CLI",
    help="Industrial OCR, layout parsing, and financial data extraction CLI."
)


@cli_app.command("serve")
def start_server(
    host: str = typer.Option(None, help="Host address to bind"),
    port: int = typer.Option(None, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development")
):
    """Run the FastAPI web and webhook service."""
    settings = get_settings()
    bind_host = host or settings.API_HOST
    bind_port = port or settings.API_PORT

    app_logger.info(f"Starting API server on http://{bind_host}:{bind_port} (Swagger docs: http://{bind_host}:{bind_port}/docs)")
    uvicorn.run("src.api.app:app", host=bind_host, port=bind_port, reload=reload)


@cli_app.command("watch")
def start_watcher():
    """Start the Paperless-ngx style consumption folder watcher."""
    watcher = FolderWatcherService()
    try:
        watcher.start()
    except KeyboardInterrupt:
        watcher.stop()


@cli_app.command("scan")
def scan_single_file(
    file_path: str = typer.Argument(..., help="Path to PDF invoice or receipt image file"),
    no_excel: bool = typer.Option(False, help="Disable Excel export"),
    no_json: bool = typer.Option(False, help="Disable JSON export"),
    dispatch_webhook: bool = typer.Option(True, help="Dispatch to n8n webhook if configured")
):
    """Scan a single document through the pipeline from the command line."""
    target_file = Path(file_path)
    if not target_file.exists():
        app_logger.error(f"File not found: {target_file}")
        sys.exit(1)

    app_logger.info(f"Initiating single file scan for: {target_file.name}")
    
    parser = DoclingEngine()
    extractor = FinancialExtractor()
    file_manager = FileManager()
    excel_exporter = ExcelExporter()
    webhook_dispatcher = WebhookDispatcher()

    # 1. Parse Layout with Docling
    markdown_text, metadata = parser.parse_document(target_file)

    # 2. Extract with Instructor
    document = extractor.extract_from_markdown(markdown_text, target_file.name)

    # 3. Export JSON
    if not no_json:
        json_path = file_manager.save_json_output(document.model_dump(), target_file.name)
        typer.echo(f"Structured JSON: {json_path}")

    # 4. Export Excel
    if not no_excel:
        excel_path = excel_exporter.export_to_excel(document, target_file.name)
        typer.echo(f"Excel Workbook: {excel_path}")

    # 5. Dispatch Webhook
    if dispatch_webhook:
        webhook_dispatcher.dispatch(document, target_file.name, metadata)

    typer.echo("\n--- Extraction Summary ---")
    typer.echo(f"Document Type: {document.document_type.value}")
    typer.echo(f"Document Number: {document.document_number}")
    typer.echo(f"Vendor: {document.vendor.name or 'N/A'}")
    typer.echo(f"Customer: {document.customer.name or 'N/A'}")
    typer.echo(f"Grand Total: {document.summary.grand_total:,.2f} {document.currency}")
    typer.echo(f"Line Items Count: {len(document.items)}")


@cli_app.command("run-all")
def run_all(
    host: str = typer.Option(None, help="Host address"),
    port: int = typer.Option(None, help="Port")
):
    """Run both the FastAPI server and the consumption Folder Watcher concurrently."""
    app_logger.info("Starting both Web API and Folder Watcher concurrently...")
    
    watcher_service = FolderWatcherService()
    watcher_thread = threading.Thread(target=watcher_service.start, daemon=True)
    watcher_thread.start()

    start_server(host=host, port=port, reload=False)


if __name__ == "__main__":
    cli_app()
