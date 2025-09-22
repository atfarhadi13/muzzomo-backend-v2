from django.db import models
from django.core.validators import RegexValidator, MinLengthValidator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.functions import Lower

from user.models import CustomUser

PROVINCE_CHOICES = (
    ("AB", "Alberta"),
    ("BC", "British Columbia"),
    ("MB", "Manitoba"),
    ("NB", "New Brunswick"),
    ("NL", "Newfoundland and Labrador"),
    ("NS", "Nova Scotia"),
    ("NT", "Northwest Territories"),
    ("NU", "Nunavut"),
    ("ON", "Ontario"),
    ("PE", "Prince Edward Island"),
    ("QC", "Quebec"),
    ("SK", "Saskatchewan"),
    ("YT", "Yukon"),
)


name_validator = RegexValidator(
    r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9\s\-\.'’/]+$",
    "Only letters (incl. accents), numbers, spaces, hyphens, apostrophes, periods, and slashes are allowed.",
)

country_code_validator = RegexValidator(r"^[A-Z]{2,10}$", "Code must contain 2–10 uppercase letters.")
province_code_validator = RegexValidator(r"^[A-Z]{2}$", "Province/territory code must be 2 uppercase letters.")

street_number_validator = RegexValidator(
    r"^[0-9A-Za-z]+(?:-[0-9A-Za-z]+)?$",
    "Use digits/letters, optionally a single hyphen (e.g., 12, 12A, 12-14).",
)

unit_validator = RegexValidator(
    r"^[A-Za-z0-9\-#/]+$",
    "Use letters/numbers and - # / only.",
)

postal_code_ca_validator = RegexValidator(
    r"^[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d$",
    "Enter a valid Canadian postal code (e.g., A1A 1A1).",
)


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True, validators=[name_validator])
    code = models.CharField(max_length=10, unique=True, validators=[country_code_validator])

    class Meta:
        verbose_name_plural = "Countries"

    def __str__(self):
        return self.name


class Province(models.Model):
    name = models.CharField(max_length=100, validators=[name_validator])
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="provinces")
    code = models.CharField(max_length=2, validators=[province_code_validator], choices=PROVINCE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "country",
                name="uniq_province_name_country_ci"
            ),
            models.UniqueConstraint(
                Lower("code"), "country",
                name="uniq_province_code_country_ci"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class City(models.Model):
    name = models.CharField(max_length=100, validators=[name_validator])
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="cities")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "province",
                name="uniq_city_name_province_ci"
            )
        ]
        indexes = [
            models.Index(fields=["province"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.province.code}"


class Address(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="addresses")

    street_number = models.CharField(
        max_length=20,
        validators=[MinLengthValidator(1), street_number_validator],
        help_text="e.g., 123, 12A, 12-14",
    )
    street_name = models.CharField(
        max_length=255,
        validators=[name_validator],
        help_text="e.g., St. George Street / 3e Avenue",
    )
    unit_suite = models.CharField(
        max_length=20,
        null=True, blank=True,
        validators=[unit_validator],
        help_text="e.g., 5B, #1203 (optional)",
    )

    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="addresses")

    postal_code = models.CharField(max_length=7, validators=[postal_code_ca_validator], db_index=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Addresses"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["postal_code"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(latitude__gte=-90.0) & Q(latitude__lte=90.0) | Q(latitude__isnull=True),
                name="chk_lat_range",
            ),
            models.CheckConstraint(
                check=Q(longitude__gte=-180.0) & Q(longitude__lte=180.0) | Q(longitude__isnull=True),
                name="chk_lng_range",
            ),
        ]

    def __str__(self):
        unit = f"Unit {self.unit_suite}, " if self.unit_suite else ""
        return f"{unit}{self.street_number} {self.street_name}, {self.city}, {self.postal_code_formatted}"

    @property
    def province(self):
        return self.city.province

    @property
    def country(self):
        return self.city.province.country

    @property
    def postal_code_formatted(self) -> str:
        pc = (self.postal_code or "").replace(" ", "").upper()
        return f"{pc[:3]} {pc[3:]}" if len(pc) == 6 else pc

    def clean(self):
        super().clean()
        if self.postal_code:
            pc = self.postal_code.replace(" ", "").upper()
            self.postal_code = pc

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
