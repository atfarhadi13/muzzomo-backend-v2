from uuid import uuid4
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, EmailValidator, URLValidator
from django.db import models
from django.utils import timezone


def validate_hex_color(value: str):
    if value is None:
        return
    value = value.strip()
    hex_re = RegexValidator(regex=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
    hex_re(value)


def validate_file_size(file, max_size=5 * 1024 * 1024):
    if file and getattr(file, "size", 0) > max_size:
        raise ValidationError(f"File size cannot exceed {max_size // (1024 * 1024)}MB.")


def validate_image_mime(file):
    allowed = {"image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/x-icon"}
    ctype = getattr(file, "content_type", None)
    if ctype and ctype not in allowed:
        raise ValidationError("Invalid image type. Allowed: PNG, JPEG, WEBP, SVG, ICO.")


class AppSettings(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    site_name = models.CharField(max_length=120, default="App")
    primary_color = models.CharField(max_length=7, validators=[validate_hex_color], default="#0ea5e9")
    secondary_color = models.CharField(max_length=7, validators=[validate_hex_color], default="#1f2937")
    font_family = models.CharField(max_length=120, default="Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif")
    logo = models.FileField(upload_to="branding/logo/", blank=True, null=True, validators=[validate_file_size, validate_image_mime])
    favicon = models.FileField(upload_to="branding/favicon/", blank=True, null=True, validators=[validate_file_size, validate_image_mime])
    privacy_policy = models.TextField(blank=True, default="")
    terms_and_conditions = models.TextField(blank=True, default="")
    support_email = models.EmailField(blank=True, null=True, validators=[EmailValidator()])
    support_phone = models.CharField(max_length=50, blank=True, null=True)
    website_url = models.URLField(blank=True, null=True, validators=[URLValidator()])
    ios_store_url = models.URLField(blank=True, null=True, validators=[URLValidator()])
    android_store_url = models.URLField(blank=True, null=True, validators=[URLValidator()])
    maintenance_mode = models.BooleanField(default=False)
    locale = models.CharField(max_length=10, default="en")
    extra = models.JSONField(blank=True, null=True, default=dict)
    version = models.CharField(max_length=36, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["updated_at"]),
            models.Index(fields=["maintenance_mode"]),
            models.Index(fields=["locale"]),
        ]

    def __str__(self):
        return f"{self.site_name} settings"

    def clean(self):
        validate_hex_color(self.primary_color)
        validate_hex_color(self.secondary_color)

    def save(self, *args, **kwargs):
        self.full_clean()
        old = None
        if self.pk:
            try:
                old = AppSettings.objects.get(pk=self.pk)
            except AppSettings.DoesNotExist:
                old = None
        res = super().save(*args, **kwargs)
        if old:
            if old.logo and old.logo != self.logo:
                try:
                    storage, name = old.logo.storage, old.logo.name
                    if storage and name:
                        storage.delete(name)
                except Exception:
                    pass
            if old.favicon and old.favicon != self.favicon:
                try:
                    storage, name = old.favicon.storage, old.favicon.name
                    if storage and name:
                        storage.delete(name)
                except Exception:
                    pass
        if not self.version:
            self.version = str(uuid4())
            super().save(update_fields=["version"])
        return res

    def delete(self, *args, **kwargs):
        logo_storage = self.logo.storage if self.logo else None
        logo_name = self.logo.name if self.logo else None
        favicon_storage = self.favicon.storage if self.favicon else None
        favicon_name = self.favicon.name if self.favicon else None
        res = super().delete(*args, **kwargs)
        try:
            if logo_storage and logo_name:
                logo_storage.delete(logo_name)
            if favicon_storage and favicon_name:
                favicon_storage.delete(favicon_name)
        except Exception:
            pass
        return res

    @property
    def theme(self):
        return {
            "primary": self.primary_color,
            "secondary": self.secondary_color,
            "font": self.font_family,
        }

    def bump_version(self):
        self.version = str(uuid4())
        self.updated_at = timezone.now()
        self.save(update_fields=["version", "updated_at"])
