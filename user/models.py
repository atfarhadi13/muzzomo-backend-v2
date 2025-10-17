from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.core.validators import RegexValidator, MinLengthValidator
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

import secrets
import os
from datetime import datetime

phone_validator = RegexValidator(
    regex=r"^\+?\d{7,15}$",
    message='Enter a valid phone number (7-15 digits, optional leading "+").',
)

def validate_image_size(image):
    max_size = 5 * 1024 * 1024
    if image.size > max_size:
        from django.core.exceptions import ValidationError
        raise ValidationError(
            f"Profile image cannot be larger than 5MB. Current size: {image.size / (1024 * 1024):.2f} MB."
        )

def validate_image_format(image):
    valid_formats = ["image/png", "image/jpeg", "image/webp"]
    if getattr(image, "content_type", None) not in valid_formats:
        from django.core.exceptions import ValidationError
        raise ValidationError("Profile image must be PNG, JPG, JPEG, or WEBP.")

def profile_image_upload_to(instance, filename):
    now = datetime.now()
    base_filename = f"{(instance.first_name or 'user')}_{(instance.last_name or 'img')}_{now.strftime('%Y%m%d_%H%M%S')}"
    ext = filename.split(".")[-1]
    return os.path.join(str(now.year), now.strftime("%B"), str(now.day), f"{base_filename}.{ext}")

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True, validators=[MinLengthValidator(2)])
    last_name = models.CharField(max_length=30, blank=True, validators=[MinLengthValidator(2)])
    phone_number = models.CharField(max_length=20, blank=True, null=True, validators=[phone_validator])
    profile_image = models.ImageField(
        upload_to=profile_image_upload_to,
        null=True,
        blank=True,
        validators=[validate_image_size, validate_image_format],
        default="path_to_default_image",
    )

    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True, unique=True)

    is_provider = models.BooleanField(default=False)
    is_professional = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    email_verified_at = models.DateTimeField(null=True, blank=True)

    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_failure = models.DateTimeField(null=True, blank=True)

    token_valid_after = models.DateTimeField(default=timezone.now)
    last_password_changed_at = models.DateTimeField(default=timezone.now)

    last_email_changed_at = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        ordering = ["email"]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and timezone.now() < self.locked_until)

    @property
    def full_name(self):
        return f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip() or None

    def register_failed_login(self, threshold=5, lock_minutes=15):
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        self.last_login_failure = timezone.now()
        if self.failed_login_attempts >= threshold:
            self.locked_until = timezone.now() + timedelta(minutes=lock_minutes)
        self.save(update_fields=["failed_login_attempts", "last_login_failure", "locked_until"])

    def reset_login_failures(self):
        if self.failed_login_attempts or self.locked_until or self.last_login_failure:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.last_login_failure = None
            self.save(update_fields=["failed_login_attempts", "locked_until", "last_login_failure"])

class OneTimeCodeQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        return self.filter(used_at__isnull=True, expires_at__gt=now)

class OneTimeCode(models.Model):
    PURPOSE_LOGIN = 'login_otp'
    PURPOSE_RESET = 'password_reset'
    PURPOSE_EMAIL = 'email_update'
    PURPOSE_UNLOCK = 'account_unlock'
    PURPOSE_REACTIVATE = 'account_reactivate'

    PURPOSE_CHOICES = [
        (PURPOSE_LOGIN, 'Login OTP'),
        (PURPOSE_RESET, 'Password Reset'),
        (PURPOSE_EMAIL, 'Email Update'),
        (PURPOSE_UNLOCK, 'Account Unlock'),
        (PURPOSE_REACTIVATE, 'Account Reactivation'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='one_time_codes')
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=128, editable=False)
    new_email = models.EmailField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    verify_attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)

    objects = OneTimeCodeQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'purpose']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['used_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'purpose'],
                condition=Q(used_at__isnull=True),
                name='uniq_active_code_per_user_purpose',
            ),
        ]

    def __str__(self):
        return f"{self.purpose} for {self.user_id} (used={self.used_at is not None})"

    @classmethod
    def _generate_numeric_code(cls, length=6) -> str:
        alphabet = '0123456789'
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @classmethod
    def _default_ttl(cls, purpose):
        if purpose == cls.PURPOSE_RESET:
            return timedelta(minutes=15)
        if purpose == cls.PURPOSE_EMAIL:
            return timedelta(minutes=30)
        if purpose == cls.PURPOSE_UNLOCK:
            return timedelta(minutes=10)
        if purpose == cls.PURPOSE_REACTIVATE:
            return timedelta(minutes=15)
        return timedelta(minutes=10)

    @classmethod
    def issue(cls, *, user, purpose, new_email=None, length=6, ttl=None) -> "OneTimeCode":
        if purpose == cls.PURPOSE_EMAIL:
            if not new_email:
                raise ValidationError({'new_email': 'new_email is required for email update.'})
            new_email = new_email.lower()
            if user.email and user.email.lower() == new_email:
                raise ValidationError({'new_email': 'New email must be different from current email.'})

        raw_code = cls._generate_numeric_code(length=length)
        expires_at = timezone.now() + (ttl or cls._default_ttl(purpose))

        with transaction.atomic():
            cls.objects.select_for_update().filter(user=user, purpose=purpose, used_at__isnull=True)\
                .update(used_at=timezone.now())

            obj = cls(
                user=user,
                purpose=purpose,
                code_hash=make_password(raw_code),
                new_email=new_email.lower() if new_email else None,
                expires_at=expires_at,
            )
            obj.full_clean()
            obj.save()

        obj.raw_code = raw_code
        return obj

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def clean(self):
        super().clean()
        if self.new_email:
            self.new_email = self.new_email.lower()

        if self.purpose == self.PURPOSE_EMAIL and not self.new_email:
            raise ValidationError({'new_email': 'new_email is required for email update.'})
        if self.purpose != self.PURPOSE_EMAIL and self.new_email:
            raise ValidationError({'new_email': 'new_email must be empty unless purpose is email update.'})

        if self.purpose == self.PURPOSE_EMAIL and self.new_email:
            User = get_user_model()
            if User.objects.filter(email__iexact=self.new_email).exists():
                raise ValidationError({'new_email': 'This email is already in use.'})

    def verify(self, raw_code: str) -> bool:
        if self.is_used or self.is_expired:
            return False
        return check_password(raw_code, self.code_hash)

    def mark_used(self):
        if not self.is_used:
            self.used_at = timezone.now()
            self.save(update_fields=['used_at'])

    @classmethod
    def verify_and_consume(cls, *, user, purpose, raw_code: str) -> bool:
        with transaction.atomic():
            code = cls.objects.select_for_update().active().filter(user=user, purpose=purpose).first()
            if not code:
                return False
            if code.verify_attempts >= code.max_attempts:
                code.used_at = timezone.now()
                code.save(update_fields=["verify_attempts", "used_at"])
                return False
            ok = check_password(raw_code, code.code_hash)
            code.verify_attempts += 1
            if ok:
                code.used_at = timezone.now()
            code.save(update_fields=["verify_attempts", "used_at"])
            return ok
