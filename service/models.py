from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, Avg
from django.db.models.functions import Lower


class ServiceCategory(models.Model):
    title = models.CharField(max_length=50, unique=True)
    photo = models.ImageField(upload_to='service_category/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Service Categories"
        ordering = ['title']
        constraints = [
            models.UniqueConstraint(Lower('title'), name='uniq_servicecategory_title_ci'),
        ]
        indexes = [
            models.Index(Lower('title'), name='idx_servicecategory_title_ci'),
        ]

    def __str__(self):
        return self.title


class Unit(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(Lower('name'), name='uniq_unit_name_ci'),
            models.UniqueConstraint(
                Lower('code'),
                name='uniq_unit_code_ci',
                condition=Q(code__isnull=False),
            ),
        ]
        indexes = [
            models.Index(Lower('name'), name='idx_unit_name_ci'),
            models.Index(Lower('code'), name='idx_unit_code_ci'),
        ]

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class Service(models.Model):
    title = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    categories = models.ManyToManyField(ServiceCategory, related_name='services', blank=True)
    is_trade_required = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, blank=True, null=True, related_name='services')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']
        constraints = [
            models.UniqueConstraint(Lower('title'), name='uniq_service_title_ci'),
        ]
        indexes = [
            models.Index(Lower('title'), name='idx_service_title_ci'),
            models.Index(fields=['is_trade_required', 'price']),
        ]

    def __str__(self):
        return self.title

    @property
    def average_rating(self):
        result = self.ratings.aggregate(avg_rating=Avg('rating'))
        return round(result['avg_rating'], 2) if result['avg_rating'] is not None else None


class ServiceType(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='types')
    title = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['service', 'title']
        constraints = [
            models.UniqueConstraint(Lower('title'), 'service', name='uniq_servicetype_title_service_ci'),
        ]
        indexes = [
            models.Index(Lower('title'), name='idx_servicetype_title_ci'),
            models.Index(fields=['service', 'title']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        return f"{self.service.title} - {self.title}"


class ServicePhoto(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='service_photos/')
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Photo for {self.service.title}"

    def delete(self, *args, **kwargs):
        storage = self.photo.storage
        name = self.photo.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)


class ServiceTypePhoto(models.Model):
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='service_type_photos/')
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Photo for {self.service_type}"

    def delete(self, *args, **kwargs):
        storage = self.photo.storage
        name = self.photo.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)


class Rating(models.Model):
    service = models.ForeignKey(Service, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='service_ratings', on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['service', 'user'], name='uniq_rating_per_user_service'),
            models.CheckConstraint(check=Q(rating__gte=1) & Q(rating__lte=5), name='chk_rating_between_1_5'),
        ]
        indexes = [
            models.Index(fields=['service']),
            models.Index(fields=['user']),
            models.Index(fields=['rating']),
        ]

    def __str__(self):
        return f"{self.rating}⭐ by {self.user.email} for {self.service.title}"

    def clean(self):
        super().clean()
        if not (1 <= self.rating <= 5):
            raise ValidationError("Rating must be between 1 and 5.")
