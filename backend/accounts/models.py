from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


class Business(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="business")
    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15)
    pan = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.gstin})"
