from rest_framework import serializers

from .models import Professional, ProfessionalService, ProfessionalInsurance, ProfessionalTrade, ProfessionalInventory, ProfessionalTask, ProfessionalRating, ProfessionalPayout
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
        return Professional.objects.create(**validated_data)
    
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
        fields = '__all__'
        read_only_fields = ['professional', 'date_added']

class ProfessionalTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalTask
        fields = '__all__'
        read_only_fields = ['professional', 'date_created']

class ProfessionalRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalRating
        fields = '__all__'
        read_only_fields = ['professional', 'created_at']

class ProfessionalPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalPayout
        fields = '__all__'
        read_only_fields = ['professional', 'created_at', 'updated_at']