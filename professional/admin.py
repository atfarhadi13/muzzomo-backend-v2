from django.contrib import admin
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
    list_display = ('user', 'license_number', 'verification_status', 'is_verified')
    search_fields = ('user__email', 'license_number', 'sin')
    list_filter = ('verification_status', 'is_verified')
    readonly_fields = ('average_rating',)


@admin.register(ProfessionalService)
class ProfessionalServiceAdmin(admin.ModelAdmin):
    list_display = ('professional', 'service')
    search_fields = ('professional__user__email', 'service__title')
    list_filter = ('service',)


@admin.register(ProfessionalInsurance)
class ProfessionalInsuranceAdmin(admin.ModelAdmin):
    list_display = ('professional', 'insurance_provider_name', 'insurance_policy_number', 'insurance_expiry_date')
    search_fields = ('insurance_provider_name', 'insurance_policy_number')
    list_filter = ('insurance_expiry_date',)


@admin.register(ProfessionalTrade)
class ProfessionalTradeAdmin(admin.ModelAdmin):
    list_display = ('professional', 'trade_license_number', 'trade_license_expiry_date')
    search_fields = ('trade_license_number',)
    list_filter = ('trade_license_expiry_date',)


@admin.register(ProfessionalInventory)
class ProfessionalInventoryAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'quantity', 'unit', 'professional', 'date_added')
    search_fields = ('item_name', 'professional__user__email')
    list_filter = ('date_added',)


@admin.register(ProfessionalTask)
class ProfessionalTaskAdmin(admin.ModelAdmin):
    list_display = ('worker_name', 'professional', 'start_date', 'start_time', 'end_time', 'status', 'price_per_hour')
    search_fields = ('worker_name', 'professional__user__email')
    list_filter = ('status', 'start_date')


@admin.register(ProfessionalRating)
class ProfessionalRatingAdmin(admin.ModelAdmin):
    list_display = ('professional', 'user', 'rating', 'created_at')
    search_fields = ('professional__user__email', 'user__email')
    list_filter = ('rating', 'created_at')


@admin.register(ProfessionalPayout)
class ProfessionalPayoutAdmin(admin.ModelAdmin):
    list_display = ('professional', 'payouts_enabled', 'onboarding_complete', 'last_payout_status', 'last_payout_date')
    search_fields = ('professional__user__email', 'stripe_account_id')
    list_filter = ('payouts_enabled', 'onboarding_complete', 'last_payout_date')
    readonly_fields = ('created_at', 'updated_at')
