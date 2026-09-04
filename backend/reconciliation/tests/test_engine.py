from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from reconciliation import engine


def record(id, gstin, inv_no, taxable=1000, tax=180, inv_date=None, source="books"):
    return {
        "id": id,
        "supplier_gstin": gstin,
        "invoice_number": inv_no,
        "invoice_date": inv_date or date(2026, 4, 5),
        "taxable_value": Decimal(str(taxable)),
        "tax_amount": Decimal(str(tax)),
        "source": source,
    }


class ReconcileTests(SimpleTestCase):
    def test_exact_match(self):
        books = [record(1, "27AAAAA0000A1Z5", "INV-1")]
        stmt = [record(2, "27AAAAA0000A1Z5", "INV-1", source="2a")]
        results = engine.reconcile(books, stmt)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].discrepancy_type, engine.MATCHED)

    def test_missing_in_2a(self):
        books = [record(1, "27AAAAA0000A1Z5", "INV-1")]
        results = engine.reconcile(books, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].discrepancy_type, engine.MISSING_IN_2A)
        self.assertEqual(results[0].books_invoice_id, 1)

    def test_missing_in_books(self):
        stmt = [record(1, "27AAAAA0000A1Z5", "INV-1", source="2a")]
        results = engine.reconcile([], stmt)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].discrepancy_type, engine.MISSING_IN_BOOKS)
        self.assertEqual(results[0].statement_invoice_id, 1)

    def test_value_mismatch_beyond_tolerance(self):
        books = [record(1, "27AAAAA0000A1Z5", "INV-1", taxable=1000, tax=180)]
        stmt = [record(2, "27AAAAA0000A1Z5", "INV-1", taxable=1050, tax=180, source="2a")]
        results = engine.reconcile(books, stmt, value_tolerance=Decimal("1.00"))
        self.assertEqual(results[0].discrepancy_type, engine.VALUE_MISMATCH)

    def test_value_within_tolerance_is_matched(self):
        books = [record(1, "27AAAAA0000A1Z5", "INV-1", taxable=1000.00, tax=180.00)]
        stmt = [record(2, "27AAAAA0000A1Z5", "INV-1", taxable=1000.40, tax=180.00, source="2a")]
        results = engine.reconcile(books, stmt, value_tolerance=Decimal("1.00"))
        self.assertEqual(results[0].discrepancy_type, engine.MATCHED)

    def test_duplicate_within_source(self):
        books = [
            record(1, "27AAAAA0000A1Z5", "INV-1"),
            record(2, "27AAAAA0000A1Z5", "INV-1"),
        ]
        results = engine.reconcile(books, [])
        types = sorted(r.discrepancy_type for r in results)
        self.assertIn(engine.DUPLICATE, types)
        self.assertIn(engine.MISSING_IN_2A, types)

    def test_gstin_typo_detected_as_gstin_mismatch(self):
        books = [record(1, "27AAAAA0000A1Z5", "INV-1", taxable=1000, tax=180)]
        # one character off
        stmt = [record(2, "27AAAAA0000A1Z6", "INV-1", taxable=1000, tax=180, source="2a")]
        results = engine.reconcile(books, stmt)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].discrepancy_type, engine.GSTIN_MISMATCH)

    def test_completely_different_gstin_not_fuzzy_matched(self):
        books = [record(1, "27AAAAA0000A1Z5", "INV-1")]
        stmt = [record(2, "09BBBBB1111B2Z8", "INV-1", source="2a")]
        results = engine.reconcile(books, stmt)
        types = sorted(r.discrepancy_type for r in results)
        self.assertEqual(types, [engine.MISSING_IN_2A, engine.MISSING_IN_BOOKS])

    def test_date_mismatch(self):
        books = [record(1, "27AAAAA0000A1Z5", "INV-1", inv_date=date(2026, 4, 5))]
        stmt = [record(2, "27AAAAA0000A1Z5", "INV-1", inv_date=date(2026, 4, 9), source="2a")]
        results = engine.reconcile(books, stmt)
        self.assertEqual(results[0].discrepancy_type, engine.DATE_MISMATCH)

    def test_invoice_number_normalization_ignores_case_and_spacing(self):
        books = [record(1, "27AAAAA0000A1Z5", " inv-001 ")]
        stmt = [record(2, "27AAAAA0000A1Z5", "INV001", source="2a")]
        results = engine.reconcile(books, stmt)
        self.assertEqual(results[0].discrepancy_type, engine.MATCHED)
