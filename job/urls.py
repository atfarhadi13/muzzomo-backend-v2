from django.urls import path, include

from rest_framework.routers import DefaultRouter

from .views import (
    JobCreateView,
    JobUpdateView,
    JobDeleteView,
    JobListView,
    JobRetrieveView,
    PaymentSheetView,
    PaymentSuccess,
    JobRateViewSet,
    JobUnitUpdateRequestCreateView,
    JobUnitUpdateRequestAcceptView,
    JobUnitUpdateRequestRejectView,
    JobOfferListView,
    JobOfferAcceptView,
    ProfessionalJobListView,
    ProfessionalJobRetrieveView,
    JobAttachmentListView,
    JobServiceTypeListView,
    JobAddressRetrieveView,
    JobUnitUpdateRequestListForOwnerView,
    JobUnitUpdateRequestListForProfessionalView
)

router = DefaultRouter()
router.register(r"job-rates", JobRateViewSet, basename="job-rate")

urlpatterns = [
    path("jobs/", JobCreateView.as_view(), name="job-create"),
    path("jobs/list/", JobListView.as_view(), name="job-list"),
    path("jobs/<int:pk>/", JobRetrieveView.as_view(), name="job-detail"),
    path("jobs/<int:pk>/update/", JobUpdateView.as_view(), name="job-update"),
    path("jobs/<int:pk>/delete/", JobDeleteView.as_view(), name="job-delete"),

    path("payment-sheet/", PaymentSheetView.as_view(), name="payment-sheet"),
    path("payment-success/", PaymentSuccess.as_view(), name="payment-success"),

    path("jobs/unit-update-requests/", JobUnitUpdateRequestCreateView.as_view(), name="job-unit-update-request-create"),
    path("jobs/unit-update-requests/owner/", JobUnitUpdateRequestListForOwnerView.as_view(), name="job-unit-update-requests-owner"),
    path("jobs/unit-update-requests/pro/", JobUnitUpdateRequestListForProfessionalView.as_view(), name="job-unit-update-requests-pro"),
    path("jobs/unit-update-requests/<int:pk>/accept/", JobUnitUpdateRequestAcceptView.as_view(), name="job-unit-update-request-accept"),
    path("jobs/unit-update-requests/<int:pk>/reject/", JobUnitUpdateRequestRejectView.as_view(), name="job-unit-update-request-reject"),

    path("offers/", JobOfferListView.as_view(), name="job-offer-list"),
    path("offers/<int:pk>/accept/", JobOfferAcceptView.as_view(), name="job-offer-accept"),

    path("pro/jobs/list/", ProfessionalJobListView.as_view(), name="pro-job-list"),
    path("pro/jobs/<int:pk>/", ProfessionalJobRetrieveView.as_view(), name="pro-job-detail"),

    path("jobs/<int:pk>/attachments/", JobAttachmentListView.as_view(), name="job-attachments"),
    path("jobs/<int:pk>/service-types/", JobServiceTypeListView.as_view(), name="job-service-types"),
    path("jobs/<int:pk>/address/", JobAddressRetrieveView.as_view(), name="job-address"),

    path("", include(router.urls)),
]
