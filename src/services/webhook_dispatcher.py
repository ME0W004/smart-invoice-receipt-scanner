import time
from typing import Dict, Any, Optional
import httpx
from config.settings import get_settings
from src.core.logger import app_logger
from src.core.exceptions import WebhookDeliveryError
from src.extractor.schemas import ExtractedDocument


class WebhookDispatcher:
    """
    Dispatches extracted structured invoice data to downstream automation systems (e.g. n8n).
    Includes automatic retry mechanism and delivery telemetry.
    """

    def __init__(self):
        self.settings = get_settings()

    def dispatch(
        self, 
        document: ExtractedDocument, 
        original_filename: str, 
        parsing_metadata: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3
    ) -> bool:
        """
        Send payload to configured N8N_WEBHOOK_URL.
        
        Args:
            document: Extracted and validated document.
            original_filename: Source filename.
            parsing_metadata: Metadata from Docling parser.
            max_attempts: Number of retry attempts.
            
        Returns:
            bool: True if delivered successfully.
        """
        target_url = self.settings.N8N_WEBHOOK_URL
        if not target_url:
            app_logger.debug("N8N_WEBHOOK_URL not configured. Skipping webhook dispatch.")
            return False

        payload = {
            "status": "success",
            "source_filename": original_filename,
            "document": document.model_dump(),
            "metadata": parsing_metadata or {},
        }

        app_logger.info(f"Dispatching document '{original_filename}' to webhook: {target_url}")

        attempt = 0
        backoff = 1.0

        while attempt < max_attempts:
            attempt += 1
            try:
                with httpx.Client(timeout=self.settings.WEBHOOK_TIMEOUT_SECONDS) as client:
                    response = client.post(
                        target_url,
                        json=payload,
                        headers={"Content-Type": "application/json", "User-Agent": "SmartInvoiceScanner/1.0"}
                    )
                    
                    if 200 <= response.status_code < 300:
                        app_logger.success(
                            f"Webhook delivered successfully to {target_url} (HTTP {response.status_code})"
                        )
                        return True
                    else:
                        app_logger.warning(
                            f"Webhook returned non-200 code {response.status_code}: {response.text[:200]}"
                        )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                app_logger.warning(f"Webhook connection attempt {attempt}/{max_attempts} failed: {e}")

            time.sleep(backoff)
            backoff *= 2.0

        error_msg = f"Failed to deliver webhook to {target_url} after {max_attempts} attempts."
        app_logger.error(error_msg)
        raise WebhookDeliveryError(error_msg, details={"target_url": target_url, "attempts": max_attempts})
