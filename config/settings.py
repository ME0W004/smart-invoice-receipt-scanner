from functools import lru_cache
from pathlib import Path
from typing import Optional
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel
    class BaseSettings(BaseModel):
        pass
    SettingsConfigDict = dict
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    Follows 12-Factor App methodology.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --- LLM Provider Configuration ---
    LLM_PROVIDER: str = Field(default="openai", description="LLM provider name: openai, deepseek, ollama, openrouter")
    LLM_API_KEY: str = Field(default="sk-placeholder", description="API Key for the LLM service")
    LLM_BASE_URL: str = Field(default="https://api.openai.com/v1", description="OpenAI-compatible Base URL")
    LLM_MODEL_NAME: str = Field(default="gpt-4o-mini", description="Model name to use for extraction")
    LLM_TEMPERATURE: float = Field(default=0.0, description="Sampling temperature (0 for deterministic extraction)")
    LLM_MAX_RETRIES: int = Field(default=3, description="Instructor auto-retry attempts on validation failure")
    LLM_TIMEOUT_SECONDS: float = Field(default=60.0, description="Timeout for LLM API requests")

    # --- IBM Docling Engine Configuration ---
    DOCLING_TABLE_MODE: str = Field(default="accurate", description="Table structure mode: accurate or fast")
    DOCLING_DO_OCR: bool = Field(default=True, description="Enable OCR for scanned images/PDFs")
    DOCLING_OCR_ENGINE: str = Field(default="rapidocr", description="OCR engine: rapidocr, easyocr, tesseract")
    DOCLING_CACHE_DIR: Path = Field(default=Path("./storage/.cache/docling"))

    # --- Storage & Watcher Paths (Paperless-ngx pattern) ---
    STORAGE_CONSUME_DIR: Path = Field(default=Path("./storage/consume"))
    STORAGE_ARCHIVE_DIR: Path = Field(default=Path("./storage/archive"))
    STORAGE_ERROR_DIR: Path = Field(default=Path("./storage/error"))
    STORAGE_OUTPUT_DIR: Path = Field(default=Path("./storage/output"))
    WATCHER_POLL_INTERVAL: float = Field(default=2.0, description="Seconds between directory scans")
    WATCHER_DEBOUNCE_SECONDS: float = Field(default=3.0, description="Debounce wait to ensure file write completed")

    # --- Downstream n8n & Exporters ---
    N8N_WEBHOOK_URL: Optional[str] = Field(default=None, description="n8n inbound webhook URL")
    WEBHOOK_TIMEOUT_SECONDS: float = Field(default=15.0, description="Webhook HTTP timeout")
    ENABLE_EXCEL_EXPORT: bool = Field(default=True, description="Export results as formatted Excel workbook")
    ENABLE_JSON_EXPORT: bool = Field(default=True, description="Export raw structured JSON")

    # --- API Server ---
    API_HOST: str = Field(default="0.0.0.0", description="FastAPI host binding")
    API_PORT: int = Field(default=8000, description="FastAPI port")
    API_DEBUG: bool = Field(default=False, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")

    def ensure_directories(self) -> None:
        """Create storage directories if they do not exist."""
        for path in [
            self.STORAGE_CONSUME_DIR,
            self.STORAGE_ARCHIVE_DIR,
            self.STORAGE_ERROR_DIR,
            self.STORAGE_OUTPUT_DIR,
            self.DOCLING_CACHE_DIR
        ]:
            path.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    settings = Settings()
    settings.ensure_directories()
    return settings
