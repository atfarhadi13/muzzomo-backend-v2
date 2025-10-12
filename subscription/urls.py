from django.urls import path
from .views import (
    SubscriptionSheetView,
    SubscriptionSuccessView,
    ChangePlanView,
    CancelAtPeriodEndView,
    CancelNowView,
    MySubscriptionView,
    ListUserSubscriptionsView,
    ListPlansView,
)

app_name = "subscriptions"

urlpatterns = [
    path("plans/", ListPlansView.as_view(), name="list-plans"),
    path("subscribe/", SubscriptionSheetView.as_view(), name="subscribe"),
    path("subscribe/success/", SubscriptionSuccessView.as_view(), name="subscribe-success"),
    path("change-plan/", ChangePlanView.as_view(), name="change-plan"),
    path("cancel/at-period-end/", CancelAtPeriodEndView.as_view(), name="cancel-at-period-end"),
    path("cancel/now/", CancelNowView.as_view(), name="cancel-now"),
    path("me/", MySubscriptionView.as_view(), name="my-subscription"),
    path("all/", ListUserSubscriptionsView.as_view(), name="list-user-subscriptions"),
]
