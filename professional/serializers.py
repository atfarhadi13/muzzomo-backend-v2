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