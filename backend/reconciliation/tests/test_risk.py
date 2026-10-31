from django.test import SimpleTestCase

from reconciliation.risk import score_discrepancy


class RiskScoreTests(SimpleTestCase):
    def test_large_missing_invoice_is_high_risk(self):
        score, level = score_discrepancy("missing_in_2a", 100000)
        self.assertGreaterEqual(score, 75)
        self.assertEqual(level, "high")

    def test_date_mismatch_is_low_risk_when_tax_is_small(self):
        score, level = score_discrepancy("date_mismatch", 100)
        self.assertEqual(score, 35)
        self.assertEqual(level, "low")

    def test_low_confidence_fuzzy_candidate_gets_medium_priority(self):
        score, level = score_discrepancy("fuzzy_match", 100, confidence_score=82)
        self.assertEqual(score, 50)
        self.assertEqual(level, "medium")
