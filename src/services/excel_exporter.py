from datetime import datetime
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config.settings import get_settings
from src.core.logger import app_logger
from src.core.exceptions import ExportError
from src.extractor.schemas import ExtractedDocument


class ExcelExporter:
    """
    Industrial Excel generator formatting financial documents into multi-sheet workbooks.
    Sheet 1: Invoice Overview & Parties
    Sheet 2: Detailed Line Items
    """

    def __init__(self):
        self.settings = get_settings()

    def export_to_excel(self, document: ExtractedDocument, original_filename: str) -> Path:
        """
        Generate a styled Excel workbook from an ExtractedDocument model.
        
        Args:
            document: Extracted and validated document.
            original_filename: Name of the original source file.
            
        Returns:
            Path: Path to the generated .xlsx file.
        """
        try:
            wb = openpyxl.Workbook()
            
            # --- Styles Definition ---
            header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
            sub_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
            zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
            total_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
            
            white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            bold_font = Font(name="Calibri", size=11, bold=True)
            title_font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
            
            thin_border = Border(
                left=Side(style='thin', color='D9D9D9'),
                right=Side(style='thin', color='D9D9D9'),
                top=Side(style='thin', color='D9D9D9'),
                bottom=Side(style='thin', color='D9D9D9')
            )

            # -------------------------------------------------------------
            # SHEET 1: Document Summary & Parties
            # -------------------------------------------------------------
            ws_summary = wb.active
            ws_summary.title = "Summary & Overview"
            ws_summary.views.sheetView[0].showGridLines = True

            # Document Title
            ws_summary["A1"] = f"DOCUMENT AUDIT REPORT: {document.document_type.value.upper()}"
            ws_summary["A1"].font = title_font
            ws_summary.row_dimensions[1].height = 25

            # Basic Info Block
            info_rows = [
                ("Document Number", document.document_number or "N/A"),
                ("Issue Date", document.issue_date or "N/A"),
                ("Due Date", document.due_date or "N/A"),
                ("Currency", document.currency),
                ("Payment Method", document.payment_method or "N/A"),
                ("Payment Reference", document.payment_reference or "N/A"),
            ]

            ws_summary.append([])
            ws_summary.append(["Metadata Field", "Value"])
            meta_header_row = ws_summary.max_row
            for col in range(1, 3):
                cell = ws_summary.cell(row=meta_header_row, column=col)
                cell.fill = header_fill
                cell.font = white_bold

            for field, val in info_rows:
                ws_summary.append([field, val])
                row_idx = ws_summary.max_row
                ws_summary.cell(row=row_idx, column=1).font = bold_font
                for col in range(1, 3):
                    ws_summary.cell(row=row_idx, column=col).border = thin_border

            # Vendor & Customer Parties
            ws_summary.append([])
            ws_summary.append(["Party Section", "Vendor / Seller", "Customer / Buyer"])
            party_header_row = ws_summary.max_row
            for col in range(1, 4):
                cell = ws_summary.cell(row=party_header_row, column=col)
                cell.fill = header_fill
                cell.font = white_bold

            party_fields = [
                ("Name", document.vendor.name, document.customer.name),
                ("Tax ID / VAT", document.vendor.tax_id, document.customer.tax_id),
                ("National / Reg ID", document.vendor.national_id, document.customer.national_id),
                ("Phone", document.vendor.phone, document.customer.phone),
                ("Email", document.vendor.email, document.customer.email),
                ("Address", document.vendor.address, document.customer.address),
                ("Bank / Account", document.vendor.bank_account, document.customer.bank_account),
            ]

            for label, v_val, c_val in party_fields:
                ws_summary.append([label, v_val or "-", c_val or "-"])
                row_idx = ws_summary.max_row
                ws_summary.cell(row=row_idx, column=1).font = bold_font
                for col in range(1, 4):
                    ws_summary.cell(row=row_idx, column=col).border = thin_border

            # Financial Totals Block
            ws_summary.append([])
            ws_summary.append(["Financial Breakdown", "Amount"])
            fin_header_row = ws_summary.max_row
            for col in range(1, 3):
                cell = ws_summary.cell(row=fin_header_row, column=col)
                cell.fill = header_fill
                cell.font = white_bold

            totals_data = [
                ("Subtotal", document.summary.subtotal),
                ("Total Discount (-)", document.summary.total_discount),
                ("Total Tax / VAT (+)", document.summary.total_tax),
                ("Shipping / Fees (+)", document.summary.shipping_cost),
                ("Grand Total", document.summary.grand_total),
                ("Amount Paid", document.summary.amount_paid),
                ("Amount Due", document.summary.amount_due or 0.0),
            ]

            for label, amount in totals_data:
                ws_summary.append([label, amount])
                row_idx = ws_summary.max_row
                ws_summary.cell(row=row_idx, column=1).font = bold_font
                num_cell = ws_summary.cell(row=row_idx, column=2)
                num_cell.number_format = '#,##0.00'
                if label == "Grand Total":
                    ws_summary.cell(row=row_idx, column=1).fill = total_fill
                    num_cell.fill = total_fill
                    num_cell.font = bold_font
                for col in range(1, 3):
                    ws_summary.cell(row=row_idx, column=col).border = thin_border

            # Notes
            if document.notes:
                ws_summary.append([])
                ws_summary.append(["Notes & Terms:", document.notes])
                ws_summary.cell(row=ws_summary.max_row, column=1).font = bold_font

            # Adjust Column widths for Summary
            for col in ws_summary.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws_summary.column_dimensions[col_letter].width = max(max_len + 4, 18)

            # -------------------------------------------------------------
            # SHEET 2: Line Items Detail
            # -------------------------------------------------------------
            ws_items = wb.create_sheet(title="Line Items")
            ws_items.views.sheetView[0].showGridLines = True

            item_headers = [
                "#", "SKU / Code", "Description", "Qty", "Unit", 
                "Unit Price", "Discount", "Tax %", "Tax Amount", "Line Total"
            ]
            ws_items.append(item_headers)
            for col_idx in range(1, len(item_headers) + 1):
                cell = ws_items.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = white_bold
                cell.alignment = Alignment(horizontal="center", vertical="center")
            ws_items.row_dimensions[1].height = 24

            for idx, item in enumerate(document.items, start=1):
                row_data = [
                    item.item_index or idx,
                    item.sku or "",
                    item.description,
                    item.quantity,
                    item.unit_of_measure or "",
                    item.unit_price,
                    item.discount,
                    f"{item.tax_rate}%" if item.tax_rate is not None else "",
                    item.tax_amount,
                    item.total_price
                ]
                ws_items.append(row_data)
                curr_row = ws_items.max_row
                
                # Apply borders and formatting
                for c_idx in range(1, len(item_headers) + 1):
                    c = ws_items.cell(row=curr_row, column=c_idx)
                    c.border = thin_border
                    if idx % 2 == 0:
                        c.fill = zebra_fill
                    if c_idx in [4, 6, 7, 9, 10]:
                        c.number_format = '#,##0.00'

            # Add Totals Row in Line Items Sheet
            if document.items:
                sum_row = ws_items.max_row + 1
                ws_items.cell(row=sum_row, column=3, value="Total Line Items Sum:").font = bold_font
                ws_items.cell(row=sum_row, column=3).alignment = Alignment(horizontal="right")
                total_cell = ws_items.cell(row=sum_row, column=10, value=f"=SUM(J2:J{sum_row-1})")
                total_cell.font = bold_font
                total_cell.fill = total_fill
                total_cell.number_format = '#,##0.00'
                total_cell.border = thin_border

            # Adjust Column widths for Items
            for col in ws_items.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws_items.column_dimensions[col_letter].width = max(max_len + 3, 12)

            # Save Workbook
            stem = Path(original_filename).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.settings.STORAGE_OUTPUT_DIR / f"{timestamp}_{stem}.xlsx"
            wb.save(output_path)
            
            app_logger.info(f"Successfully generated Excel workbook: {output_path}")
            return output_path

        except Exception as e:
            app_logger.error(f"Failed to generate Excel file: {e}")
            raise ExportError(f"Excel export failed: {str(e)}", details={"error": str(e)})
