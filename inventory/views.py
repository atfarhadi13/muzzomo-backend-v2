# inventory/views.py
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from .models import InventoryItem, ItemLocation, InventoryLog
from .serializers import (
    InventoryItemSerializer, ItemLocationSerializer, InventoryLogSerializer,
    QuantityActionSerializer, AdjustActionSerializer, LocationQuantityActionSerializer, TransferActionSerializer
)


class ScopedQuerysetMixin:
    def scope(self, qs, field="professional"):
        prof = getattr(self.request.user, "professional_profile", None)
        if prof:
            return qs.filter(**{field: prof})
        return qs.none()


class InventoryItemViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InventoryItemSerializer

    def get_queryset(self):
        qs = self.scope(InventoryItem.objects.all())
        q = self.request.query_params.get("q")
        t = self.request.query_params.get("type")
        if q:
            qs = qs.filter(name__icontains=q)
        if t in dict(InventoryItem.ItemType.choices).keys():
            qs = qs.filter(item_type=t)
        return qs.order_by("name")

    def perform_create(self, serializer):
        serializer.save(professional=self.request.user.professional_profile)

    @action(detail=True, methods=["post"], url_path="add-stock")
    @transaction.atomic
    def add_stock(self, request, pk=None):
        item = self.get_object()
        ser = QuantityActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item.add_stock(ser.validated_data["quantity"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="consume")
    @transaction.atomic
    def consume(self, request, pk=None):
        item = self.get_object()
        ser = QuantityActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item.consume(ser.validated_data["quantity"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="checkout")
    @transaction.atomic
    def checkout(self, request, pk=None):
        item = self.get_object()
        ser = QuantityActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item.checkout(ser.validated_data["quantity"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="checkin")
    @transaction.atomic
    def checkin(self, request, pk=None):
        item = self.get_object()
        ser = QuantityActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item.checkin(ser.validated_data["quantity"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="adjust")
    @transaction.atomic
    def adjust(self, request, pk=None):
        item = self.get_object()
        ser = AdjustActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item.adjust(ser.validated_data["quantity_delta"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="add-stock-at")
    @transaction.atomic
    def add_stock_at(self, request, pk=None):
        item = self.get_object()
        ser = LocationQuantityActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        location = ser.validated_data["location"]
        if location.item_id != item.id:
            return Response({"detail": "Location does not belong to this item."}, status=400)
        item.add_stock_at(location, ser.validated_data["quantity"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="consume-at")
    @transaction.atomic
    def consume_at(self, request, pk=None):
        item = self.get_object()
        ser = LocationQuantityActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        location = ser.validated_data["location"]
        if location.item_id != item.id:
            return Response({"detail": "Location does not belong to this item."}, status=400)
        item.consume_at(location, ser.validated_data["quantity"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="checkout-at")
    @transaction.atomic
    def checkout_at(self, request, pk=None):
        item = self.get_object()
        ser = LocationQuantityActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        location = ser.validated_data["location"]
        if location.item_id != item.id:
            return Response({"detail": "Location does not belong to this item."}, status=400)
        item.checkout_at(location, ser.validated_data["quantity"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="checkin-at")
    @transaction.atomic
    def checkin_at(self, request, pk=None):
        item = self.get_object()
        ser = LocationQuantityActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        location = ser.validated_data["location"]
        if location.item_id != item.id:
            return Response({"detail": "Location does not belong to this item."}, status=400)
        item.checkin_at(location, ser.validated_data["quantity"], ser.validated_data.get("note") or "", ser.validated_data.get("task"))
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="transfer")
    @transaction.atomic
    def transfer(self, request, pk=None):
        item = self.get_object()
        ser = TransferActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        source = ser.validated_data["source"]
        dest = ser.validated_data["dest"]
        if source.item_id != item.id or dest.item_id != item.id:
            return Response({"detail": "Both locations must belong to this item."}, status=400)
        item.transfer(source, dest, ser.validated_data["quantity"], ser.validated_data.get("note") or "")
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["get"], url_path="locations")
    def locations(self, request, pk=None):
        item = self.get_object()
        qs = item.locations.all().order_by("location_name")
        return Response(ItemLocationSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="logs")
    def logs(self, request, pk=None):
        item = self.get_object()
        qs = InventoryLog.objects.filter(item=item).order_by("-created_at")
        return Response(InventoryLogSerializer(qs, many=True).data)


class ItemLocationViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ItemLocationSerializer

    def get_queryset(self):
        qs = self.scope(ItemLocation.objects.select_related("item"))
        item_id = self.request.query_params.get("item")
        if item_id:
            qs = qs.filter(item_id=item_id)
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(location_name__icontains=q)
        return qs.order_by("location_name")

    def perform_create(self, serializer):
        serializer.save(professional=self.request.user.professional_profile)


class InventoryLogViewSet(ScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InventoryLogSerializer

    def get_queryset(self):
        qs = self.scope(InventoryLog.objects.select_related("item"))
        item_id = self.request.query_params.get("item")
        task_id = self.request.query_params.get("task")
        if item_id:
            qs = qs.filter(item_id=item_id)
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs.order_by("-created_at")
