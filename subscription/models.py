from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=50, unique=True)
    stripe_plan_id = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(0.00)]
    )
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['price']
        indexes = [
            models.Index(fields=['stripe_plan_id']),
        ]

    def __str__(self):
        return f"{self.name} (${self.price})"

class UserSubscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='professional_subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_subscriptions'
    )
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    active = models.BooleanField(default=False)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    trial_end = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['active']),
            models.Index(fields=['end_date']),
        ]

    def __str__(self):
        plan_name = self.plan.name if self.plan else 'No Plan'
        status = 'Active' if self.active else 'Inactive'
        return f"{self.user.email} - {plan_name} ({status})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError('End date must be after start date.')
        if self.trial_end and self.start_date and self.trial_end < self.start_date:
            raise ValidationError('Trial end date cannot be before start date.')