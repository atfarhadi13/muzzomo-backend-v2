from datetime import datetime
import stripe

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

from .models import SubscriptionPlan, UserSubscription
from .serializers import SubscriptionPlanSerializer, UserSubscriptionSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY
User = get_user_model()


def _get_or_create_customer(user: User):
    if getattr(user, "stripe_customer_id", None):
        try:
            stripe.Customer.retrieve(user.stripe_customer_id)
            return user.stripe_customer_id
        except stripe.error.InvalidRequestError:
            pass
    customer = stripe.Customer.create(email=user.email or None)
    User.objects.filter(pk=user.pk).update(stripe_customer_id=customer["id"])
    return customer["id"]


class SubscriptionSheetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get("plan_id")
        if not plan_id:
            return Response({"detail": "plan_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        plan = get_object_or_404(SubscriptionPlan, id=plan_id)

        try:
            customer_id = _get_or_create_customer(request.user)
            ephemeral_key = stripe.EphemeralKey.create(
                customer=customer_id,
                stripe_version="2022-11-15",
            )
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan.stripe_plan_id}],
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                expand=["latest_invoice.payment_intent"],
            )
            pi = subscription["latest_invoice"]["payment_intent"]
            client_secret = pi["client_secret"]

            sub_obj, _ = UserSubscription.objects.get_or_create(
                user=request.user,
                defaults={
                    "plan": plan,
                    "stripe_subscription_id": subscription["id"],
                    "active": False,
                    "start_date": timezone.now(),
                    "end_date": None,
                    "trial_end": None,
                },
            )
            if sub_obj.plan_id != plan.id or sub_obj.stripe_subscription_id != subscription["id"]:
                sub_obj.plan = plan
                sub_obj.stripe_subscription_id = subscription["id"]
                sub_obj.active = False
                sub_obj.save(update_fields=["plan", "stripe_subscription_id", "active"])

            return Response(
                {
                    "paymentIntentClientSecret": client_secret,
                    "ephemeralKeySecret": ephemeral_key.secret,
                    "customer": customer_id,
                    "publishableKey": settings.STRIPE_PUBLIC_KEY,
                    "stripe_subscription_id": subscription["id"],
                    "plan": {
                        "id": plan.id,
                        "name": plan.name,
                        "price": str(plan.price),
                        "stripe_price_id": plan.stripe_plan_id,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except stripe.error.StripeError as e:
            return Response({"detail": "Stripe error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": "Unexpected error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionSuccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub_id = request.data.get("stripe_subscription_id")
        if not sub_id:
            return Response({"detail": "stripe_subscription_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            subscription = stripe.Subscription.retrieve(sub_id, expand=["latest_invoice.payment_intent"])
        except stripe.error.StripeError as e:
            return Response({"detail": "Stripe error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if subscription["customer"] != (request.user.stripe_customer_id or ""):
            return Response({"detail": "Subscription does not belong to current user."}, status=status.HTTP_403_FORBIDDEN)

        status_str = subscription["status"]
        pi = subscription["latest_invoice"]["payment_intent"] if subscription.get("latest_invoice") else None
        if status_str not in ("active", "trialing"):
            pi_status = (pi or {}).get("status")
            return Response(
                {"detail": "Subscription not active yet.", "subscription_status": status_str, "payment_intent_status": pi_status},
                status=status.HTTP_400_BAD_REQUEST,
            )

        items = subscription.get("items", {}).get("data", [])
        price_id = items[0]["price"]["id"] if items else None
        plan = SubscriptionPlan.objects.filter(stripe_plan_id=price_id).first()

        sub_obj, _ = UserSubscription.objects.get_or_create(user=request.user)
        sub_obj.plan = plan
        sub_obj.stripe_subscription_id = subscription["id"]
        sub_obj.active = True

        cps = subscription.get("current_period_start")
        cpe = subscription.get("current_period_end")
        trl = subscription.get("trial_end")

        sub_obj.start_date = timezone.make_aware(datetime.fromtimestamp(cps)) if cps else timezone.now()
        sub_obj.end_date = timezone.make_aware(datetime.fromtimestamp(cpe)) if cpe else None
        sub_obj.trial_end = timezone.make_aware(datetime.fromtimestamp(trl)) if trl else None
        sub_obj.save()

        return Response(
            {
                "message": "Subscription activated.",
                "stripe_subscription_id": subscription["id"],
                "status": status_str,
                "plan": {
                    "id": plan.id if plan else None,
                    "name": plan.name if plan else None,
                    "price": str(plan.price) if plan else None,
                },
                "start_date": sub_obj.start_date.isoformat(),
                "end_date": sub_obj.end_date.isoformat() if sub_obj.end_date else None,
                "trial_end": sub_obj.trial_end.isoformat() if sub_obj.trial_end else None,
                "active": sub_obj.active,
            },
            status=status.HTTP_200_OK,
        )


class ChangePlanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_plan_id = request.data.get("plan_id")
        if not new_plan_id:
            return Response({"detail": "plan_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            plan = SubscriptionPlan.objects.get(id=new_plan_id)
        except SubscriptionPlan.DoesNotExist:
            return Response({"detail": "Invalid subscription plan."}, status=status.HTTP_404_NOT_FOUND)

        us = getattr(request.user, "professional_subscription", None)
        if not us or not us.stripe_subscription_id:
            return Response({"detail": "No active subscription to change."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sub = stripe.Subscription.retrieve(us.stripe_subscription_id)
            item_id = sub["items"]["data"][0]["id"]
            stripe.Subscription.modify(
                us.stripe_subscription_id,
                items=[{"id": item_id, "price": plan.stripe_plan_id}],
                proration_behavior="create_prorations",
            )
            return Response({"message": "Plan change requested."}, status=status.HTTP_200_OK)
        except stripe.error.StripeError as e:
            return Response({"detail": "Stripe error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CancelAtPeriodEndView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        us = getattr(request.user, "professional_subscription", None)
        if not us or not us.stripe_subscription_id:
            return Response({"detail": "No active subscription to cancel."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            stripe.Subscription.modify(us.stripe_subscription_id, cancel_at_period_end=True)
            return Response({"message": "Will cancel at period end."}, status=status.HTTP_200_OK)
        except stripe.error.StripeError as e:
            return Response({"detail": "Stripe error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CancelNowView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        us = getattr(request.user, "professional_subscription", None)
        if not us or not us.stripe_subscription_id:
            return Response({"detail": "No active subscription to cancel."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            stripe.Subscription.delete(us.stripe_subscription_id)
            UserSubscription.objects.filter(user=request.user).update(active=False, end_date=timezone.now())
            return Response({"message": "Subscription canceled immediately."}, status=status.HTTP_200_OK)
        except stripe.error.StripeError as e:
            return Response({"detail": "Stripe error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        us = UserSubscription.objects.filter(user=request.user).select_related("plan").first()
        if not us:
            return Response({"detail": "No subscription found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserSubscriptionSerializer(us).data, status=status.HTTP_200_OK)


class ListUserSubscriptionsView(ListAPIView):
    queryset = UserSubscription.objects.select_related("user", "plan").all().order_by("-start_date")
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAdminUser]


class ListPlansView(ListAPIView):
    queryset = SubscriptionPlan.objects.all().order_by("price")
    serializer_class = SubscriptionPlanSerializer
    permission_classes = []
