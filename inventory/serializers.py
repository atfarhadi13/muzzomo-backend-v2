from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from .models import InventoryItem, ItemLocation, InventoryLog
from project_management.models import Task


class InventoryItemSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    available_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id", "professional", "name", "item_type", "unit",
            "total_quantity", "in_use_quantity", "available_quantity",
            "reorder_point", "notes", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "professional", "available_quantity", "created_at", "updated_at", "in_use_quantity", "total_quantity"]

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["professional"] = request.user.professional_profile
        return super().create(validated_data)


class ItemLocationSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    item = serializers.PrimaryKeyRelatedField(queryset=InventoryItem.objects.all())

    class Meta:
        model = ItemLocation
        fields = ["id", "professional", "item", "location_name", "on_hand", "in_use", "updated_at"]
        read_only_fields = ["id", "professional", "on_hand", "in_use", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["professional"] = request.user.professional_profile
        return super().create(validated_data)


class InventoryLogSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = InventoryLog
        fields = ["id", "professional", "item", "action", "quantity", "unit", "task", "note", "created_at"]
        read_only_fields = ["id", "professional", "created_at"]


class QuantityActionSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all(), required=False, allow_null=True)

    def validate_quantity(self, v):
        if v <= Decimal("0"):
            raise serializers.ValidationError("Quantity must be positive.")
        return v


class AdjustActionSerializer(serializers.Serializer):
    quantity_delta = serializers.DecimalField(max_digits=12, decimal_places=3)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all(), required=False, allow_null=True)


class LocationQuantityActionSerializer(QuantityActionSerializer):
    location_id = serializers.PrimaryKeyRelatedField(queryset=ItemLocation.objects.all(), source="location")


class TransferActionSerializer(serializers.Serializer):
    source_location_id = serializers.PrimaryKeyRelatedField(queryset=ItemLocation.objects.all(), source="source")
    dest_location_id = serializers.PrimaryKeyRelatedField(queryset=ItemLocation.objects.all(), source="dest")
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_quantity(self, v):
        if v <= Decimal("0"):
            raise serializers.ValidationError("Quantity must be positive.")
        return v
