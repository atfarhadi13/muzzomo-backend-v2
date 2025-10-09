from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction, IntegrityError
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

from service.models import Service, ServiceType
from professional.models import Professional, ProfessionalService
from address.models import Address

class JobStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'

class JobOfferStatus(models.TextChoices):
    SENT = 'sent', 'Sent'
    VIEWED = 'viewed', 'Viewed'
    ACCEPTED = 'accepted', 'Accepted'
    DECLINED = 'declined', 'Declined'
    EXPIRED = 'expired', 'Expired'

class JobUnitUpdateRequestStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    CANCELLED = 'cancelled', 'Cancelled'

class Job(models.Model):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='jobs',
    )
    professional = models.ForeignKey(
        Professional,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='assigned_jobs',
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='jobs',
    )

    service_types = models.ManyToManyField(
        ServiceType,
        through='JobServiceType',
        related_name='jobs',
        blank=True,
    )

    address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        related_name='jobs',
    )

    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    submit_date = models.DateTimeField(auto_now_add=True)
    start_at = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)

    quantity = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )

    total_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        db_index=True,
    )
    is_paid = models.BooleanField(default=False)
    stripe_session_id = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['user']),
            models.Index(fields=['professional']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['professional', 'status']),
            models.Index(fields=['address']),
        ]
        constraints = [
            models.CheckConstraint(check=Q(quantity__gt=0), name='chk_job_quantity_gt_zero'),
            models.CheckConstraint(check=Q(total_price__gte=0), name='chk_job_total_price_gte_zero'),
            models.CheckConstraint(
                check=Q(status__in=[JobStatus.PENDING, JobStatus.CANCELLED]) | Q(professional__isnull=False),
                name='chk_job_pro_required_for_active',
            ),
            models.CheckConstraint(
                check=Q(status__in=[JobStatus.PENDING, JobStatus.IN_PROGRESS, JobStatus.CANCELLED]) | Q(completed_date__isnull=False),
                name='chk_job_completed_has_date',
            ),
        ]

    def __str__(self):
        return f"{self.title} by {self.user.email}"
    
    @property
    def unit_price(self):
        return self.service.price

    @property
    def paid_units(self):
        if not self.service_id or self.unit_price == 0:
            return Decimal("0.00")
        units = (self.paid_amount / self.unit_price).quantize(Decimal("0.00"))
        return max(Decimal("0.00"), min(units, self.quantity))

    @property
    def remaining_units(self):
        rem = (self.quantity - self.paid_units)
        return rem if rem > 0 else Decimal("0.00")

    @property
    def outstanding_amount(self):
        rem = (self.total_price - (self.paid_amount or Decimal("0.00"))).quantize(Decimal("0.01"))
        return rem if rem > 0 else Decimal("0.00")

    def _validate_dates(self):
        ref = self.submit_date or timezone.now()
        if self.completed_date and self.completed_date < ref:
            raise ValidationError({'completed_date': 'Completion date cannot precede submission date.'})
        if self.start_at and self.start_at < ref:
            raise ValidationError({'start_at': 'Start time cannot precede submission date.'})

    def _validate_status(self):
        if self.status == JobStatus.COMPLETED:
            if not self.completed_date:
                raise ValidationError({'completed_date': 'Completed jobs must have a completion date.'})
            if not self.is_paid:
                raise ValidationError({'is_paid': 'Completed jobs must be marked as paid.'})

    def clean(self):
        super().clean()
        self._validate_dates()
        self._validate_status()

        if self.address_id and self.user_id and self.address.user_id != self.user_id:
            raise ValidationError({'address': "Address doesn't belong to this user."})

        if self.professional_id:
            if not ProfessionalService.objects.filter(
                professional_id=self.professional_id,
                service_id=self.service_id
            ).exists():
                raise ValidationError({'professional': 'Assigned professional does not offer this service.'})

    def save(self, *args, **kwargs):
        recalc = False
        if self._state.adding:
            recalc = True
        else:
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                if {'service', 'quantity'} & set(update_fields):
                    recalc = True
            elif self.pk:
                old = type(self).objects.only('service_id', 'quantity').get(pk=self.pk)
                if (old.service_id != self.service_id) or (old.quantity != self.quantity):
                    recalc = True

        if self.service_id and self.quantity is not None:
            computed_total = (self.service.price * self.quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if recalc or self.total_price != computed_total:
                self.total_price = computed_total

        paid = (self.paid_amount or Decimal("0.00")).quantize(Decimal("0.01"))
        total = (self.total_price or Decimal("0.00")).quantize(Decimal("0.01"))
        self.is_paid = paid >= total

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def computed_total_price(self) -> Decimal:
        return (self.service.price * self.quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

class JobAttachment(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='attachments')
    attachment = models.FileField(upload_to='job_attachments/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Attachment for {self.job.title}"

class JobServiceType(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='job_service_types')
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name='job_service_types')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['job', 'service_type'], name='uniq_job_service_type'),
        ]
        indexes = [
            models.Index(fields=['job']),
            models.Index(fields=['service_type']),
        ]

    def __str__(self):
        return f"{self.service_type.title} for {self.job.title}"

    def clean(self):
        super().clean()
        if self.job.service_id and self.service_type.service_id != self.job.service_id:
            raise ValidationError({'service_type': 'Service type must belong to the job service.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class JobUnitUpdateRequest(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='unit_update_requests')
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='unit_update_requests')
    new_unit_qty = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    status = models.CharField(
        max_length=20,
        choices=JobUnitUpdateRequestStatus.choices,
        default=JobUnitUpdateRequestStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'professional'],
                condition=Q(status=JobUnitUpdateRequestStatus.PENDING),
                name='uniq_pending_unit_update_per_job_professional',
            ),
        ]
        indexes = [
            models.Index(fields=['job', 'professional']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Unit update ({self.new_unit_qty}) for {self.job.title}"

    def clean(self):
        super().clean()
        if self.new_unit_qty <= 0:
            raise ValidationError({'new_unit_qty': 'New unit quantity must be greater than zero.'})
        if self.job.professional_id and self.professional_id != self.job.professional_id:
            raise ValidationError({'professional': 'Only the assigned professional can request unit updates.'})

    @transaction.atomic
    def accept(self):
        if self.status != JobUnitUpdateRequestStatus.PENDING:
            raise ValidationError('Only pending requests can be accepted.')

        job = Job.objects.select_for_update().get(pk=self.job_id)

        new_qty = (job.quantity or Decimal("0")) + self.new_unit_qty
        if new_qty <= Decimal("0"):
            raise ValidationError('Resulting job quantity must be greater than zero.')

        job.quantity = new_qty
        job.save(update_fields=['quantity', 'updated_at'])

        self.status = JobUnitUpdateRequestStatus.ACCEPTED
        self.save(update_fields=['status', 'updated_at'])

class JobOffer(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='offers')
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='job_offers')
    status = models.CharField(max_length=20, choices=JobOfferStatus.choices, default=JobOfferStatus.SENT, db_index=True)
    distance_km = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['job', 'professional'], name='uniq_job_offer'),
            models.UniqueConstraint(
                fields=['job'],
                condition=Q(status=JobOfferStatus.ACCEPTED),
                name='uniq_single_accepted_offer_per_job',
            ),
            models.CheckConstraint(
                check=Q(distance_km__gte=0) | Q(distance_km__isnull=True),
                name='chk_offer_distance_non_negative',
            ),
        ]
        indexes = [
            models.Index(fields=['job', 'status']),
            models.Index(fields=['professional', 'status']),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Offer of {self.job.title} → {self.professional.user.email} ({self.status})'

    def clean(self):
        super().clean()
        if not ProfessionalService.objects.filter(
            professional=self.professional,
            service=self.job.service
        ).exists():
            raise ValidationError('Professional does not provide the required service.')

    @transaction.atomic
    def accept(self):
        if self.status not in [JobOfferStatus.SENT, JobOfferStatus.VIEWED]:
            raise ValidationError('Only sent or viewed offers can be accepted.')

        locked_job = Job.objects.select_for_update().get(pk=self.job_id)

        if locked_job.professional_id and locked_job.professional_id != self.professional_id:
            raise ValidationError('Job already assigned to another professional.')

        locked_job.professional = self.professional
        if locked_job.status == JobStatus.PENDING:
            locked_job.status = JobStatus.IN_PROGRESS
        locked_job.save(update_fields=['professional', 'status', 'updated_at'])

        self.status = JobOfferStatus.ACCEPTED
        self.accepted_at = timezone.now()
        try:
            self.save(update_fields=['status', 'accepted_at', 'updated_at'])
        except IntegrityError:
            raise ValidationError('Another offer was accepted for this job just now. Please refresh.')

class JobRate(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='rate')
    rate = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    rated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(rate__gte=1) & Q(rate__lte=5), name='chk_jobrate_between_1_5'),
        ]
        indexes = [
            models.Index(fields=['rated_at']),
        ]

    def __str__(self):
        return f"Rating {self.rate} for {self.job.title}"