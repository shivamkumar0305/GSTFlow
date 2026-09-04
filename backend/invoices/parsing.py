"""File parsing for uploaded purchase registers and GSTR-2A/2B statements.

Handles CSV, XLSX (optionally password-protected) and JSON. Parsing is kept
deliberately separate from the reconciliation engine (reconciliation/engine.py)
and from any AI code — this module's only job is turning an uploaded file
into a list of plain dicts with normalized column names.
"""

import io
import json
from datetime import datetime

import msoffcrypto
import pandas as pd

REQUIRED_FIELDS = ["supplier_gstin", "invoice_number"]

# Maps normalized (lowercased, stripped of non-alnum) source column names to
# our canonical field names. Covers the header variants commonly seen in
# GST portal GSTR-2A/2B exports and typical purchase-register templates.
COLUMN_ALIASES = {
    "gstin": "supplier_gstin",
    "gstinofsupplier": "supplier_gstin",
    "suppliergstin": "supplier_gstin",
    "supplierregistrationnumber": "supplier_gstin",
    "gstinuin": "supplier_gstin",
    "suppliername": "supplier_name",
    "tradelegalname": "supplier_name",
    "vendorname": "supplier_name",
    "name": "supplier_name",
    "invoicenumber": "invoice_number",
    "invoiceno": "invoice_number",
    "invno": "invoice_number",
    "documentnumber": "invoice_number",
    "billno": "invoice_number",
    "invoicedate": "invoice_date",
    "invdate": "invoice_date",
    "documentdate": "invoice_date",
    "billdate": "invoice_date",
    "date": "invoice_date",
    "taxablevalue": "taxable_value",
    "taxablevalueinr": "taxable_value",
    "taxableamount": "taxable_value",
    "value": "taxable_value",
    "integratedtax": "tax_amount_igst",
    "centraltax": "tax_amount_cgst",
    "statetax": "tax_amount_sgst",
    "cess": "tax_amount_cess",
    "taxamount": "tax_amount",
    "totaltax": "tax_amount",
    "gstamount": "tax_amount",
}


class FileNeedsPassword(Exception):
    """Raised when a file is encrypted and no (or the wrong) password was given."""


class InvalidFile(Exception):
    """Raised when a file can't be parsed at all (bad format, no usable columns)."""


def _normalize_col(col: str) -> str:
    return "".join(ch for ch in str(col).lower().strip() if ch.isalnum())


def _decrypt_xlsx(file_bytes: bytes, password: str | None) -> bytes:
    """Returns decrypted xlsx bytes. If the file isn't encrypted, returns it
    unchanged. Raises FileNeedsPassword if encrypted and password is missing
    or wrong."""
    buf = io.BytesIO(file_bytes)
    office_file = msoffcrypto.OfficeFile(buf)
    if not office_file.is_encrypted():
        return file_bytes

    if not password:
        raise FileNeedsPassword("This file is password-protected.")

    out = io.BytesIO()
    try:
        office_file.load_key(password=password)
        office_file.decrypt(out)
    except Exception as exc:
        raise FileNeedsPassword("Incorrect password.") from exc
    return out.getvalue()


def _coerce_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _coerce_decimal(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value:
            return 0
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0


def _dataframe_to_rows(df: pd.DataFrame) -> list[dict]:
    df = df.rename(columns={c: COLUMN_ALIASES.get(_normalize_col(c), _normalize_col(c)) for c in df.columns})

    # Combine split CGST/SGST/IGST/cess columns into one tax_amount if a
    # single combined column wasn't present.
    split_tax_cols = [
        c for c in ("tax_amount_igst", "tax_amount_cgst", "tax_amount_sgst", "tax_amount_cess") if c in df.columns
    ]
    if split_tax_cols and "tax_amount" not in df.columns:
        df["tax_amount"] = df[split_tax_cols].apply(
            lambda row: sum(_coerce_decimal(v) for v in row), axis=1
        )

    missing = [f for f in REQUIRED_FIELDS if f not in df.columns]
    if missing:
        raise InvalidFile(
            f"Could not find required column(s) in the file: {', '.join(missing)}. "
            f"Found columns: {', '.join(str(c) for c in df.columns)}"
        )

    rows = []
    for _, row in df.iterrows():
        gstin = str(row.get("supplier_gstin", "")).strip().upper()
        inv_no = str(row.get("invoice_number", "")).strip()
        if not gstin or not inv_no or gstin == "NAN" or inv_no.lower() == "nan":
            continue
        rows.append(
            {
                "supplier_gstin": gstin,
                "supplier_name": str(row.get("supplier_name", "") or "").strip(),
                "invoice_number": inv_no,
                "invoice_date": _coerce_date(row.get("invoice_date")),
                "taxable_value": _coerce_decimal(row.get("taxable_value")),
                "tax_amount": _coerce_decimal(row.get("tax_amount")),
            }
        )
    return rows


def parse_tabular_file(file_bytes: bytes, filename: str, password: str | None = None) -> list[dict]:
    """Parses a CSV or XLSX file into a list of normalized invoice dicts.
    Used for both purchase-register and GSTR-2A/2B XLSX uploads."""
    lower = filename.lower()

    if lower.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as exc:
            raise InvalidFile(f"Could not parse CSV file: {exc}") from exc
        return _dataframe_to_rows(df)

    if lower.endswith(".json"):
        try:
            data = json.loads(file_bytes.decode("utf-8"))
        except Exception as exc:
            raise InvalidFile(f"Could not parse JSON file: {exc}") from exc
        records = data if isinstance(data, list) else data.get("invoices") or data.get("data") or []
        df = pd.DataFrame(records)
        return _dataframe_to_rows(df)

    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        decrypted = _decrypt_xlsx(file_bytes, password)
        try:
            df = pd.read_excel(io.BytesIO(decrypted))
        except Exception as exc:
            raise InvalidFile(f"Could not parse Excel file: {exc}") from exc
        return _dataframe_to_rows(df)

    raise InvalidFile(f"Unsupported file type: {filename}")
