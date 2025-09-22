from rest_framework import generics, permissions
from .models import Address
from .serializers import AddressCreateSerializer, AddressUpdateSerializer
from .permissions import IsOwner

class AddressCreateView(generics.CreateAPIView):
    serializer_class = AddressCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)
