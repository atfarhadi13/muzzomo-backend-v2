from django.urls import path, include

from rest_framework.routers import DefaultRouter

from .views import ( 
    ProfessionalViewSet, 
    ProfessionalServiceViewSet, 
    ProfessionalInsuranceViewSet, 
    ProfessionalTradeViewSet,
    ProfessionalInventoryViewSet, 
    ProfessionalTaskViewSet,
    ProfessionalRatingViewSet, 
    ProfessionalPayoutViewSet, 
    BankInfoViewSet
)

router = DefaultRouter()
router.register("professionals", ProfessionalViewSet, basename="professional")
router.register("professional-services", ProfessionalServiceViewSet, basename="professional-service")
router.register("professional-insurance", ProfessionalInsuranceViewSet, basename="professional-insurance")
router.register("professional-trades", ProfessionalTradeViewSet, basename="professional-trade")
router.register("professional-inventories", ProfessionalInventoryViewSet, basename="professional-inventory")
router.register("professional-tasks", ProfessionalTaskViewSet, basename="professional-task")
router.register("professional-ratings", ProfessionalRatingViewSet, basename="professional-rating")
router.register("professional-payouts", ProfessionalPayoutViewSet, basename="professional-payout")
router.register("bank-info", BankInfoViewSet, basename="bank-info")

urlpatterns = [
    path("api/", include(router.urls)),
]

