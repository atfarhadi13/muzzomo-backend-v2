from typing import Any

from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.db import transaction

from rest_framework import serializers

from job.models import ( 
    Job, JobRate, JobStatus, 
    JobUnitUpdateRequest, JobOffer, 
    JobAttachment, JobServiceType, 
    JobUnitUpdateRequestStatus
)

from professional.models import Professional
from service.models import ServiceType
from user.models import CustomUser

class _SafeAttrMixin:
    def _safe_get(self, obj: Any, path: str, default: Any = None) -> Any:
        cur = obj
        for part in path.split("."):
            if cur is None:
                return default
            try:
                cur = getattr(cur, part)
            except Exception:
                return default
        return cur if cur is not None else default
    
def _d(val: Any):
    try:
        if isinstance(val, Decimal):
            return str(val.quantize(Decimal("0.01")))
        return str(val)
    except Exception:
        return None

def _sdec(val: Any) -> str | None:
    try:
        if val is None:
            return None
        d = val if isinstance(val, Decimal) else Decimal(str(val))
        return str(d.quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError, TypeError):
        return None

def _safe_getattr(obj: Any, path: str, default=None):
    cur = obj
    for part in path.split("."):
        try:
            cur = getattr(cur, part)
        except Exception:
            return default
        if cur is None:
            return default
    return cur

class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "email", "first_name", "last_name", "phone_number"]

    def to_representation(self, instance):
        try:
            return super().to_representation(instance)
        except Exception:
            return {
                "id": getattr(instance, "id", None),
                "email": getattr(instance, "email", None),
                "first_name": getattr(instance, "first_name", None),
                "last_name": getattr(instance, "last_name", None),
                "phone_number": getattr(instance, "phone_number", None),
            }

class ProfessionalMiniSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = Professional
        fields = ["id", "license_number", "is_verified", "verification_status", "user"]

    def to_representation(self, instance):
        data = {
            "id": getattr(instance, "id", None),
            "license_number": getattr(instance, "license_number", None),
            "is_verified": getattr(instance, "is_verified", None),
            "verification_status": getattr(instance, "verification_status", None),
            "user": None,
        }
        try:
            if getattr(instance, "user", None) is not None:
                data["user"] = UserMiniSerializer(instance.user, context=self.context).data
        except Exception:
            data["user"] = None
        return data

class CountrySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()
    code = serializers.CharField()

    def to_representation(self, instance):
        try:
            return {
                "id": getattr(instance, "pk", None),
                "name": getattr(instance, "name", None),
                "code": getattr(instance, "code", None),
            }
        except Exception:
            return {"id": None, "name": None, "code": None}

class ProvinceSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()
    code = serializers.CharField()
    country = CountrySerializer()

    def to_representation(self, instance):
        try:
            country = getattr(instance, "country", None)
            return {
                "id": getattr(instance, "pk", None),
                "name": getattr(instance, "name", None),
                "code": getattr(instance, "code", None),
                "country": CountrySerializer(country, context=self.context).data if country else None,
            }
        except Exception:
            return {"id": None, "name": None, "code": None, "country": None}

class CitySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()
    province = ProvinceSerializer()

    def to_representation(self, instance):
        try:
            province = getattr(instance, "province", None)
            return {
                "id": getattr(instance, "pk", None),
                "name": getattr(instance, "name", None),
                "province": ProvinceSerializer(province, context=self.context).data if province else None,
            }
        except Exception:
            return {"id": None, "name": None, "province": None}

class AddressSerializer(serializers.Serializer, _SafeAttrMixin):
    street_number = serializers.CharField()
    street_name = serializers.CharField()
    unit_suite = serializers.CharField(allow_null=True)
    postal_code = serializers.CharField()
    city = serializers.CharField(source="city.name")
    province_code = serializers.CharField(source="city.province.code")
    province_name = serializers.CharField(source="city.province.name")
    country_name = serializers.CharField(source="city.province.country.name")
    country_code = serializers.CharField(source="city.province.country.code")

    def to_representation(self, instance):
        try:
            return {
                "street_number": getattr(instance, "street_number", None),
                "street_name": getattr(instance, "street_name", None),
                "unit_suite": getattr(instance, "unit_suite", None),
                "postal_code": getattr(instance, "postal_code_formatted", getattr(instance, "postal_code", None)),
                "city": self._safe_get(instance, "city.name"),
                "province_code": self._safe_get(instance, "city.province.code"),
                "province_name": self._safe_get(instance, "city.province.name"),
                "country_name": self._safe_get(instance, "city.province.country.name"),
                "country_code": self._safe_get(instance, "city.province.country.code"),
            }
        except Exception:
            return {
                "street_number": None,
                "street_name": None,
                "unit_suite": None,
                "postal_code": None,
                "city": None,
                "province_code": None,
                "province_name": None,
                "country_name": None,
                "country_code": None,
            }

class ServiceCategoryMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    title = serializers.CharField()

    def to_representation(self, instance):
        try:
            return {"id": getattr(instance, "pk", None), "title": getattr(instance, "title", None)}
        except Exception:
            return {"id": None, "title": None}

class UnitMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()
    code = serializers.CharField(allow_null=True)

    def to_representation(self, instance):
        try:
            return {
                "id": getattr(instance, "pk", None),
                "name": getattr(instance, "name", None),
                "code": getattr(instance, "code", None),
            }
        except Exception:
            return {"id": None, "name": None, "code": None}

class ServiceMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit = serializers.CharField(source="unit.code", allow_null=True)
    categories = serializers.ListField(child=serializers.CharField(), read_only=True)

    def to_representation(self, instance):
        try:
            unit_code = getattr(getattr(instance, "unit", None), "code", None)
        except Exception:
            unit_code = None

        try:
            cats = list(getattr(instance, "categories").values_list("title", flat=True))
        except Exception:
            cats = []

        try:
            price = getattr(instance, "price", None)
            price_str = _sdec(price)
        except Exception:
            price_str = None

        try:
            return {
                "id": getattr(instance, "id", None),
                "title": getattr(instance, "title", None),
                "price": price_str,
                "unit": unit_code,
                "categories": cats,
            }
        except Exception:
            return {"id": None, "title": None, "price": None, "unit": None, "categories": []}

class ServiceTypeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ["id", "title", "price"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            if data.get("price") is not None:
                data["price"] = _sdec(Decimal(str(data["price"])))
        except Exception:
            pass
        return data

class JobAttachmentSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = JobAttachment
        fields = ["id", "url", "file_name", "uploaded_at"]

    def get_file_name(self, obj):
        try:
            name = getattr(getattr(obj, "attachment", None), "name", "")
            return name.rsplit("/", 1)[-1] if name else None
        except Exception:
            return None

    def get_url(self, obj):
        try:
            att = getattr(obj, "attachment", None)
            return att.url if att else None
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

    def to_representation(self, instance):
        def g(obj, path, default=None):
            cur = obj
            for p in path.split("."):
                if cur is None:
                    return default
                try:
                    cur = getattr(cur, p)
                except Exception:
                    return default
            return cur if cur is not None else default

        try:
            return {
                "id": getattr(instance, "pk", None),
                "street_number": getattr(instance, "street_number", None),
                "street_name": getattr(instance, "street_name", None),
                "unit_suite": getattr(instance, "unit_suite", None),
                "postal_code": getattr(instance, "postal_code", None),
                "postal_code_formatted": getattr(instance, "postal_code_formatted", None),
                "city": g(instance, "city.name"),
                "province": g(instance, "city.province.name"),
                "province_code": g(instance, "city.province.code"),
                "country": g(instance, "city.province.country.name"),
                "country_code": g(instance, "city.province.country.code"),
            }
        except Exception:
            return {
                "id": None,
                "street_number": None,
                "street_name": None,
                "unit_suite": None,
                "postal_code": None,
                "postal_code_formatted": None,
                "city": None,
                "province": None,
                "province_code": None,
                "country": None,
                "country_code": None,
            }

class JobServiceTypeItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="service_type.id", read_only=True)
    title = serializers.CharField(source="service_type.title", read_only=True)
    price = serializers.DecimalField(source="service_type.price", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = JobServiceType
        fields = ["id", "title", "price"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            if data.get("price") is not None:
                data["price"] = _d(Decimal(str(data["price"])))
        except Exception:
            pass
        return data

class JobCreateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Job
        fields = [
            "id", "title", "description",
            "service", "address", "start_at",
            "quantity", "status", "total_price",
        ]
        extra_kwargs = {
            "service": {"required": True, "write_only": True},
            "address": {"required": True, "write_only": True},
            "start_at": {"required": False, "allow_null": True},
            "quantity": {"required": True},
        }

    def validate_quantity(self, value: Decimal):
        try:
            q = Decimal(value)
        except Exception:
            raise serializers.ValidationError("Invalid quantity.")
        if q <= Decimal("0"):
            raise serializers.ValidationError("Quantity must be greater than 0.")
        return q

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["total_price"] = _sdec(_safe_getattr(instance, "total_price"))
        data["quantity"] = _sdec(_safe_getattr(instance, "quantity"))
        return data

class JobRateSerializer(serializers.ModelSerializer):
    job_id = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all(), source="job")
    rated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = JobRate
        fields = ["id", "job_id", "rate", "rated_at"]

    def validate_rate(self, value):
        try:
            v = int(value)
        except Exception:
            raise serializers.ValidationError("Rate must be an integer between 1 and 5.")
        if v < 1 or v > 5:
            raise serializers.ValidationError("Rate must be between 1 and 5.")
        return v

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
        try:
            sts = [jst.service_type for jst in getattr(obj, "job_service_types").all()]
            return ServiceTypeMiniSerializer(sts, many=True).data
        except Exception:
            return []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["total_price"] = _sdec(_safe_getattr(instance, "total_price"))
        return data

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
        try:
            sts = [jst.service_type for jst in getattr(obj, "job_service_types").all()]
            return ServiceTypeMiniSerializer(sts, many=True).data
        except Exception:
            return []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["total_price"] = _sdec(_safe_getattr(instance, "total_price"))
        data["quantity"] = _sdec(_safe_getattr(instance, "quantity"))
        return data

class JobUnitUpdateRequestCreateSerializer(serializers.ModelSerializer):
    job_id = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all(), source="job")
    new_unit_qty = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = JobUnitUpdateRequest
        fields = ["id", "job_id", "new_unit_qty", "status", "created_at", "updated_at"]
        read_only_fields = ["status", "created_at", "updated_at"]

    def validate_new_unit_qty(self, value):
        try:
            v = Decimal(value)
        except Exception:
            raise serializers.ValidationError("Invalid quantity.")
        if v <= Decimal("0"):
            raise serializers.ValidationError("Must be greater than zero.")
        return v

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not hasattr(request.user, "professional_profile"):
            raise serializers.ValidationError({"detail": "Only professionals can submit requests."})

        job: Job = attrs["job"]
        professional: Professional = request.user.professional_profile

        if job.professional_id != professional.id:
            raise serializers.ValidationError({"job_id": "You are not assigned to this job."})
        if job.status in [JobStatus.COMPLETED, JobStatus.CANCELLED]:
            raise serializers.ValidationError({"job_id": "Cannot request unit update for completed or cancelled jobs."})

        if JobUnitUpdateRequest.objects.filter(
                job=job,
                professional=professional,
                status=JobUnitUpdateRequestStatus.PENDING
        ).exists():
            raise serializers.ValidationError({"detail": "There is already a pending request for this job."})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        professional = request.user.professional_profile
        with transaction.atomic():
            return JobUnitUpdateRequest.objects.create(professional=professional, **validated_data)

class JobUnitUpdateRequestListSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    professional_email = serializers.EmailField(source="professional.user.email", read_only=True)

    class Meta:
        model = JobUnitUpdateRequest
        fields = ["id", "job", "job_title", "professional", "professional_email", "new_unit_qty", "status", "created_at", "updated_at"]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["new_unit_qty"] = _sdec(_safe_getattr(instance, "new_unit_qty"))
        return data

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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["distance_km"] = _sdec(_safe_getattr(instance, "distance_km"))
        return data