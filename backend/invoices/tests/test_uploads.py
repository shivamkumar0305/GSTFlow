from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Business, User
from invoices.models import InvoiceBatch
from invoices.tasks import parse_and_store_batch


def _run_task_synchronously(*args, **kwargs):
    """Runs the Celery task's body inline instead of enqueueing it, so tests
    don't depend on a running worker or on Celery's eager-mode plumbing."""
    return parse_and_store_batch.run(*args, **kwargs)


@override_settings(UPLOAD_PASSWORD_MAX_ATTEMPTS=2)
@patch("invoices.views.parse_and_store_batch.delay", side_effect=_run_task_synchronously)
class PasswordProtectedUploadTests(APITestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username="a@b.com", email="a@b.com", password="pw12345!")
        self.business = Business.objects.create(user=user, name="Biz", gstin="27AAAAA0000A1Z5", pan="AAAAA0000A")
        self.client.force_authenticate(user=user)

    @patch("invoices.views._is_encrypted_xlsx", return_value=True)
    def test_encrypted_file_without_password_prompts_for_one(self, _mock, _mock_delay):
        f = SimpleUploadedFile("statement.xlsx", b"fake-encrypted-bytes")
        resp = self.client.post(reverse("upload-gstr2a"), {"file": f})
        self.assertEqual(resp.status_code, 422)
        self.assertTrue(resp.data["needs_password"])
        self.assertIn("upload_token", resp.data)

    @patch("invoices.parsing.parse_tabular_file")
    @patch("invoices.views._is_encrypted_xlsx", return_value=True)
    def test_wrong_password_is_rate_limited(self, _mock_enc, mock_parse, _mock_delay):
        from invoices import parsing

        mock_parse.side_effect = parsing.FileNeedsPassword("bad password")

        f = SimpleUploadedFile("statement.xlsx", b"fake-encrypted-bytes")
        resp = self.client.post(reverse("upload-gstr2a"), {"file": f})
        token = resp.data["upload_token"]

        # First wrong-password attempt (within UPLOAD_PASSWORD_MAX_ATTEMPTS=2)
        resp = self.client.post(reverse("upload-gstr2a"), {"upload_token": token, "password": "wrong1"})
        self.assertEqual(resp.status_code, 202)
        batch_id = resp.data["batch_id"]
        batch = InvoiceBatch.objects.get(id=batch_id)
        self.assertEqual(batch.status, "failed")

        # Second wrong-password attempt — exhausts the limit
        resp = self.client.post(reverse("upload-gstr2a"), {"upload_token": token, "password": "wrong2"})
        self.assertEqual(resp.status_code, 202)

        # Third attempt should now be refused before even trying
        resp = self.client.post(reverse("upload-gstr2a"), {"upload_token": token, "password": "wrong3"})
        self.assertEqual(resp.status_code, 429)

    def test_password_never_persisted_after_successful_parse(self, _mock_delay):
        with patch("invoices.parsing.parse_tabular_file", return_value=[]):
            f = SimpleUploadedFile("statement.xlsx", b"not-actually-encrypted")
            with patch("invoices.views._is_encrypted_xlsx", return_value=False):
                resp = self.client.post(
                    reverse("upload-gstr2a"), {"file": f, "password": "correct-horse"}
                )
        self.assertEqual(resp.status_code, 202)
        token = resp.data["upload_token"]
        self.assertIsNone(cache.get(f"upload:{token}:pw"))
