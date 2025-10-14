from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InventoryItemViewSet, ItemLocationViewSet, InventoryLogViewSet

router = DefaultRouter()
router.register(r"items", InventoryItemViewSet, basename="inventory-item")
router.register(r"item-locations", ItemLocationViewSet, basename="item-location")
router.register(r"logs", InventoryLogViewSet, basename="inventory-log")

urlpatterns = [
    path("", include(router.urls)),
]
