from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from rest_framework import serializers

from job.models import Job, JobAttachment, JobServiceType
from service.models import Service, ServiceType
from address.models import Address, Country, Province, City

class JobServiceTypeInputSerializer(serializers.Serializer):
    service_type_id = serializers.IntegerField()

class AddressInputSerializer(serializers.Serializer):
    street_number = serializers.CharField(max_length=20)
    street_name = serializers.CharField(max_length=255)
    unit_suite = serializers.CharField(max_length=20, allow_null=True, allow_blank=True, required=False)
    city_name = serializers.CharField(max_length=100)
    province_name = serializers.CharField(max_length=100)
    country_name = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=7)

class JobCreateSerializer(serializers.ModelSerializer):
    start_date = serializers.DateField(write_only=True, required=False)
    start_time = serializers.TimeField(write_only=True, required=False)
    address = AddressInputSerializer(write_only=True)
    job_service_types = JobServiceTypeInputSerializer(many=True, write_only=True, required=False)
    job_attachments = serializers.ListField(child=serializers.FileField(), write_only=True, required=False)

    id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Job
        fields = [
            "id", "title", "description",
            "start_date", "start_time",
            "service", "address", "job_service_types", "job_attachments",
            "status", "total_price",
        ]
        extra_kwargs = {"service": {"required": True, "write_only": True}}

    def _make_start_at(self, start_date, start_time):
        if not start_date or not start_time:
            return None
        dt = datetime.combine(start_date, start_time)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    def _resolve_address(self, user, data: dict) -> Address:
        country = Country.objects.filter(name__iexact=data["country_name"]).first()
        if not country:
            raise serializers.ValidationError({"address": "Country not found. Seed countries first."})
        province = Province.objects.filter(name__iexact=data["province_name"], country=country).first()
        if not province:
            raise serializers.ValidationError({"address": "Province not found for the given country."})
        city, _ = City.objects.get_or_create(name=data["city_name"], province=province)

        addr = Address(
            user=user,
            street_number=data["street_number"],
            street_name=data["street_name"],
            unit_suite=data.get("unit_suite") or None,
            city=city,
            postal_code=data["postal_code"],
        )
        addr.full_clean()
        addr.save()
        return addr

    def validate(self, attrs):
        service: Service = attrs["service"]
        st_inputs = self.initial_data.get("job_service_types") or []
        if st_inputs:
            st_ids = [x.get("service_type_id") for x in st_inputs]
            svc_types = ServiceType.objects.filter(id__in=st_ids).select_related("service")
            if len(svc_types) != len(st_ids):
                raise serializers.ValidationError({"job_service_types": "One or more service_type_id are invalid."})
            for st in svc_types:
                if st.service_id != service.id:
                    raise serializers.ValidationError({"job_service_types": "All service types must belong to the selected service."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        start_date = validated_data.pop("start_date", None)
        start_time = validated_data.pop("start_time", None)
        address_payload = self.initial_data.get("address") or {}
        st_inputs = self.initial_data.get("job_service_types") or []
        files = self.initial_data.get("job_attachments")

        start_at = self._make_start_at(start_date, start_time)
        address = self._resolve_address(user, address_payload)

        job = Job.objects.create(
            user=user,
            service=validated_data["service"],
            address=address,
            title=validated_data["title"],
            description=validated_data.get("description"),
            start_at=start_at,
            quantity=Decimal("1.00"),
        )

        if st_inputs:
            st_ids = [x["service_type_id"] for x in st_inputs]
            JobServiceType.objects.bulk_create(
                [JobServiceType(job=job, service_type_id=st_id) for st_id in st_ids]
            )

        if files and isinstance(files, list):
            for f in files:
                JobAttachment.objects.create(job=job, attachment=f)

        return job
