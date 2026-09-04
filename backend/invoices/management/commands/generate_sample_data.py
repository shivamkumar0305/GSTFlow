"""Generates a synthetic purchase-register CSV and a matching GSTR-2A XLSX
with deliberate mismatches, so the reconciliation engine has real data to
chew on during development/demo instead of an empty database.

Usage: python manage.py generate_sample_data [--out sample_data]
"""

from datetime import date
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

SUPPLIERS = [
    ("27AAAAA0000A1Z5", "Sharma Traders"),
    ("29BBBBB1111B2Z8", "Karnataka Steel Co"),
    ("07CCCCC2222C3Z1", "Delhi Packaging Ltd"),
    ("36DDDDD3333D4Z6", "Hyderabad Electronics"),
    ("24EEEEE4444E5Z2", "Gujarat Textiles"),
]


class Command(BaseCommand):
    help = "Generate a synthetic purchase register + GSTR-2A pair with deliberate mismatches."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="sample_data")

    def handle(self, *args, **options):
        out_dir = Path(options["out"])
        out_dir.mkdir(exist_ok=True)

        books_rows = []
        stmt_rows = []

        def add_pair(inv_no, gstin, name, taxable, tax, inv_date, *, books=True, stmt=True,
                     stmt_gstin=None, stmt_taxable=None, stmt_tax=None, stmt_date=None):
            if books:
                books_rows.append(
                    {
                        "GSTIN of Supplier": gstin,
                        "Supplier Name": name,
                        "Invoice Number": inv_no,
                        "Invoice Date": inv_date.strftime("%d-%m-%Y"),
                        "Taxable Value": taxable,
                        "Tax Amount": tax,
                    }
                )
            if stmt:
                stmt_rows.append(
                    {
                        "GSTIN of Supplier": stmt_gstin or gstin,
                        "Trade/Legal Name": name,
                        "Invoice Number": inv_no,
                        "Invoice Date": (stmt_date or inv_date).strftime("%d-%m-%Y"),
                        "Taxable Value": stmt_taxable if stmt_taxable is not None else taxable,
                        "Integrated Tax": 0,
                        "Central Tax": (stmt_tax if stmt_tax is not None else tax) / 2,
                        "State Tax": (stmt_tax if stmt_tax is not None else tax) / 2,
                    }
                )

        # 1. Clean matches
        for i in range(1, 6):
            gstin, name = SUPPLIERS[i % len(SUPPLIERS)]
            add_pair(f"INV-{1000 + i}", gstin, name, 10000 + i * 250, 1800 + i * 45, date(2026, 4, 5 + i))

        # 2. Missing in 2A — supplier hasn't filed yet
        gstin, name = SUPPLIERS[0]
        add_pair("INV-2001", gstin, name, 22000, 3960, date(2026, 4, 12), stmt=False)

        # 3. Missing in books — business forgot to record it
        gstin, name = SUPPLIERS[1]
        add_pair("INV-3001", gstin, name, 15000, 2700, date(2026, 4, 15), books=False)

        # 4. Value mismatch
        gstin, name = SUPPLIERS[2]
        add_pair("INV-4001", gstin, name, 18000, 3240, date(2026, 4, 18), stmt_taxable=18500, stmt_tax=3240)

        # 5. Duplicate in books (booked twice by mistake)
        gstin, name = SUPPLIERS[3]
        add_pair("INV-5001", gstin, name, 9000, 1620, date(2026, 4, 20))
        books_rows.append(dict(books_rows[-1]))  # exact duplicate row

        # 6. GSTIN typo (one character off) between books and 2A
        gstin, name = SUPPLIERS[4]
        typo_gstin = gstin[:-1] + ("6" if gstin[-1] != "6" else "7")
        add_pair("INV-6001", gstin, name, 12000, 2160, date(2026, 4, 22), stmt_gstin=typo_gstin)

        # 7. Date mismatch
        gstin, name = SUPPLIERS[0]
        add_pair(
            "INV-7001", gstin, name, 8000, 1440, date(2026, 4, 25), stmt_date=date(2026, 4, 29)
        )

        books_df = pd.DataFrame(books_rows)
        stmt_df = pd.DataFrame(stmt_rows)

        books_path = out_dir / "purchase_register.csv"
        stmt_path = out_dir / "gstr2a.xlsx"
        books_df.to_csv(books_path, index=False)
        stmt_df.to_excel(stmt_path, index=False)

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(books_df)} rows to {books_path}"))
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(stmt_df)} rows to {stmt_path}"))
        self.stdout.write("Upload these via /api/uploads/purchase-register/ and /api/uploads/gstr2a/.")
