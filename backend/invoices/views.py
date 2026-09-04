import io
import uuid

import msoffcrypto
from django.core.cache import cache
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from .models import InvoiceBatch
from .serializers import InvoiceBatchSerializer
from .tasks import UPLOAD_CACHE_PREFIX, parse_and_store_batch

UPLOAD_CACHE_TTL = 15 * 60  # keep raw bytes around for 15 min while a password round-trip happens


def _key(token: str, name: str) -> str:
    return f"{UPLOAD_CACHE_PREFIX}:{token}:{name}"


def _is_encrypted_xlsx(file_bytes: bytes) -> bool:
    try:
        return msoffcrypto.OfficeFile(io.BytesIO(file_bytes)).is_encrypted()
    except Exception:
        return False


class BaseUploadView(APIView):
    source = None  # set by subclass: "books" or "2a"

    def post(self, request):
        business = request.user.business
        upload_token = request.data.get("upload_token")
        password = request.data.get("password") or None
        period = request.data.get("period", "")

        if upload_token:
            filename = cache.get(_key(upload_token, "filename"))
            if filename is None:
                return Response(
                    {"detail": "This upload has expired. Please re-upload the file."}, status=400
                )
            attempts = cache.get(_key(upload_token, "attempts"), 0)
            if attempts >= settings.UPLOAD_PASSWORD_MAX_ATTEMPTS:
                return Response(
                    {"detail": "Too many incorrect password attempts. Please re-upload the file."},
                    status=429,
                )
        else:
            f = request.FILES.get("file")
            if not f:
                return Response({"detail": "No file provided."}, status=400)
            file_bytes = f.read()
            filename = f.name
            upload_token = uuid.uuid4().hex
            cache.set(_key(upload_token, "bytes"), file_bytes, UPLOAD_CACHE_TTL)
            cache.set(_key(upload_token, "filename"), filename, UPLOAD_CACHE_TTL)
            cache.set(_key(upload_token, "attempts"), 0, UPLOAD_CACHE_TTL)

        if filename.lower().endswith((".xlsx", ".xls")) and not password:
            file_bytes = cache.get(_key(upload_token, "bytes"))
            if file_bytes is not None and _is_encrypted_xlsx(file_bytes):
                return Response(
                    {
                        "needs_password": True,
                        "upload_token": upload_token,
                        "filename": filename,
                    },
                    status=422,
                )

        if password:
            # Short-lived: only long enough for the Celery task to pick it up.
            cache.set(_key(upload_token, "pw"), password, 60)

        batch = InvoiceBatch.objects.create(
            business=business,
            source=self.source,
            original_filename=filename,
            period=period,
            status="processing",
        )
        parse_and_store_batch.delay(batch.id, upload_token, self.source)
        return Response(
            {"batch_id": batch.id, "status": "processing", "upload_token": upload_token}, status=202
        )


class UploadPurchaseRegisterView(BaseUploadView):
    source = "books"


class UploadGSTR2AView(BaseUploadView):
    source = "2a"


class BatchStatusView(generics.RetrieveAPIView):
    serializer_class = InvoiceBatchSerializer

    def get_queryset(self):
        return InvoiceBatch.objects.filter(business=self.request.user.business)
