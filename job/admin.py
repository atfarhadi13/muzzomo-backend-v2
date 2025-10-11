from django.contrib import admin, messages
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .models import (
    Job, JobAttachment, JobServiceType, JobRate,
    JobUnitUpdateRequest, JobOffer
)


# ------------------ Inlines ------------------

class JobAttachmentInline(admin.TabularInline):
    model = JobAttachment
    extra = 0
    readonly_fields = ('attachment_filename', 'uploaded_at')

    def attachment_filename(self, obj):
        if obj.attachment:
            return obj.attachment.name.split('/')[-1]
        return "-"
    attachment_filename.short_description = "Attachment"


class JobServiceTypeInline(admin.TabularInline):
    model = JobServiceType
    extra = 0
    autocomplete_fields = ['service_type']
    readonly_fields = ('service_type',)


# ------------------ Job ------------------

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
        'paid_amount', 'stripe_session_id', 'total_price'
    )
    autocomplete_fields = ['user', 'professional', 'service', 'address']
    date_hierarchy = 'created_at'
    inlines = [JobAttachmentInline, JobServiceTypeInline]
    list_select_related = ('user', 'professional__user', 'service', 'address')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('service_types')

    def user_email(self, obj):
        email = getattr(obj.user, 'email', None)
        if email:
            return '***@' + email.split('@')[1]
        return None
    user_email.short_description = 'User'

    def professional_email(self, obj):
        email = getattr(getattr(obj.professional, 'user', None), 'email', None)
        if email:
            return '***@' + email.split('@')[1]
        return None
    professional_email.short_description = 'Professional'


# ------------------ JobAttachment ------------------

@admin.register(JobAttachment)
class JobAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'attachment_filename', 'uploaded_at')
    search_fields = ('job__title', 'job__user__email')
    list_filter = ('uploaded_at',)
    autocomplete_fields = ['job']
    date_hierarchy = 'uploaded_at'
    list_select_related = ('job',)

    def attachment_filename(self, obj):
        if obj.attachment:
            return obj.attachment.name.split('/')[-1]
        return "-"
    attachment_filename.short_description = "Attachment"


# ------------------ JobServiceType ------------------

@admin.register(JobServiceType)
class JobServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('job', 'service_type')
    search_fields = ('job__title', 'service_type__title')
    autocomplete_fields = ['job', 'service_type']
    readonly_fields = ('service_type',)
    list_select_related = ('job', 'service_type')


# ------------------ JobRate ------------------

@admin.register(JobRate)
class JobRateAdmin(admin.ModelAdmin):
    list_display = ('job', 'rate', 'rated_at')
    list_filter = ('rate', 'rated_at')
    search_fields = ('job__title', 'job__user__email', 'job__professional__user__email')
    autocomplete_fields = ['job']
    date_hierarchy = 'rated_at'
    list_select_related = ('job',)
    readonly_fields = ('rated_at',)


# ------------------ JobUnitUpdateRequest ------------------

@admin.register(JobUnitUpdateRequest)
class JobUnitUpdateRequestAdmin(admin.ModelAdmin):
    list_display = ('job', 'professional', 'new_unit_qty', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job__title', 'professional__user__email')
    autocomplete_fields = ['job', 'professional']
    date_hierarchy = 'created_at'
    list_select_related = ('job', 'professional', 'professional__user')
    readonly_fields = ('created_at', 'updated_at')
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


# ------------------ JobOffer ------------------

@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = ('job', 'professional', 'status', 'distance_km', 'created_at', 'accepted_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job__title', 'professional__user__email')
    autocomplete_fields = ['job', 'professional']
    date_hierarchy = 'created_at'
    list_select_related = ('job', 'professional', 'professional__user')
    readonly_fields = ('created_at', 'updated_at', 'accepted_at')
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
