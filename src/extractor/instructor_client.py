from typing import Optional

try:
    import instructor
    from openai import OpenAI, APIError, APIConnectionError, RateLimitError
except ImportError:
    instructor = None
    OpenAI = None
    APIError = Exception
    APIConnectionError = Exception
    RateLimitError = Exception

from config.settings import get_settings
from src.core.logger import app_logger
from src.core.exceptions import ExtractionValidationError, LLMServiceError
from src.extractor.schemas import ExtractedDocument


SYSTEM_PROMPT = """You are an expert AI financial document analyst and forensic auditor.
Your job is to examine structured markdown extracted from invoices, receipts, and financial statements by IBM Docling, and transform it into a perfectly validated structured JSON conforming to the requested schema.

Guidelines:
1. Precision is paramount. Extract every line item with its exact description, quantity, unit price, tax, and total.
2. If tables are present in the markdown, parse each row accurately. Do not skip or merge separate line items.
3. Extract Party Details: Find the exact Vendor/Seller and Customer/Buyer legal names, tax IDs (VAT, TIN, شناسه ملی، کد اقتصادی), addresses, and phones.
4. Mathematical verification: Ensure subtotal, discounts, taxes (VAT), shipping, and grand total are logically aligned.
5. Currency: Detect the currency (USD, EUR, IRR, IRT, GBP, AED, etc.). If Persian Toman/Rial is used, specify IRR or IRT.
6. Dates: Normalize dates to ISO format (YYYY-MM-DD) when possible. If a Shamsi/Jalali date (e.g. 1403/08/15) is present, preserve it or convert to YYYY-MM-DD.
7. Return only validated data conforming strictly to the requested ExtractedDocument schema.
"""


class FinancialExtractor:
    """
    LLM extraction service utilizing Instructor for Pydantic V2 schema enforcement
    and automatic error correction via LLM feedback loops.
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = self._init_client()

    def _init_client(self):
        """Initialize instructor-wrapped OpenAI client."""
        if instructor is None or OpenAI is None:
            app_logger.warning("instructor or openai packages are not installed in current environment.")
            return None

        raw_client = OpenAI(
            api_key=self.settings.LLM_API_KEY,
            base_url=self.settings.LLM_BASE_URL,
            timeout=self.settings.LLM_TIMEOUT_SECONDS
        )
        # Patch client with instructor for automatic response_model parsing
        return instructor.from_openai(raw_client)

    def extract_from_markdown(
        self, 
        markdown_content: str, 
        document_filename: Optional[str] = None
    ) -> ExtractedDocument:
        """
        Extract structured invoice/receipt data from Docling-generated markdown.
        
        Args:
            markdown_content: Clean markdown representation of the document.
            document_filename: Optional filename for logging and context.
            
        Returns:
            ExtractedDocument: Fully validated Pydantic model.
        """
        if self.client is None:
            raise LLMServiceError(
                "LLM client could not be initialized because 'instructor' or 'openai' packages are missing."
            )

        app_logger.info(
            f"Starting LLM extraction for '{document_filename or 'document'}' "
            f"using model '{self.settings.LLM_MODEL_NAME}'..."
        )

        user_content = f"Document Filename: {document_filename or 'Unknown'}\n\nDocument Content:\n{markdown_content}"

        try:
            extracted: ExtractedDocument = self.client.chat.completions.create(
                model=self.settings.LLM_MODEL_NAME,
                response_model=ExtractedDocument,
                max_retries=self.settings.LLM_MAX_RETRIES,
                temperature=self.settings.LLM_TEMPERATURE,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ]
            )

            app_logger.success(
                f"Extraction succeeded for '{document_filename}': "
                f"Type={extracted.document_type.value}, Total={extracted.summary.grand_total} {extracted.currency}, "
                f"Items Count={len(extracted.items)}"
            )
            return extracted

        except (RateLimitError, APIConnectionError) as e:
            app_logger.error(f"LLM API network/rate limit error: {e}")
            raise LLMServiceError(f"LLM upstream connection error: {str(e)}", details={"error": str(e)})

        except APIError as e:
            app_logger.error(f"LLM API returned an error: {e}")
            raise LLMServiceError(f"LLM API error: {str(e)}", details={"code": getattr(e, "code", None)})

        except Exception as e:
            app_logger.error(f"Failed to extract structured data after retries: {e}")
            raise ExtractionValidationError(
                f"Pydantic validation failed for document extraction: {str(e)}",
                details={"filename": document_filename, "error": str(e)}
            )
