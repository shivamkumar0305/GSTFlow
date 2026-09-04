from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Business
from .serializers import BusinessSerializer, RegisterSerializer


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        business = serializer.save()
        refresh = RefreshToken.for_user(business.user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "business": BusinessSerializer(business).data,
            },
            status=201,
        )


class MeView(generics.RetrieveAPIView):
    serializer_class = BusinessSerializer

    def get_object(self):
        return self.request.user.business
