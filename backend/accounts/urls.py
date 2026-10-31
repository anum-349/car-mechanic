from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import LoginTokenSerializer
from .views import MeView, MechanicProfileViewSet, RegisterView, home_view


class LoginTokenView(TokenObtainPairView):
    serializer_class = LoginTokenSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(max_length=4096, write_only=True)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=LogoutSerializer, responses={205: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
        except (TokenError, TypeError, ValueError):
            return Response({"detail": "Invalid refresh token."},
                            status=status.HTTP_400_BAD_REQUEST)
        if str(token.get("user_id")) != str(request.user.pk):
            return Response({"detail": "Invalid refresh token."},
                            status=status.HTTP_400_BAD_REQUEST)
        token.blacklist()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


router = SimpleRouter()
router.register("mechanics", MechanicProfileViewSet, basename="mechanic")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/token/", LoginTokenView.as_view(), name="token"),
    path("auth/token/refresh/", ThrottledTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
] + router.urls
