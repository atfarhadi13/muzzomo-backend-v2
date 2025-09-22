from django.contrib import admin, messages
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import (
    Job, JobAttachment, JobServiceType, JobRate,
    JobUnitUpdateRequest, JobOffer
)


# ------------ Inlines ------------

class JobAttachmentInline(admin.TabularInline):
    model = JobAttachment
    extra = 0


class JobServiceTypeInline(admin.TabularInline):
    model = JobServiceType
    extra = 0
    autocomplete_fields = ['service_type']


# ------------ Job ------------

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'user_email', 'professional_email', 'service',
        'quantity', 'total_price', 'status', 'is_paid', 'created_at',
    )
    list_filter = ('status', 'is_paid', 'service', 'created_at')
    search_fields = (
        'title', 'user__email', 'professional__user__email',
        'address__street_name', 'address__city_name',
    )
    readonly_fields = (
        'submit_date', 'created_at', 'updated_at', 'computed_total_price',
    )
    autocomplete_fields = ['user', 'professional', 'service', 'address']
    date_hierarchy = 'created_at'
    inlines = [JobAttachmentInline, JobServiceTypeInline]
    list_select_related = ('user', 'professional__user', 'service', 'address')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('service_types')

    def user_email(self, obj):
        return getattr(obj.user, 'email', None)
    user_email.short_description = 'User'

    def professional_email(self, obj):
        return getattr(getattr(obj.professional, 'user', None), 'email', None)
    professional_email.short_description = 'Professional'


# ------------ JobAttachment (optional standalone) ------------

@admin.register(JobAttachment)
class JobAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'attachment', 'uploaded_at')
    search_fields = ('job__title', 'job__user__email')
    list_filter = ('uploaded_at',)
    autocomplete_fields = ['job']
    date_hierarchy = 'uploaded_at'
    list_select_related = ('job',)


# ------------ JobServiceType (optional standalone) ------------

@admin.register(JobServiceType)
class JobServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('job', 'service_type')
    search_fields = ('job__title', 'service_type__title')
    autocomplete_fields = ['job', 'service_type']
    list_select_related = ('job', 'service_type')


# ------------ JobRate ------------

@admin.register(JobRate)
class JobRateAdmin(admin.ModelAdmin):
    list_display = ('job', 'rate', 'rated_at')
    list_filter = ('rate', 'rated_at')
    search_fields = ('job__title', 'job__user__email', 'job__professional__user__email')
    autocomplete_fields = ['job']
    date_hierarchy = 'rated_at'
    list_select_related = ('job',)


# ------------ JobUnitUpdateRequest ------------

@admin.register(JobUnitUpdateRequest)
class JobUnitUpdateRequestAdmin(admin.ModelAdmin):
    list_display = ('job', 'professional', 'new_unit_qty', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job__title', 'professional__user__email')
    autocomplete_fields = ['job', 'professional']
    date_hierarchy = 'created_at'
    list_select_related = ('job', 'professional', 'professional__user')
    actions = ['accept_selected_requests']

    @admin.action(description='Accept selected unit update requests (only pending)')
    def accept_selected_requests(self, request, queryset):
        processed = 0
        errors = 0
        for req in queryset:
            try:
                with transaction.atomic():
                    req.accept()
                processed += 1
            except ValidationError as e:
                errors += 1
                messages.error(request, f'#{req.id}: {e.messages[0]}')
        if processed:
            messages.success(request, f'Accepted {processed} request(s).')
        if errors and not processed:
            messages.warning(request, 'No requests accepted.')


# ------------ JobOffer ------------

@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = ('job', 'professional', 'status', 'distance_km', 'created_at', 'accepted_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job__title', 'professional__user__email')
    autocomplete_fields = ['job', 'professional']
    date_hierarchy = 'created_at'
    list_select_related = ('job', 'professional', 'professional__user')
    actions = ['accept_selected_offers']

    @admin.action(description='Accept selected offers (only sent/viewed)')
    def accept_selected_offers(self, request, queryset):
        processed = 0
        errors = 0
        for offer in queryset:
            try:
                with transaction.atomic():
                    offer.accept()
                processed += 1
            except ValidationError as e:
                errors += 1
                messages.error(request, f'Offer #{offer.id}: {e.messages[0]}')
        if processed:
            messages.success(request, f'Accepted {processed} offer(s).')
        if errors and not processed:
            messages.warning(request, 'No offers accepted.')
