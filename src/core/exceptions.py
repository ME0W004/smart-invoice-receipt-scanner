"""
Custom exception hierarchy for Smart Invoice & Receipt Scanner.
Provides clear error classifications for resilient error handling and status reporting.
"""

class ScannerBaseException(Exception):
    """Base exception for all scanner-related errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedFileFormatError(ScannerBaseException):
    """Raised when an uploaded/consumed file format is not supported."""
    pass


class DocumentParsingError(ScannerBaseException):
    """Raised when IBM Docling fails to convert or parse the document layout."""
    pass


class ExtractionValidationError(ScannerBaseException):
    """Raised when Instructor/LLM output fails Pydantic schema validation after max retries."""
    pass


class LLMServiceError(ScannerBaseException):
    """Raised when the upstream LLM API returns connection, timeout, or auth errors."""
    pass


class ExportError(ScannerBaseException):
    """Raised when generating Excel or JSON reports fails."""
    pass


class WebhookDeliveryError(ScannerBaseException):
    """Raised when downstream webhook dispatch (e.g., to n8n) fails."""
    pass
