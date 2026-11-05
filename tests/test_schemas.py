import pytest
from pydantic import ValidationError
from src.extractor.schemas import (
    DocumentType,
    PartyDetails,
    InvoiceLineItem,
    FinancialSummary,
    ExtractedDocument,
)


def test_invoice_line_item_auto_computation():
    """Test that line total is automatically computed if unit_price and quantity are given."""
    item = InvoiceLineItem(
        description="Cloud Hosting Service",
        quantity=2.0,
        unit_price=150.0,
        discount=20.0,
        tax_amount=25.2,
    )
    # total = (2 * 150) - 20 + 25.2 = 305.2
    assert item.total_price == 305.2


def test_financial_summary_validation():
    """Test financial summary creation and amount_due auto-calculation."""
    summary = FinancialSummary(
        subtotal=1000.0,
        total_discount=100.0,
        total_tax=90.0,
        shipping_cost=10.0,
        grand_total=1000.0,
        amount_paid=400.0,
    )
    assert summary.amount_due == 600.0


def test_full_extracted_document_validation():
    """Test end-to-end schema validation for a complete corporate invoice."""
    doc_data = {
        "document_type": "invoice",
        "document_number": "INV-2026-089",
        "issue_date": "2026-11-05",
        "due_date": "2026-11-20",
        "currency": "USD",
        "vendor": {
            "name": "Tech Corp Solutions Ltd.",
            "tax_id": "VAT-99887766",
            "phone": "+1-555-0199",
            "email": "billing@techcorp.com",
            "address": "100 Silicon Way, Tech City",
        },
        "customer": {
            "name": "Global Traders Inc.",
            "tax_id": "US-TAX-12345",
            "phone": "+1-555-0200",
            "email": "procurement@globaltraders.com",
        },
        "items": [
            {
                "item_index": 1,
                "sku": "SRV-001",
                "description": "Server Maintenance (Monthly)",
                "quantity": 1.0,
                "unit_price": 500.0,
                "discount": 0.0,
                "tax_rate": 10.0,
                "tax_amount": 50.0,
                "total_price": 550.0,
            },
            {
                "item_index": 2,
                "sku": "LIC-002",
                "description": "Enterprise Security License",
                "quantity": 5.0,
                "unit_price": 100.0,
                "discount": 50.0,
                "tax_rate": 10.0,
                "tax_amount": 45.0,
                "total_price": 495.0,
            }
        ],
        "summary": {
            "subtotal": 1000.0,
            "total_discount": 50.0,
            "total_tax": 95.0,
            "shipping_cost": 0.0,
            "grand_total": 1045.0,
            "amount_paid": 0.0,
        },
        "payment_method": "Bank Wire",
        "notes": "Net 15 payment terms apply."
    }

    doc = ExtractedDocument(**doc_data)
    assert doc.document_number == "INV-2026-089"
    assert doc.vendor.name == "Tech Corp Solutions Ltd."
    assert len(doc.items) == 2
    assert doc.summary.grand_total == 1045.0
    assert doc.document_type == DocumentType.INVOICE


def test_missing_required_fields_raises_validation_error():
    """Ensure missing summary fails validation (Pydantic enforcement)."""
    with pytest.raises(ValidationError):
        ExtractedDocument(
            document_number="INV-001",
            # Missing summary
        )
