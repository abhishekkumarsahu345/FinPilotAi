"""
Invoice and bank statement file parsing utilities.
All monetary values are converted to integer Minor_Units (paise = amount × 100).
"""
import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import openpyxl

REQUIRED_INVOICE_COLUMNS = {
    "invoice_number", "invoice_date", "due_date", "customer_name",
    "subtotal", "tax", "total",
}
OPTIONAL_INVOICE_COLUMNS = {"discount", "notes", "currency"}

REQUIRED_BANK_COLUMNS_CANONICAL = {
    "transaction_date", "description", "debit_amount", "credit_amount", "account_identifier",
}


def to_minor(value: Any) -> tuple[int | None, str | None]:
    """
    Convert a decimal amount string/number to integer paise.
    Returns (minor_units, error_message).
    """
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"))
        if d < 0:
            return None, "Amount must be non-negative"
        return int(d * 100), None
    except (InvalidOperation, TypeError, ValueError):
        return None, f"Invalid amount: {value!r}"


def parse_date(value: Any) -> tuple[date | None, str | None]:
    """Parse a date string in YYYY-MM-DD, DD/MM/YYYY, or DD-MM-YYYY format."""
    if isinstance(value, date):
        return value, None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(str(value).strip(), fmt).date(), None
        except ValueError:
            continue
    return None, f"Unrecognised date: {value!r}. Use YYYY-MM-DD."


def read_rows(file_bytes: bytes, filename: str) -> tuple[list[dict], str | None]:
    """
    Parse CSV or XLSX file into a list of row dicts.
    Returns (rows, error_message).
    """
    name_lower = filename.lower()
    if name_lower.endswith(".csv"):
        try:
            text = file_bytes.decode("utf-8-sig")  # Handle BOM
            reader = csv.DictReader(io.StringIO(text))
            rows = [dict(r) for r in reader]
            if not rows:
                return [], "File contains no data rows."
            return rows, None
        except Exception as exc:
            return [], f"Could not parse CSV: {exc}"
    elif name_lower.endswith(".xlsx"):
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            ws = wb.active
            headers = [str(c.value).strip() if c.value else "" for c in next(ws.iter_rows(max_row=1))]
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if all(v is None for v in row):
                    continue
                rows.append(dict(zip(headers, [str(v) if v is not None else "" for v in row])))
            if not rows:
                return [], "File contains no data rows."
            return rows, None
        except Exception as exc:
            return [], f"Could not parse XLSX: {exc}"
    else:
        return [], "Unsupported file type. Upload CSV or XLSX."


def validate_invoice_row(row: dict, row_num: int, org_customers: dict) -> dict:
    """
    Validate a single invoice import row.
    org_customers: {name_lower: customer_id}
    Returns normalized_data or populates errors list.
    """
    errors = []
    warnings = []
    normalized = {}

    # Invoice number
    inv_num = str(row.get("invoice_number", "")).strip()
    if not inv_num:
        errors.append({"field": "invoice_number", "message": "Invoice number is required."})
    else:
        normalized["invoice_number"] = inv_num

    # Dates
    for field in ("invoice_date", "due_date"):
        raw = str(row.get(field, "")).strip()
        parsed, err = parse_date(raw)
        if err:
            errors.append({"field": field, "message": err})
        else:
            normalized[field] = parsed

    # Customer
    cust_name = str(row.get("customer_name", "")).strip()
    if not cust_name:
        errors.append({"field": "customer_name", "message": "Customer name is required."})
    else:
        cust_id = org_customers.get(cust_name.lower())
        if cust_id is None:
            errors.append({
                "field": "customer_name",
                "message": f"Customer '{cust_name}' not found in this organization.",
            })
        else:
            normalized["customer_id"] = cust_id

    # Amounts
    for field, col in [("subtotal_minor", "subtotal"), ("tax_minor", "tax"), ("total_minor", "total")]:
        raw = str(row.get(col, "0")).strip() or "0"
        minor, err = to_minor(raw)
        if err:
            errors.append({"field": col, "message": err})
        else:
            normalized[field] = minor

    disc_raw = str(row.get("discount", "0")).strip() or "0"
    disc_minor, err = to_minor(disc_raw)
    if err:
        errors.append({"field": "discount", "message": err})
    else:
        normalized["discount_minor"] = disc_minor

    # Verify calculated total vs supplied total
    if not errors:
        calc_total = (
            normalized.get("subtotal_minor", 0)
            - normalized.get("discount_minor", 0)
            + normalized.get("tax_minor", 0)
        )
        if calc_total != normalized.get("total_minor"):
            errors.append({
                "field": "total",
                "message": (
                    f"Calculated total ({calc_total / 100:.2f}) does not match "
                    f"file total ({normalized.get('total_minor', 0) / 100:.2f})."
                ),
            })
        else:
            # Use the calculated total as authoritative
            normalized["total_minor"] = calc_total

    # Currency
    currency = str(row.get("currency", "INR")).strip().upper() or "INR"
    normalized["currency"] = currency

    # Notes
    normalized["notes"] = str(row.get("notes", "")).strip()

    return {"row_number": row_num, "normalized": normalized, "errors": errors, "warnings": warnings}
