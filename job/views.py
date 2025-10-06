from rest_framework import permissions, generics

from .serializers import JobCreateSerializer

class JobCreateView(generics.CreateAPIView):
    serializer_class = JobCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
