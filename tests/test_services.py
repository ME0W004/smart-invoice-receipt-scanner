import json
from pathlib import Path
from src.extractor.schemas import (
    DocumentType,
    PartyDetails,
    InvoiceLineItem,
    FinancialSummary,
    ExtractedDocument,
)
from src.services.excel_exporter import ExcelExporter
from src.services.file_manager import FileManager


def test_excel_export_generation(tmp_path):
    """Test generating a styled Excel file with summary and line item sheets."""
    exporter = ExcelExporter()
    # Override output dir to tmp_path for test
    exporter.settings.STORAGE_OUTPUT_DIR = tmp_path

    doc = ExtractedDocument(
        document_type=DocumentType.RECEIPT,
        document_number="REC-5544",
        issue_date="2026-11-05",
        currency="EUR",
        vendor=PartyDetails(name="Cafe Central", phone="+49-12345678"),
        customer=PartyDetails(name="John Doe"),
        items=[
            InvoiceLineItem(description="Espresso", quantity=2.0, unit_price=3.5, total_price=7.0),
            InvoiceLineItem(description="Croissant", quantity=1.0, unit_price=4.0, total_price=4.0),
        ],
        summary=FinancialSummary(
            subtotal=11.0,
            grand_total=11.0,
        )
    )

    generated_file = exporter.export_to_excel(doc, "sample_receipt.pdf")
    assert generated_file.exists()
    assert generated_file.suffix == ".xlsx"


def test_file_manager_json_export(tmp_path):
    """Test saving JSON output via FileManager."""
    fm = FileManager()
    fm.settings.STORAGE_OUTPUT_DIR = tmp_path

    data = {"invoice_number": "INV-100", "total": 500.0}
    json_path = fm.save_json_output(data, "invoice.pdf")

    assert json_path.exists()
    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["invoice_number"] == "INV-100"
