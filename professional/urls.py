from django.urls import path, include

from rest_framework.routers import DefaultRouter

from .views import ( ProfessionalViewSet, ProfessionalServiceViewSet, 
                    ProfessionalInsuranceViewSet, ProfessionalTradeViewSet,
                    ProfessionalInventoryViewSet, ProfessionalTaskViewSet,
                    ProfessionalRatingViewSet, ProfessionalPayoutViewSet
                    )

from .professional_strip_views.views import CreateStripeConnectAccount, StripeConnectCallback

router = DefaultRouter()
router.register("professionals", ProfessionalViewSet, basename="professional")
router.register("professional-services", ProfessionalServiceViewSet, basename="professional-service")
router.register("professional-insurance", ProfessionalInsuranceViewSet, basename="professional-insurance")
router.register("professional-trades", ProfessionalTradeViewSet, basename="professional-trade")
router.register("professional-inventories", ProfessionalInventoryViewSet, basename="professional-inventory")
router.register("professional-tasks", ProfessionalTaskViewSet, basename="professional-task")
router.register("professional-ratings", ProfessionalRatingViewSet, basename="professional-rating")
router.register("professional-payouts", ProfessionalPayoutViewSet, basename="professional-payout")

urlpatterns = [
    path("stripe/connect/", CreateStripeConnectAccount.as_view(), name="stripe-connect"),
    path("stripe/callback/", StripeConnectCallback.as_view(), name="stripe-callback"),
    
    path("api/", include(router.urls)),
]

