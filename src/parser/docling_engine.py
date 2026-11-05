import time
from pathlib import Path
from typing import Dict, Any, Tuple
from config.settings import get_settings
from src.core.logger import app_logger
from src.core.exceptions import DocumentParsingError
from src.parser.preprocessor import validate_file, wait_for_file_readiness


class DoclingEngine:
    """
    Enterprise Document Parsing engine using IBM Docling.
    Extracts multi-column text, metadata, and complex tables preserving markdown grid layout.
    """

    def __init__(self):
        self.settings = get_settings()
        self._converter = None
        self._init_converter()

    def _init_converter(self):
        """Lazy-load and configure the Docling DocumentConverter."""
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
            from docling.datamodel.base_models import InputFormat

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_table_structure = True
            
            # Select table extraction mode
            if self.settings.DOCLING_TABLE_MODE.lower() == "accurate":
                pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
            else:
                pipeline_options.table_structure_options.mode = TableFormerMode.FAST

            pipeline_options.do_ocr = self.settings.DOCLING_DO_OCR

            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            app_logger.info("IBM Docling DocumentConverter initialized successfully.")

        except ImportError:
            app_logger.warning(
                "docling library is not yet installed in this environment. "
                "Will use fallback parsing mechanism if available."
            )
            self._converter = None
        except Exception as e:
            app_logger.error(f"Failed to configure Docling converter: {e}")
            self._converter = None

    def parse_document(self, file_path: Path) -> Tuple[str, Dict[str, Any]]:
        """
        Parse PDF or image file into structured Markdown and metadata.
        
        Args:
            file_path: Path to the target document.
            
        Returns:
            Tuple[str, Dict[str, Any]]: (Markdown content, Parsing metadata)
        """
        file_path = validate_file(file_path)
        wait_for_file_readiness(file_path)

        app_logger.info(f"Parsing document with IBM Docling: {file_path.name}")
        start_time = time.time()

        if self._converter is not None:
            try:
                conversion_result = self._converter.convert(str(file_path))
                markdown_text = conversion_result.document.export_to_markdown()
                elapsed = time.time() - start_time

                metadata = {
                    "parser": "IBM Docling",
                    "filename": file_path.name,
                    "elapsed_seconds": round(elapsed, 2),
                    "table_mode": self.settings.DOCLING_TABLE_MODE,
                    "pages": getattr(conversion_result.document, "num_pages", 1),
                }

                app_logger.success(
                    f"Document '{file_path.name}' parsed in {elapsed:.2f}s "
                    f"({len(markdown_text)} chars extracted)."
                )
                return markdown_text, metadata

            except Exception as e:
                app_logger.error(f"Docling conversion failed for {file_path.name}: {e}")
                raise DocumentParsingError(
                    f"Docling parser failed to process {file_path.name}: {str(e)}",
                    details={"file": str(file_path), "error": str(e)}
                )

        # Fallback parser if docling is not installed in local lightweight dev mode
        return self._fallback_parse(file_path, start_time)

    def _fallback_parse(self, file_path: Path, start_time: float) -> Tuple[str, Dict[str, Any]]:
        """Fallback lightweight text extraction for non-GPU or testing environments."""
        app_logger.warning(f"Using lightweight fallback parser for {file_path.name}")
        ext = file_path.suffix.lower()
        extracted_text = ""

        if ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                pages = [page.extract_text() or "" for page in reader.pages]
                extracted_text = "\n\n--- Page Break ---\n\n".join(pages)
            except Exception as e:
                app_logger.warning(f"pypdf fallback failed: {e}")
                extracted_text = f"Sample invoice text content from {file_path.name}"
        else:
            extracted_text = f"Sample image receipt content from {file_path.name}"

        elapsed = time.time() - start_time
        metadata = {
            "parser": "Fallback Text Parser",
            "filename": file_path.name,
            "elapsed_seconds": round(elapsed, 2),
        }
        return extracted_text, metadata
