from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Professional,
    ProfessionalService,
    ProfessionalInsurance,
    ProfessionalTrade,
    ProfessionalInventory,
    ProfessionalTask,
    ProfessionalRating,
    ProfessionalPayout,
)


@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'license_number', 'verification_status', 'is_verified', 'average_rating_display')
    search_fields = ('user__email', 'license_number')
    list_filter = ('verification_status', 'is_verified')
    readonly_fields = ('average_rating_display',)

    @admin.display(description="User Email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Average Rating")
    def average_rating_display(self, obj):
        if obj.average_rating is None:
            return "-"
        return f"{obj.average_rating:.2f} ⭐"

    # Hide sensitive fields from admin forms
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        readonly.extend(['license_number', 'verification_status'])
        return readonly


@admin.register(ProfessionalService)
class ProfessionalServiceAdmin(admin.ModelAdmin):
    list_display = ('professional_email', 'service_title')
    search_fields = ('professional__user__email', 'service__title')
    list_filter = ('service',)

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email

    @admin.display(description="Service")
    def service_title(self, obj):
        return obj.service.title


@admin.register(ProfessionalInsurance)
class ProfessionalInsuranceAdmin(admin.ModelAdmin):
    list_display = ('professional_email', 'insurance_provider_name', 'insurance_policy_number', 'insurance_expiry_date')
    search_fields = ('insurance_provider_name', 'insurance_policy_number')
    list_filter = ('insurance_expiry_date',)

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email


@admin.register(ProfessionalTrade)
class ProfessionalTradeAdmin(admin.ModelAdmin):
    list_display = ('professional_email', 'trade_license_number', 'trade_license_expiry_date')
    search_fields = ('trade_license_number',)
    list_filter = ('trade_license_expiry_date',)

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email


@admin.register(ProfessionalInventory)
class ProfessionalInventoryAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'quantity', 'unit', 'professional_email', 'date_added')
    search_fields = ('item_name', 'professional__user__email')
    list_filter = ('date_added',)

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email


@admin.register(ProfessionalTask)
class ProfessionalTaskAdmin(admin.ModelAdmin):
    list_display = ('worker_name', 'professional_email', 'start_date', 'start_time', 'end_time', 'status', 'price_per_hour')
    search_fields = ('worker_name', 'professional__user__email')
    list_filter = ('status', 'start_date')

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email


@admin.register(ProfessionalRating)
class ProfessionalRatingAdmin(admin.ModelAdmin):
    list_display = ('professional_email', 'user_email', 'rating', 'created_at')
    search_fields = ('professional__user__email', 'user__email')
    list_filter = ('rating', 'created_at')

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email

    @admin.display(description="User")
    def user_email(self, obj):
        return obj.user.email


@admin.register(ProfessionalPayout)
class ProfessionalPayoutAdmin(admin.ModelAdmin):
    list_display = ('professional_email', 'payouts_enabled', 'onboarding_complete', 'last_payout_status', 'last_payout_date')
    search_fields = ('professional__user__email', 'stripe_account_id')
    list_filter = ('payouts_enabled', 'onboarding_complete', 'last_payout_date')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email
