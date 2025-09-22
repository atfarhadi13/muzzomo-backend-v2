from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import models
from django.db.models import Q, Avg
from django.db.models.functions import Lower
from django.utils import timezone
from service.models import Service
from django.db import transaction

phone_validator = RegexValidator(r'^\+?\d{7,15}$', 'Enter a valid phone number (7-15 digits, optional leading "+").')
sin_digits_validator = RegexValidator(r'^\d{9}$', 'SIN must be exactly 9 digits.')
institution_number_validator = RegexValidator(r'^\d{3}$', 'Institution number must be 3 digits.')
transit_number_validator = RegexValidator(r'^\d{5}$', 'Transit number must be 5 digits.')
account_number_validator = RegexValidator(r'^\d{5,12}$', 'Account number must be 5–12 digits.')

def _luhn_valid(num: str) -> bool:
    total = 0
    alt = False
    for d in reversed(num):
        n = ord(d) - 48
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0

class Professional(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING  = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    class IssuedId(models.TextChoices):
        PASSPORT = 'passport', 'Passport'
        DRIVER_LICENSE = 'driver_license', 'Driver License'
        PR = 'pr', 'Permanent Resident Card'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='professional_profile')
    sin = models.CharField(max_length=9, validators=[sin_digits_validator], null=True, blank=True, unique=True)

    license_number = models.CharField(max_length=255)
    government_issued_id = models.CharField(max_length=20, choices=IssuedId.choices, default=IssuedId.DRIVER_LICENSE)
    certification = models.FileField(upload_to='professional_certification/', blank=True, null=True)

    institution_name = models.CharField(max_length=255, blank=True, null=True)
    institution_number = models.CharField(max_length=3, blank=True, null=True, validators=[institution_number_validator])
    transit_number = models.CharField(max_length=5, blank=True, null=True, validators=[transit_number_validator])
    account_number = models.CharField(max_length=12, blank=True, null=True, validators=[account_number_validator])
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)

    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.PENDING)

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

    def clean(self):
        super().clean()
        if self.sin and not _luhn_valid(self.sin):
            raise ValidationError({'sin': 'Invalid SIN (failed checksum).'})
        trio = [self.institution_number, self.transit_number, self.account_number]
        if any(trio) and not all(trio):
            raise ValidationError('Provide institution number, transit number, and account number together.')

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            res = super().save(*args, **kwargs)
            user = self.user
            if not user.is_professional or user.is_provider:
                user.is_professional = True
                user.is_provider = False
                user.save(update_fields=['is_professional', 'is_provider'])
            return res

    def delete(self, *args, **kwargs):
        storage = self.certification.storage if self.certification else None
        name = self.certification.name if self.certification else None
        with transaction.atomic():
            user = self.user
            res = super().delete(*args, **kwargs)
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
    insurance_file = models.FileField(upload_to='insurance_files/', null=True, blank=True)
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
    trade_license_file = models.FileField(upload_to='trade_license/', null=True, blank=True)
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

class ProfessionalInventory(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='inventories')
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    unit = models.CharField(max_length=50, blank=True, null=True)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_added']
        constraints = [
            models.CheckConstraint(check=Q(quantity__gte=Decimal('0')), name='chk_inventory_qty_gte_zero'),
        ]
        indexes = [
            models.Index(fields=['item_name']),
            models.Index(fields=['professional']),
        ]

    def __str__(self):
        unit_display = f" {self.unit}" if self.unit else ""
        return f"{self.item_name} ({self.quantity}{unit_display}) - {self.professional.user.email}"

class ProfessionalTaskStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'

class ProfessionalTask(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='tasks')
    worker_name = models.CharField(max_length=255)
    worker_phone = models.CharField(max_length=20, blank=True, null=True, validators=[phone_validator])
    worker_email = models.EmailField(blank=True, null=True)
    start_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(blank=True, null=True)
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=ProfessionalTaskStatus.choices, default=ProfessionalTaskStatus.PENDING)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_created']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['professional']),
            models.Index(fields=['start_date']),
        ]
        constraints = [
            models.CheckConstraint(check=Q(price_per_hour__gte=Decimal('0')), name='chk_task_price_gte_zero'),
        ]

    def __str__(self):
        return f"Task for {self.worker_name} on {self.start_date}"

    def clean(self):
        super().clean()
        if self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'End time must be after start time.'})

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
        if not (1 <= self.rating <= 5):
            raise ValidationError("Rating must be between 1 and 5.")
