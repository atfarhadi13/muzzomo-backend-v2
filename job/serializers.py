from decimal import Decimal

from django.db.models import Q
from django.db import transaction

from rest_framework import serializers
from rest_framework.serializers import ( ModelSerializer, IntegerField, CharField, 
                                        DecimalField, DateTimeField, BooleanField )

from job.models import Job, JobRate, JobStatus, JobUnitUpdateRequest, JobOffer, JobAttachment, JobServiceType

from professional.models import Professional
from service.models import ServiceType

class UserMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone_number = serializers.CharField(allow_null=True)


class ProfessionalMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    is_verified = serializers.BooleanField()
    verification_status = serializers.CharField()
    license_number = serializers.CharField()
    user = UserMiniSerializer(source="user")


class CountrySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()
    code = serializers.CharField()


class ProvinceSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()
    code = serializers.CharField()
    country = CountrySerializer()


class CitySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()
    province = ProvinceSerializer()


class AddressSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    street_number = serializers.CharField()
    street_name = serializers.CharField()
    unit_suite = serializers.CharField(allow_null=True)
    postal_code = serializers.CharField()
    postal_code_formatted = serializers.CharField()
    city = CitySerializer()


class ServiceCategoryMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    title = serializers.CharField()


class UnitMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()
    code = serializers.CharField(allow_null=True)


class ServiceMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    title = serializers.CharField()
    is_trade_required = serializers.BooleanField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit = UnitMiniSerializer(allow_null=True)
    categories = ServiceCategoryMiniSerializer(many=True)

class ServiceTypeMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    title = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)

class JobAttachmentSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = JobAttachment
        fields = ["id", "url", "file_name", "uploaded_at"]

    def get_file_name(self, obj):
        return obj.attachment.name.rsplit("/", 1)[-1] if obj.attachment and obj.attachment.name else None
    
    def get_url(self, obj):
        try:
            return obj.attachment.url if obj.attachment else None
        except Exception:
            return None

class JobAddressSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    street_number = serializers.CharField()
    street_name = serializers.CharField()
    unit_suite = serializers.CharField(allow_null=True)
    postal_code = serializers.CharField()
    postal_code_formatted = serializers.CharField()
    city = serializers.CharField(source="city.name")
    province = serializers.CharField(source="city.province.name")
    province_code = serializers.CharField(source="city.province.code")
    country = serializers.CharField(source="city.province.country.name")
    country_code = serializers.CharField(source="city.province.country.code")

class JobServiceTypeItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="service_type.id", read_only=True)
    title = serializers.CharField(source="service_type.title", read_only=True)
    price = serializers.DecimalField(source="service_type.price", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = JobServiceType
        fields = ["id", "title", "price"]

class JobCreateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Job
        fields = [
            "id", "title", "description",
            "service", "address", "start_at",
            "status", "total_price",
        ]
        extra_kwargs = {
            "service": {"required": True, "write_only": True},
            "address": {"required": True, "write_only": True},
            "start_at": {"required": False, "allow_null": True},
        }

class JobRateSerializer(serializers.ModelSerializer):
    job_id = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all(), source="job")
    rated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = JobRate
        fields = ["id", "job_id", "rate", "rated_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        job = attrs.get("job") or getattr(self.instance, "job", None)
        if job is None:
            raise serializers.ValidationError({"job_id": "Job is required."})
        if request is None or job.user_id != request.user.id:
            raise serializers.ValidationError({"job_id": "You can only rate your own job."})
        if self.instance is None and JobRate.objects.filter(job=job).exists():
            raise serializers.ValidationError({"job_id": "This job is already rated."})
        if job.status != JobStatus.COMPLETED or not job.is_paid:
            raise serializers.ValidationError({"job_id": "You can rate only completed and paid jobs."})
        return attrs
    
class JobListSerializer(serializers.ModelSerializer):
    owner = UserMiniSerializer(source="user", read_only=True)
    professional = ProfessionalMiniSerializer(read_only=True)
    address = AddressSerializer(read_only=True)
    service = ServiceMiniSerializer(read_only=True)
    service_types = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id", "title", "description",
            "status", "is_paid", "total_price", "start_at", "created_at",
            "owner", "professional", "address", "service", "service_types",
        ]

    def get_service_types(self, obj):
        sts = ServiceType.objects.filter(job_service_types__job=obj).only("id", "title", "price")
        return ServiceTypeMiniSerializer(sts, many=True).data


class JobDetailSerializer(serializers.ModelSerializer):
    owner = UserMiniSerializer(source="user", read_only=True)
    professional = ProfessionalMiniSerializer(read_only=True)
    address = AddressSerializer(read_only=True)
    service = ServiceMiniSerializer(read_only=True)
    service_types = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id", "title", "description",
            "status", "is_paid", "total_price", "quantity",
            "submit_date", "start_at", "completed_date", "created_at", "updated_at",
            "owner", "professional", "address", "service", "service_types",
        ]

    def get_service_types(self, obj):
        sts = ServiceType.objects.filter(job_service_types__job=obj).only("id", "title", "price")
        return ServiceTypeMiniSerializer(sts, many=True).data

class JobUnitUpdateRequestCreateSerializer(serializers.ModelSerializer):
    job_id = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all(), source="job")
    new_unit_qty = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = JobUnitUpdateRequest
        fields = ["id", "job_id", "new_unit_qty", "status", "created_at", "updated_at"]
        read_only_fields = ["status", "created_at", "updated_at"]

    def validate(self, attrs):
        request = self.context["request"]
        job: Job = attrs["job"]
        if not hasattr(request.user, "professional_profile"):
            raise serializers.ValidationError({"detail": "Only professionals can submit requests."})
        professional: Professional = request.user.professional_profile
        if job.professional_id != professional.id:
            raise serializers.ValidationError({"job_id": "You are not assigned to this job."})
        if job.status in [JobStatus.COMPLETED, JobStatus.CANCELLED]:
            raise serializers.ValidationError({"job_id": "Cannot request unit update for completed or cancelled jobs."})
        qty: Decimal = attrs["new_unit_qty"]
        if qty <= Decimal("0"):
            raise serializers.ValidationError({"new_unit_qty": "Must be greater than zero."})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        professional = request.user.professional_profile
        with transaction.atomic():
            obj = JobUnitUpdateRequest.objects.create(professional=professional, **validated_data)
        return obj
    
class JobUnitUpdateRequestListSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    professional_email = serializers.EmailField(source="professional.user.email", read_only=True)

    class Meta:
        model = JobUnitUpdateRequest
        fields = ["id", "job", "job_title", "professional", "professional_email", "new_unit_qty", "status", "created_at", "updated_at"]
        read_only_fields = fields
    
class JobOfferSerializer(serializers.ModelSerializer):
    job_id = serializers.IntegerField(source="job.id", read_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)
    service_id = serializers.IntegerField(source="job.service.id", read_only=True)
    service_title = serializers.CharField(source="job.service.title", read_only=True)
    city = serializers.CharField(source="job.address.city.name", read_only=True)
    province = serializers.CharField(source="job.address.city.province.code", read_only=True)
    start_at = serializers.DateTimeField(source="job.start_at", read_only=True)

    class Meta:
        model = JobOffer
        fields = [
            "id",
            "status",
            "distance_km",
            "created_at",
            "updated_at",
            "accepted_at",
            "job_id",
            "job_title",
            "service_id",
            "service_title",
            "city",
            "province",
            "start_at",
        ]