from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from src.extractor.schemas import ExtractedDocument


class ScanResponse(BaseModel):
    """API response model for document scan endpoint."""
    status: str = Field("success", description="Status of the operation")
    filename: str = Field(..., description="Uploaded filename")
    document: ExtractedDocument = Field(..., description="Extracted and validated document data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Parsing and OCR telemetry")
    excel_file: Optional[str] = Field(None, description="Path to generated Excel file")
    json_file: Optional[str] = Field(None, description="Path to generated JSON file")
    webhook_dispatched: bool = Field(False, description="Whether n8n webhook was dispatched")


class AsyncJobResponse(BaseModel):
    """Response when document is queued for background processing."""
    status: str = Field("queued", description="Job status")
    filename: str = Field(..., description="Original filename")
    message: str = Field(..., description="Descriptive status message")


class HealthResponse(BaseModel):
    """System health check and capability status."""
    status: str = "healthy"
    version: str = "1.0.0"
    llm_provider: str
    llm_model: str
    docling_table_mode: str
    storage_directories_ready: bool
