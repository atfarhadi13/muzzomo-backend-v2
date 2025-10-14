# professional/admin.py
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Professional,
    ProfessionalService,
    ProfessionalInsurance,
    ProfessionalTrade,
    ProfessionalRating,
    ProfessionalPayout,
    BankInfo,
)


class ProfessionalServiceInline(admin.TabularInline):
    model = ProfessionalService
    extra = 0
    autocomplete_fields = ("service",)
    verbose_name_plural = "Services"


class ProfessionalTradeInline(admin.TabularInline):
    model = ProfessionalTrade
    extra = 0


class ProfessionalInsuranceInline(admin.StackedInline):
    model = ProfessionalInsurance
    can_delete = True
    extra = 0


class HasInsuranceFilter(admin.SimpleListFilter):
    title = "has insurance"
    parameter_name = "has_insurance"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        v = self.value()
        if v == "yes":
            return queryset.filter(insurance__isnull=False)
        if v == "no":
            return queryset.filter(insurance__isnull=True)
        return queryset


@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = (
        "user_email",
        "license_number",
        "verification_status",
        "is_verified",
        "registration_completion_display",
        "rating_avg_display",
        "rating_count",
    )
    list_filter = ("verification_status", "is_verified", HasInsuranceFilter)
    search_fields = ("user__email", "license_number")
    list_select_related = ("user",)
    readonly_fields = ("rating_avg_display", "registration_completion_display")
    ordering = ("user__email",)
    inlines = [ProfessionalInsuranceInline, ProfessionalServiceInline, ProfessionalTradeInline]
    actions = ("approve_selected", "reject_selected", "mark_pending")

    @admin.display(description="User Email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Completion")
    def registration_completion_display(self, obj):
        pct = obj.registration_completion
        return format_html('<span style="font-weight:600;">{}%</span>', pct)

    @admin.display(description="Avg Rating")
    def rating_avg_display(self, obj):
        return "-" if obj.rating_avg is None else f"{obj.rating_avg:.2f} ⭐"

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            ro.extend(["verification_status", "is_verified"])
        return ro

    @admin.action(description="Approve selected professionals")
    def approve_selected(self, request, queryset):
        for p in queryset.select_for_update():
            p.verification_status = Professional.VerificationStatus.APPROVED
            p.is_verified = True
            p.save(update_fields=["verification_status", "is_verified"])

    @admin.action(description="Reject selected professionals")
    def reject_selected(self, request, queryset):
        for p in queryset.select_for_update():
            p.verification_status = Professional.VerificationStatus.REJECTED
            p.is_verified = False
            p.save(update_fields=["verification_status", "is_verified"])

    @admin.action(description="Mark selected as pending")
    def mark_pending(self, request, queryset):
        for p in queryset.select_for_update():
            p.verification_status = Professional.VerificationStatus.PENDING
            p.is_verified = False
            p.save(update_fields=["verification_status", "is_verified"])


@admin.register(ProfessionalService)
class ProfessionalServiceAdmin(admin.ModelAdmin):
    list_display = ("professional_email", "service_title")
    search_fields = ("professional__user__email", "service__title")
    list_select_related = ("professional__user", "service")
    autocomplete_fields = ("professional", "service")
    ordering = ("professional__user__email", "service__title")

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email

    @admin.display(description="Service")
    def service_title(self, obj):
        return obj.service.title


@admin.register(ProfessionalInsurance)
class ProfessionalInsuranceAdmin(admin.ModelAdmin):
    list_display = ("professional_email", "insurance_provider_name", "insurance_policy_number", "insurance_expiry_date")
    search_fields = ("professional__user__email", "insurance_provider_name", "insurance_policy_number")
    list_filter = ("insurance_expiry_date",)
    list_select_related = ("professional__user",)
    autocomplete_fields = ("professional",)
    ordering = ("-insurance_expiry_date",)

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email


@admin.register(ProfessionalTrade)
class ProfessionalTradeAdmin(admin.ModelAdmin):
    list_display = ("professional_email", "trade_license_number", "trade_license_expiry_date")
    search_fields = ("professional__user__email", "trade_license_number")
    list_filter = ("trade_license_expiry_date",)
    list_select_related = ("professional__user",)
    autocomplete_fields = ("professional",)
    ordering = ("-trade_license_expiry_date", "trade_license_number")

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email


@admin.register(ProfessionalRating)
class ProfessionalRatingAdmin(admin.ModelAdmin):
    list_display = ("professional_email", "user_email", "rating", "created_at")
    search_fields = ("professional__user__email", "user__email")
    list_filter = ("rating", "created_at")
    list_select_related = ("professional__user", "user")
    ordering = ("-created_at",)

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email

    @admin.display(description="User")
    def user_email(self, obj):
        return obj.user.email


@admin.register(ProfessionalPayout)
class ProfessionalPayoutAdmin(admin.ModelAdmin):
    list_display = ("professional_email", "payouts_enabled", "onboarding_complete", "last_payout_status", "last_payout_date")
    search_fields = ("professional__user__email", "stripe_account_id")
    list_filter = ("payouts_enabled", "onboarding_complete", "last_payout_date")
    list_select_related = ("professional__user",)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("professional",)
    ordering = ("-updated_at",)

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email


@admin.register(BankInfo)
class BankInfoAdmin(admin.ModelAdmin):
    list_display = (
        "professional_email",
        "institution_name",
        "institution_number",
        "transit_number",
        "account_last4",
        "updated_at",
    )
    list_select_related = ("professional__user",)
    list_filter = ("institution_name",)
    search_fields = (
        "professional__user__email",
        "institution_name",
        "institution_number",
        "transit_number",
        "account_number",
    )
    readonly_fields = ("masked_account_number", "account_last4", "created_at", "updated_at")
    autocomplete_fields = ("professional",)
    ordering = ("-updated_at",)

    @admin.display(description="Professional")
    def professional_email(self, obj):
        return obj.professional.user.email
