from django.urls import reverse
from rest_framework.test import APITestCase


class RegisterThrottlingTests(APITestCase):
    def test_registration_succeeds_without_redis(self):
        url = reverse("auth-register")
        data = {
            "email": "testuser@example.com",
            "password": "StrongPassword123!",
            "business_name": "Test Enterprise",
            "gstin": "27AAAAA0000A1Z5",
            "pan": "AAAAA0000A",
        }
        resp = self.client.post(url, data, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
        self.assertEqual(resp.data["business"]["name"], "Test Enterprise")
