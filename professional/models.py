from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator, MinLengthValidator, MaxLengthValidator
from django.db import models, transaction
from django.db.models import Q, Avg, Count
from django.db.models.functions import Lower
from django.utils import timezone

from service.models import Service


def validate_file_size(file, max_size=5 * 1024 * 1024):
    if file.size > max_size:
        raise ValidationError(f"File size cannot exceed {max_size / (1024 * 1024)}MB. Current size: {file.size / (1024 * 1024):.2f} MB.")


def validate_file_format(file):
    valid_formats = ['application/pdf', 'image/jpeg', 'image/png']
    if file.content_type not in valid_formats:
        raise ValidationError("File must be a PDF, JPG, JPEG, or PNG.")


digits_only = RegexValidator(r'^\d+$', 'Digits only.')


class Professional(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    class IssuedId(models.TextChoices):
        PASSPORT = 'passport', 'Passport'
        DRIVER_LICENSE = 'driver_license', 'Driver License'
        PR = 'pr', 'Permanent Resident Card'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='professional_profile'
    )
    license_number = models.CharField(max_length=255)
    government_issued_id = models.CharField(
        max_length=20,
        choices=IssuedId.choices,
        default=IssuedId.DRIVER_LICENSE
    )
    certification = models.FileField(upload_to='professional_certification/', blank=True, null=True, validators=[validate_file_size, validate_file_format])
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )

    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['user__email']
        constraints = [
            models.UniqueConstraint(Lower('license_number'), name='uniq_professional_license_ci'),
            models.CheckConstraint(
                check=(
                    Q(verification_status='approved') & Q(is_verified=True)
                ) | (
                    Q(verification_status__in=['pending', 'rejected']) & Q(is_verified=False)
                ),
                name='chk_professional_verified_consistent',
            ),
        ]
        indexes = [
            models.Index(fields=['verification_status']),
            models.Index(fields=['is_verified']),
        ]

    def __str__(self):
        return self.user.email

    @property
    def average_rating(self):
        avg_rating = self.ratings.aggregate(avg=Avg('rating'))['avg']
        return round(avg_rating, 2) if avg_rating is not None else None

    def save(self, *args, **kwargs):
        with transaction.atomic():
            res = super().save(*args, **kwargs)
            user = self.user
            if hasattr(user, 'is_professional') and hasattr(user, 'is_provider'):
                if not user.is_professional or user.is_provider:
                    user.is_professional = True
                    user.is_provider = False
                    user.save(update_fields=['is_professional', 'is_provider'])
            return res

    def update_rating_cache(self):
        agg = self.ratings.aggregate(avg=Avg("rating"), cnt=Count("id"))
        avg = agg["avg"]
        cnt = agg["cnt"] or 0
        self.rating_avg = round(Decimal(avg), 2) if avg is not None else None
        self.rating_count = cnt
        self.save(update_fields=["rating_avg", "rating_count"])

    def registration_completion_percent(self) -> int:
        total = 3
        score = 0
        if self.services.exists():
            score += 1
        if self.trades.exists():
            score += 1
        if hasattr(self, "insurance"):
            score += 1
        return int(round((score / total) * 100))
    
    @property
    def registration_completion(self) -> int:
        return self.registration_completion_percent()

    def delete(self, *args, **kwargs):
        storage = self.certification.storage if self.certification else None
        name = self.certification.name if self.certification else None
        with transaction.atomic():
            user = self.user
            res = super().delete(*args, **kwargs)
            if hasattr(user, 'is_professional') and hasattr(user, 'is_provider'):
                if user.is_professional or not user.is_provider:
                    user.is_professional = False
                    user.is_provider = True
                    user.save(update_fields=['is_professional', 'is_provider'])
        if storage and name:
            storage.delete(name)
        return res


class ProfessionalService(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='professional_services')
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='services')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['service', 'professional'], name='uniq_professional_service'),
        ]
        indexes = [
            models.Index(fields=['professional']),
            models.Index(fields=['service']),
        ]

    def __str__(self):
        return f"{self.professional.user.email} - {self.service.title}"


class ProfessionalInsurance(models.Model):
    professional = models.OneToOneField(Professional, on_delete=models.CASCADE, related_name='insurance')
    insurance_provider_name = models.CharField(max_length=255)
    insurance_policy_number = models.CharField(max_length=255, unique=True)
    insurance_file = models.FileField(upload_to='insurance_files/', null=True, blank=True, validators=[validate_file_size, validate_file_format])
    insurance_expiry_date = models.DateField()

    class Meta:
        ordering = ['insurance_expiry_date']
        indexes = [
            models.Index(fields=['insurance_expiry_date']),
        ]

    def clean(self):
        super().clean()
        if self.insurance_expiry_date and self.insurance_expiry_date < timezone.localdate():
            raise ValidationError({'insurance_expiry_date': 'Insurance expiry date cannot be in the past.'})

    def __str__(self):
        return f"{self.insurance_provider_name} ({self.insurance_policy_number})"

    def delete(self, *args, **kwargs):
        storage = self.insurance_file.storage if self.insurance_file else None
        name = self.insurance_file.name if self.insurance_file else None
        super().delete(*args, **kwargs)
        if storage and name:
            storage.delete(name)


class ProfessionalTrade(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='trades')
    trade_license_number = models.CharField(max_length=255, unique=True)
    trade_license_file = models.FileField(upload_to='trade_license/', null=True, blank=True, validators=[validate_file_size, validate_file_format])
    trade_license_expiry_date = models.DateField()

    class Meta:
        ordering = ['trade_license_expiry_date']
        indexes = [
            models.Index(fields=['trade_license_expiry_date']),
        ]

    def clean(self):
        super().clean()
        if self.trade_license_expiry_date and self.trade_license_expiry_date < timezone.localdate():
            raise ValidationError({'trade_license_expiry_date': 'Trade license expiry date cannot be in the past.'})

    def __str__(self):
        return f"Trade License: {self.trade_license_number}"

    def delete(self, *args, **kwargs):
        storage = self.trade_license_file.storage if self.trade_license_file else None
        name = self.trade_license_file.name if self.trade_license_file else None
        super().delete(*args, **kwargs)
        if storage and name:
            storage.delete(name)


class ProfessionalRating(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='professional_ratings')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['professional', 'user'], name='uniq_rating_per_user_professional'),
            models.CheckConstraint(check=Q(rating__gte=1) & Q(rating__lte=5), name='chk_professional_rating_between_1_5'),
        ]
        indexes = [
            models.Index(fields=['professional']),
            models.Index(fields=['user']),
            models.Index(fields=['rating']),
        ]

    def __str__(self):
        return f"{self.rating}⭐ by {self.user.email} for {self.professional.user.email}"

    def clean(self):
        super().clean()
        if self.professional and self.user_id == self.professional.user_id:
            raise ValidationError("You cannot rate yourself.")
        if not (1 <= int(self.rating) <= 5):
            raise ValidationError("Rating must be between 1 and 5.")

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        self.professional.update_rating_cache()

    def delete(self, *args, **kwargs):
        pro = self.professional
        super().delete(*args, **kwargs)
        pro.update_rating_cache()


class ProfessionalPayout(models.Model):
    professional = models.OneToOneField(
        Professional,
        on_delete=models.CASCADE,
        related_name="payout"
    )
    stripe_account_id = models.CharField(max_length=64, blank=True, null=True)
    payouts_enabled = models.BooleanField(default=False)
    onboarding_complete = models.BooleanField(default=False)
    last_payout_status = models.CharField(max_length=32, blank=True, null=True)
    last_payout_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payout info for {self.professional.user.email}"


class BankInfo(models.Model):
    professional = models.OneToOneField(
        Professional,
        on_delete=models.CASCADE,
        related_name='bank_info'
    )
    institution_name = models.CharField(max_length=255, blank=True, null=True)
    institution_number = models.CharField(
        max_length=3, blank=True, null=True,
        validators=[MinLengthValidator(3), MaxLengthValidator(3), digits_only]
    )
    transit_number = models.CharField(
        max_length=5, blank=True, null=True,
        validators=[MinLengthValidator(5), MaxLengthValidator(5), digits_only]
    )
    account_number = models.CharField(
        max_length=34, blank=True, null=True,
        validators=[RegexValidator(r'^[A-Za-z0-9]+$', 'Letters and digits only.')]
    )
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['professional']),
            models.Index(fields=['institution_number', 'transit_number']),
        ]
        verbose_name = 'Bank info'
        verbose_name_plural = 'Bank info'

    def __str__(self):
        return f'{self.professional} — {self.institution_name or "Bank"}'

    @property
    def account_last4(self):
        return (self.account_number or '')[-4:] if self.account_number else ''

    @property
    def masked_account_number(self):
        if not self.account_number:
            return ''
        n = len(self.account_number)
        return f'{"*" * max(n-4, 0)}{self.account_number[-4:]}'