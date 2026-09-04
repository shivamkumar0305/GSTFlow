from django.urls import path

from .views import BatchStatusView, UploadGSTR2AView, UploadPurchaseRegisterView

urlpatterns = [
    path("purchase-register/", UploadPurchaseRegisterView.as_view(), name="upload-purchase-register"),
    path("gstr2a/", UploadGSTR2AView.as_view(), name="upload-gstr2a"),
    path("<int:pk>/", BatchStatusView.as_view(), name="upload-status"),
]
