from django.urls import path
from .views import AddressCreateView, AddressDetailView, AddressListForUserView

urlpatterns = [
    path("addresses/", AddressCreateView.as_view(), name="address-create"),
    path("addresses/<int:pk>/", AddressDetailView.as_view(), name="address-detail"),

    path("addresses-list/", AddressListForUserView.as_view(), name="address-list-for-user"),
]