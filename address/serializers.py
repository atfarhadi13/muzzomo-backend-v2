# apps/address/serializers.py
import re
from django.db import transaction, IntegrityError
from rest_framework import serializers
from .models import Country, Province, City, Address, PROVINCE_CHOICES

PROV_NAME_TO_CODE = {name.lower(): code for code, name in PROVINCE_CHOICES}
PROV_CODE_TO_NAME = {code: name for code, name in PROVINCE_CHOICES}

def _derive_country_code_from_name(name: str) -> str:
    letters = re.findall(r"[A-Za-z]", name or "")
    if not letters: return "XX"
    parts = re.findall(r"[A-Za-z]+", name)
    return (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else "".join(letters[:2]).upper()

def _resolve_geo(*, country_name=None, country_code=None, province_name=None, province_code=None, city_name=None):
    country = None
    if country_code: country = Country.objects.filter(code__iexact=country_code).first()
    if not country and country_name: country = Country.objects.filter(name__iexact=country_name).first()
    if not country:
        if not country_code and country_name: country_code = _derive_country_code_from_name(country_name)
        if not country_name and country_code: country_name = country_code
        country = Country(name=country_name, code=(country_code or "").upper())
        country.full_clean()
        try: country.save()
        except IntegrityError:
            country = Country.objects.filter(code__iexact=country.code).first() or \
                      Country.objects.filter(name__iexact=country.name).first()

    if province_code and not province_name: province_name = PROV_CODE_TO_NAME.get(province_code.upper())
    if province_name and not province_code: province_code = PROV_NAME_TO_CODE.get(province_name.lower())
    province = Province.objects.filter(country=country, code__iexact=province_code).first() \
        or Province.objects.filter(country=country, name__iexact=province_name).first()
    if not province:
        province = Province(country=country, name=province_name, code=(province_code or "").upper())
        province.full_clean()
        try: province.save()
        except IntegrityError:
            province = Province.objects.filter(country=country, code__iexact=province.code).first() or \
                       Province.objects.filter(country=country, name__iexact=province.name).first()

    # City
    city = City.objects.filter(province=province, name__iexact=city_name).first()
    if not city:
        city = City(province=province, name=city_name)
        city.full_clean()
        try: city.save()
        except IntegrityError:
            city = City.objects.filter(province=province, name__iexact=city_name).first()

    return country, province, city

class AddressCreateSerializer(serializers.Serializer):
    country_name   = serializers.CharField(required=False, allow_blank=False)
    country_code   = serializers.CharField(required=False, allow_blank=False)
    province_name  = serializers.CharField(required=False, allow_blank=False)
    province_code  = serializers.CharField(required=False, allow_blank=False)
    city_name      = serializers.CharField(required=True, allow_blank=False)

    # Address inputs
    street_number  = serializers.CharField(required=True, allow_blank=False)
    street_name    = serializers.CharField(required=True, allow_blank=False)
    unit_suite     = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    postal_code    = serializers.CharField(required=True, allow_blank=False)

    def to_representation(self, instance: Address):
        return {
            "id": instance.id,
            "street_number": instance.street_number,
            "street_name": instance.street_name,
            "unit_suite": instance.unit_suite,
            "postal_code": instance.postal_code_formatted,
            "city": {
                "id": instance.city.id,
                "name": instance.city.name,
            },
            "province": {
                "id": instance.city.province.id,
                "name": instance.city.province.name,
                "code": instance.city.province.code,
            },
            "country": {
                "id": instance.city.province.country.id,
                "name": instance.city.province.country.name,
                "code": instance.city.province.country.code,
            },
            "date_created": instance.date_created,
            "date_updated": instance.date_updated,
        }

    def validate(self, attrs):
        if not attrs.get("country_code") and not attrs.get("country_name"):
            raise serializers.ValidationError({"country": "Provide country_name or country_code."})

        if not attrs.get("province_code") and not attrs.get("province_name"):
            raise serializers.ValidationError({"province": "Provide province_name or province_code."})

        if not attrs.get("city_name"):
            raise serializers.ValidationError({"city_name": "City name is required."})

        for key in ("country_code", "province_code"):
            if attrs.get(key):
                attrs[key] = attrs[key].strip().upper()

        for key in ("country_name", "province_name", "city_name", "street_number", "street_name", "postal_code"):
            if attrs.get(key):
                attrs[key] = attrs[key].strip()

        p_code = attrs.get("province_code")
        p_name = attrs.get("province_name")

        if p_code and p_code not in PROV_CODE_TO_NAME:
            raise serializers.ValidationError({"province_code": "Invalid province code."})

        if p_name and p_name.lower() not in PROV_NAME_TO_CODE and not p_code:
            raise serializers.ValidationError({"province_name": "Invalid province name; supply a valid code."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        country_name  = validated_data.get("country_name")
        country_code  = validated_data.get("country_code")
        province_name = validated_data.get("province_name")
        province_code = validated_data.get("province_code")
        city_name     = validated_data["city_name"]

        street_number = validated_data["street_number"]
        street_name   = validated_data["street_name"]
        unit_suite    = validated_data.get("unit_suite")
        postal_code   = validated_data["postal_code"]

        country = None
        if country_code:
            country = Country.objects.filter(code__iexact=country_code).first()
        if not country and country_name:
            country = Country.objects.filter(name__iexact=country_name).first()
        if not country:
            if not country_code and country_name:
                country_code = _derive_country_code_from_name(country_name)
            if not country_name and country_code:
                country_name = country_code
            country = Country(name=country_name, code=country_code)
            country.full_clean()
            try:
                country.save()
            except IntegrityError:
                country = Country.objects.filter(code__iexact=country_code).first() or \
                          Country.objects.filter(name__iexact=country_name).first()

        if province_code and not province_name:
            province_name = PROV_CODE_TO_NAME.get(province_code)
        if province_name and not province_code:
            province_code = PROV_NAME_TO_CODE.get(province_name.lower())

        province = (
            Province.objects.filter(country=country, code__iexact=province_code).first()
            or Province.objects.filter(country=country, name__iexact=province_name).first()
        )
        if not province:
            province = Province(country=country, name=province_name, code=province_code)
            province.full_clean()
            try:
                province.save()
            except IntegrityError:
                province = (
                    Province.objects.filter(country=country, code__iexact=province_code).first()
                    or Province.objects.filter(country=country, name__iexact=province_name).first()
                )

        city = City.objects.filter(province=province, name__iexact=city_name).first()
        if not city:
            city = City(province=province, name=city_name)
            city.full_clean()
            try:
                city.save()
            except IntegrityError:
                city = City.objects.filter(province=province, name__iexact=city_name).first()

class AddressUpdateSerializer(serializers.ModelSerializer):
    country_name  = serializers.CharField(required=False)
    country_code  = serializers.CharField(required=False)
    province_name = serializers.CharField(required=False)
    province_code = serializers.CharField(required=False)
    city_name     = serializers.CharField(required=False)

    class Meta:
        model = Address
        fields = [
            "street_number", "street_name", "unit_suite", "postal_code",
            "country_name", "country_code", "province_name", "province_code", "city_name",
        ]
        extra_kwargs = {
            "street_number": {"required": False},
            "street_name":   {"required": False},
            "postal_code":   {"required": False},
        }

    def validate(self, attrs):
        wants_geo_change = any(k in attrs for k in ("country_name","country_code","province_name","province_code","city_name"))
        if wants_geo_change:
            if not attrs.get("city_name"):
                attrs["city_name"] = self.instance.city.name
            attrs.setdefault("province_name", self.instance.city.province.name)
            attrs.setdefault("province_code", self.instance.city.province.code)
            attrs.setdefault("country_name", self.instance.city.province.country.name)
            attrs.setdefault("country_code", self.instance.city.province.country.code)
        return attrs

    @transaction.atomic
    def update(self, instance, validated):
        if any(k in validated for k in ("country_name","country_code","province_name","province_code","city_name")):
            _, _, city = _resolve_geo(
                country_name = validated.get("country_name"),
                country_code = (validated.get("country_code") or "").upper() or None,
                province_name= validated.get("province_name"),
                province_code= (validated.get("province_code") or "").upper() or None,
                city_name    = validated.get("city_name"),
            )
            instance.city = city

        for f in ("street_number","street_name","unit_suite","postal_code"):
            if f in validated:
                setattr(instance, f, validated.get(f))

        instance.full_clean()
        instance.save()
        return instance
