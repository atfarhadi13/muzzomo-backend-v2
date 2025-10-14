from rest_framework import serializers
from .models import (
    Professional,
    ProfessionalService,
    ProfessionalInsurance,
    ProfessionalTrade,
    ProfessionalRating,
    ProfessionalPayout,
    BankInfo,
)
from service.models import Service


class ProfessionalSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    registration_completion = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Professional
        fields = [
            "id",
            "user",
            "license_number",
            "government_issued_id",
            "certification",
            "is_verified",
            "verification_status",
            "registration_completion",
        ]
        read_only_fields = ["user", "is_verified", "verification_status", "registration_completion"]

    def get_registration_completion(self, obj):
        return obj.registration_completion_percent()

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        validated_data["user"] = request.user
        return Professional.objects.create(**validated_data)


class ProfessionalServiceSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())

    class Meta:
        model = ProfessionalService
        fields = ["id", "professional", "service"]

    def update(self, instance, validated_data):
        validated_data.pop("professional", None)
        return super().update(instance, validated_data)


class ProfessionalInsuranceSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProfessionalInsurance
        fields = [
            "id",
            "professional",
            "insurance_provider_name",
            "insurance_policy_number",
            "insurance_file",
            "insurance_expiry_date",
        ]

    def update(self, instance, validated_data):
        validated_data.pop("professional", None)
        return super().update(instance, validated_data)


class ProfessionalTradeSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProfessionalTrade
        fields = [
            "id",
            "professional",
            "trade_license_number",
            "trade_license_file",
            "trade_license_expiry_date",
        ]

    def update(self, instance, validated_data):
        validated_data.pop("professional", None)
        return super().update(instance, validated_data)


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
        fields = "__all__"
        read_only_fields = ["professional", "created_at", "updated_at"]


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