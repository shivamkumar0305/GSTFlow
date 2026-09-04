from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Business, User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    business_name = serializers.CharField(max_length=255)
    gstin = serializers.CharField(max_length=15)
    pan = serializers.CharField(max_length=10)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_gstin(self, value):
        value = value.upper().strip()
        if len(value) != 15:
            raise serializers.ValidationError("GSTIN must be 15 characters.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        business = Business.objects.create(
            user=user,
            name=validated_data["business_name"],
            gstin=validated_data["gstin"],
            pan=validated_data["pan"].upper().strip(),
        )
        return business


class BusinessSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Business
        fields = ["id", "name", "gstin", "pan", "email", "created_at"]
