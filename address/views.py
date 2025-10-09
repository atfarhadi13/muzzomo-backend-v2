from rest_framework import generics, permissions
from .models import Address
from .serializers import AddressCreateSerializer, AddressUpdateSerializer, AddressReadSerializer
from .permissions import IsOwner

class AddressCreateView(generics.CreateAPIView):
    serializer_class = AddressCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        try:
            return Address.objects.filter(user=self.request.user)
        except Exception as e:
            return Address.objects.none()

class AddressListForUserView(generics.ListAPIView):
    serializer_class = AddressReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        try:
            return (
                Address.objects.filter(user=self.request.user)
                .select_related(
                    "city",
                    "city__province",
                    "city__province__country",
                )
                .order_by("-date_created")
            )
        except Exception as e:
            return Address.objects.none()