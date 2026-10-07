from .serializers import RegisterSerializer
from rest_framework import generics, permissions

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]