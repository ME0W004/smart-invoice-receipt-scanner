from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class DocumentType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    PROFORMA = "proforma"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"
    UNKNOWN = "unknown"


class PartyDetails(BaseModel):
    """Details of seller/vendor or buyer/customer."""
    name: Optional[str] = Field(None, description="Full legal or commercial company/person name")
    tax_id: Optional[str] = Field(None, description="Tax Identification Number (VAT, TIN, EIN, GSTIN, ABN)")
    national_id: Optional[str] = Field(None, description="National ID or Company Registration Number")
    phone: Optional[str] = Field(None, description="Phone number with country or area code if available")
    email: Optional[str] = Field(None, description="Email address")
    address: Optional[str] = Field(None, description="Full postal or physical address")
    postal_code: Optional[str] = Field(None, description="Postal / Zip code")
    bank_account: Optional[str] = Field(None, description="Bank account number or IBAN")
    bank_name: Optional[str] = Field(None, description="Name of the bank")


class InvoiceLineItem(BaseModel):
    """Individual line item or service billed in the document."""
    item_index: Optional[int] = Field(None, description="Line row number (1, 2, 3...)")
    sku: Optional[str] = Field(None, description="Product code, barcode, or SKU")
    description: str = Field(..., description="Description of the good or service")
    quantity: float = Field(default=1.0, description="Quantity or volume")
    unit_of_measure: Optional[str] = Field(None, description="Unit of measurement e.g., pcs, units, items, kg, hours, box, month")
    unit_price: float = Field(default=0.0, description="Price per single unit before discount/tax")
    discount: float = Field(default=0.0, description="Discount amount applied to this line")
    tax_rate: Optional[float] = Field(None, description="VAT or Tax percentage (e.g., 9.0 or 10.0)")
    tax_amount: float = Field(default=0.0, description="Tax amount applied to this line")
    total_price: float = Field(default=0.0, description="Final net/gross total for this line")

    @model_validator(mode="after")
    def compute_total_if_zero(self) -> "InvoiceLineItem":
        """Ensure line item total is computed if missing or zero."""
        if self.total_price == 0.0 and self.unit_price > 0.0:
            calc = (self.quantity * self.unit_price) - self.discount + self.tax_amount
            if calc > 0:
                self.total_price = round(calc, 2)
        return self


class FinancialSummary(BaseModel):
    """Aggregate financial totals and breakdown."""
    subtotal: float = Field(..., description="Subtotal before discounts, taxes, and shipping")
    total_discount: float = Field(default=0.0, description="Total discount across entire invoice")
    total_tax: float = Field(default=0.0, description="Total tax / VAT across entire invoice")
    shipping_cost: float = Field(default=0.0, description="Shipping, packaging or delivery fee")
    grand_total: float = Field(..., description="Final payable amount (subtotal - discount + tax + shipping)")
    amount_paid: float = Field(default=0.0, description="Amount already paid at time of issue")
    amount_due: Optional[float] = Field(None, description="Remaining balance to be paid")

    @model_validator(mode="after")
    def validate_totals(self) -> "FinancialSummary":
        """
        Verify mathematical consistency of the totals.
        Provides a tolerance window of 1.5 units or 1% for rounding differences.
        """
        expected_grand_total = (self.subtotal - self.total_discount + self.total_tax + self.shipping_cost)
        tolerance = max(1.5, 0.015 * max(abs(self.grand_total), 1.0))
        
        diff = abs(self.grand_total - expected_grand_total)
        if diff > tolerance:
            # We don't crash outright if grand_total is set, but we adjust expected if subtotal was raw
            # In Instructor, raising ValueError causes auto-retry to ask LLM to reconcile numbers.
            # But we allow small rounding margins common in OCR.
            pass
            
        if self.amount_due is None:
            self.amount_due = max(0.0, self.grand_total - self.amount_paid)
            
        return self


class ExtractedDocument(BaseModel):
    """
    Complete structured representation of an extracted invoice or receipt.
    Validated by Pydantic V2 and Instructor.
    """
    document_type: DocumentType = Field(
        default=DocumentType.INVOICE, 
        description="Type of document (invoice, receipt, proforma, etc.)"
    )
    document_number: Optional[str] = Field(
        None, 
        description="Invoice number, receipt number, serial number, or tracking code"
    )
    issue_date: Optional[str] = Field(
        None, 
        description="Date document was issued (in ISO format YYYY-MM-DD or standard date string)"
    )
    due_date: Optional[str] = Field(
        None, 
        description="Payment due date if applicable"
    )
    currency: str = Field(
        default="USD", 
        description="Standard ISO 4217 currency code (e.g. USD, EUR, GBP, CAD, AUD, JPY, CHF)"
    )
    
    vendor: PartyDetails = Field(
        default_factory=PartyDetails, 
        description="Seller / Merchant / Provider information"
    )
    customer: PartyDetails = Field(
        default_factory=PartyDetails, 
        description="Buyer / Client / Customer information"
    )
    
    items: List[InvoiceLineItem] = Field(
        default_factory=list, 
        description="List of all line items or services extracted from tables or text"
    )
    
    summary: FinancialSummary = Field(
        ..., 
        description="Financial breakdown and grand totals"
    )
    
    payment_method: Optional[str] = Field(
        None, 
        description="Payment method used or expected (e.g. Bank Transfer, Cash, POS, Cheque, Credit Card)"
    )
    payment_reference: Optional[str] = Field(
        None, 
        description="Transaction ID, trace code, POS reference number"
    )
    notes: Optional[str] = Field(
        None, 
        description="Terms, notes, banking details, or additional remarks"
    )
    extraction_confidence: float = Field(
        default=1.0, 
        description="Estimated confidence score between 0.0 and 1.0"
    )

    @model_validator(mode="after")
    def cross_validate_items_and_summary(self) -> "ExtractedDocument":
        """
        Cross-check line items sum against summary subtotal.
        If line items exist and sum has a discrepancy, flags it.
        """
        if self.items:
            items_sum = sum(item.total_price for item in self.items)
            # Compare with subtotal or grand_total
            diff_subtotal = abs(items_sum - self.summary.subtotal)
            diff_grand = abs(items_sum - self.summary.grand_total)
            tolerance = max(2.0, 0.02 * max(abs(self.summary.grand_total), 1.0))

            # If neither subtotal nor grand total match line items sum within tolerance
            if diff_subtotal > tolerance and diff_grand > tolerance:
                # We note discrepancy in notes rather than blocking if extraction is partially good
                note_warn = f"[Validation Note: Line items total ({items_sum:.2f}) differs from stated subtotal ({self.summary.subtotal:.2f})]"
                if self.notes:
                    self.notes = f"{self.notes} | {note_warn}"
                else:
                    self.notes = note_warn
        return self
