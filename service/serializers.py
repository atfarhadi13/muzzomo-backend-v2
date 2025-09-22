from django.db import IntegrityError

from rest_framework import serializers

from .models import (
    Service, ServicePhoto, ServiceType, ServiceTypePhoto,
    Unit, ServiceCategory, Rating
)

def abs_url(request, field):
    return request.build_absolute_uri(field.url) if request and getattr(field, "url", None) else None

class ServiceCategorySerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    services_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ServiceCategory
        fields = ["id", "title", "description", "photo", "photo_url", "services_count", "created_at"]

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo and hasattr(obj.photo, "url"):
            return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url
        return None


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "code"]


class UnitMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "code"]

class ServicePhotoSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = ServicePhoto
        fields = ["id", "caption", "uploaded_at", "photo", "photo_url"]

    def get_photo_url(self, obj):
        return abs_url(self.context.get("request"), obj.photo)


class ServiceTypePhotoSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = ServiceTypePhoto
        fields = ["id", "caption", "uploaded_at", "photo", "photo_url"]

    def get_photo_url(self, obj):
        return abs_url(self.context.get("request"), obj.photo)


class ServiceTypeSerializer(serializers.ModelSerializer):
    photos = ServiceTypePhotoSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceType
        fields = ["id", "title", "description", "price", "created_at", "photos"]

class ServiceMiniSerializer(serializers.ModelSerializer):
    unit = UnitMiniSerializer(read_only=True)

    class Meta:
        model = Service
        fields = ["id", "title", "price", "unit"]


class ServiceTypeWithServiceSerializer(serializers.ModelSerializer):
    service = ServiceMiniSerializer(read_only=True)

    class Meta:
        model = ServiceType
        fields = ["id", "title", "description", "price", "created_at", "service"]


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ["id", "title"]


class ServiceSerializer(serializers.ModelSerializer):
    unit = UnitSerializer(read_only=True)
    photos = ServicePhotoSerializer(many=True, read_only=True)
    types = ServiceTypeSerializer(many=True, read_only=True)
    categories = CategoryMiniSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            "id", "title", "description", "is_trade_required",
            "price", "unit", "categories", "photos", "types",
            "average_rating", "created_at"
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        include = False
        ctx = self.context or {}
        if ctx.get("include_types") is True:
            include = True
        else:
            req = ctx.get("request")
            if req:
                val = req.query_params.get("include_types")
                if val and val.lower() in {"1", "true", "yes"}:
                    include = True
        if not include:
            self.fields.pop("types", None)

    def get_average_rating(self, obj):
        avg = getattr(obj, "avg_rating", None)
        if avg is None:
            avg = obj.average_rating
        return round(float(avg), 2) if avg is not None else None


class RatingSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    service_title = serializers.CharField(source="service.title", read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "service", "service_title", "rating", "review", "created_at", "user_email"]
        read_only_fields = ["id", "created_at", "user_email", "service_title"]

    def validate_rating(self, value):
        if not (1 <= int(value) <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if self.instance:
            if "service" in attrs and attrs["service"].pk != self.instance.service_id:
                raise serializers.ValidationError({"service": "You cannot change the service of an existing rating."})
            return attrs

        service = attrs.get("service")
        if not service:
            raise serializers.ValidationError({"service": "This field is required."})
        if Rating.objects.filter(service=service, user=user).exists():
            raise serializers.ValidationError("You have already rated this service.")
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        try:
            return Rating.objects.create(user=user, **validated_data)
        except IntegrityError:
            raise serializers.ValidationError("You have already rated this service.")

    def update(self, instance, validated_data):
        instance.rating = validated_data.get("rating", instance.rating)
        instance.review = validated_data.get("review", instance.review)
        instance.save(update_fields=["rating", "review"])
        return instance