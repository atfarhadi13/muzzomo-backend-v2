from datetime import datetime
from decimal import Decimal

from rest_framework import serializers

from .models import ( 
    Professional, 
    ProfessionalService, 
    ProfessionalInsurance,
    ProfessionalTrade, 
    ProfessionalInventory, 
    ProfessionalTask, 
    ProfessionalRating, 
    ProfessionalPayout,
    BankInfo
)
from service.models import Service

class ProfessionalSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Professional
        fields = [
            "id", "user",
            "license_number", "government_issued_id", "certification",
            "is_verified", "verification_status",
        ]
        read_only_fields = ["user", "is_verified", "verification_status"]

    def create(self, validated_data):
        try:
            return Professional.objects.create(**validated_data)
        except Exception as e:
            raise serializers.ValidationError(str(e))
    
class ProfessionalServiceSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())

    class Meta:
        model = ProfessionalService
        fields = ["id", "professional", "service"]
        
class ProfessionalInsuranceSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProfessionalInsurance
        fields = [
            "id", "professional",
            "insurance_provider_name",
            "insurance_policy_number",
            "insurance_file",
            "insurance_expiry_date",
        ]
        
class ProfessionalTradeSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProfessionalTrade
        fields = [
            "id", "professional",
            "trade_license_number",
            "trade_license_file",
            "trade_license_expiry_date",
        ]

class ProfessionalInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalInventory
        fields = "__all__"
        read_only_fields = ["professional", "date_added"]

    def validate_item_name(self, v):
        v = (v or "").strip()
        if not v:
            raise serializers.ValidationError("Item name is required.")
        return v

    def validate_quantity(self, v):
        if v is None:
            return Decimal("0")
        if v < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return v

    def validate_unit(self, v):
        return (v or "").strip() or None

class ProfessionalTaskSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.SerializerMethodField(read_only=True)
    duration_hours = serializers.SerializerMethodField(read_only=True)
    estimated_amount = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProfessionalTask
        fields = "__all__"
        read_only_fields = ["professional", "date_created", "duration_minutes", "duration_hours", "estimated_amount"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_date and start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        pph = attrs.get("price_per_hour", getattr(self.instance, "price_per_hour", None))
        if pph is not None and pph < 0:
            raise serializers.ValidationError({"price_per_hour": "Must be >= 0."})
        return attrs

    def get_duration_minutes(self, obj):
        try:
            if not obj.end_time:
                return None
            start_dt = datetime.combine(obj.start_date, obj.start_time)
            end_dt = datetime.combine(obj.start_date, obj.end_time)
            delta = end_dt - start_dt
            minutes = int(delta.total_seconds() // 60)
            return max(minutes, 0)
        except Exception:
            return None

    def get_duration_hours(self, obj):
        mins = self.get_duration_minutes(obj)
        return round(mins / 60.0, 2) if mins is not None else None

    def get_estimated_amount(self, obj):
        hrs = self.get_duration_hours(obj)
        if hrs is None:
            return None
        try:
            return str((Decimal(str(hrs)) * obj.price_per_hour).quantize(Decimal("0.01")))
        except Exception:
            return None

class ProfessionalRatingCreateUpdateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    review = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    def validate(self, attrs):
        request = self.context["request"]
        professional = self.context["professional"]
        if professional.user_id == request.user.id:
            raise serializers.ValidationError({"detail": "You cannot rate yourself."})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        professional = self.context["professional"]
        obj, _ = ProfessionalRating.objects.update_or_create(
            professional=professional,
            user=request.user,
            defaults={
                "rating": validated_data["rating"],
                "review": validated_data.get("review", ""),
            },
        )
        return obj

class ProfessionalRatingSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = ProfessionalRating
        fields = ["id", "professional", "user", "rating", "review", "created_at"]
        read_only_fields = ["professional", "user", "created_at"]

class ProfessionalPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalPayout
        fields = '__all__'
        read_only_fields = ['professional', 'created_at', 'updated_at']

class BankInfoSerializer(serializers.ModelSerializer):
    account_last4 = serializers.SerializerMethodField(read_only=True)
    masked_account_number = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BankInfo
        fields = [
            "id",
            "professional",
            "institution_name",
            "institution_number",
            "transit_number",
            "account_number",
            "account_holder_name",
            "account_last4",
            "masked_account_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["professional", "account_last4", "masked_account_number", "created_at", "updated_at"]

    def get_account_last4(self, obj):
        return obj.account_last4

    def get_masked_account_number(self, obj):
        return obj.masked_account_number