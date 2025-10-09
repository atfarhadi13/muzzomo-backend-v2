from datetime import datetime, timezone

import stripe

from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import SubscriptionPlan, UserSubscription
from .serializers import UserSubscriptionSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY

class SubscriptionSheetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id')

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {"detail": "Invalid subscription plan."},
                status=status.HTTP_404_NOT_FOUND
            )

        user = request.user

        if not hasattr(user, 'stripe_customer_id') or not user.stripe_customer_id:
            customer = stripe.Customer.create(email=user.email)
            user.stripe_customer_id = customer.id
            user.save()
        else:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)

        try:
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{"price": plan.stripe_plan_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )

            payment_intent = subscription.latest_invoice.payment_intent

            return Response({
                "client_secret": payment_intent.client_secret,
                "subscription_id": subscription.id,
                "publishableKey": settings.STRIPE_PUBLIC_KEY,
                "customer_id": customer.id,
                "plan_name": plan.name,
                "plan_price": str(plan.price),
            }, status=status.HTTP_200_OK)

        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionSuccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription_id = request.data.get('subscription_id')

        if not subscription_id:
            return Response(
                {"error": "subscription_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        start_date = datetime.fromtimestamp(
            stripe_subscription.current_period_start, tz=timezone.utc
        )
        end_date = datetime.fromtimestamp(
            stripe_subscription.current_period_end, tz=timezone.utc
        )

        trial_end = end_date

        stripe_price_id = stripe_subscription['items']['data'][0]['price']['id']
        plan = get_object_or_404(SubscriptionPlan, stripe_plan_id=stripe_price_id)

        user_subscription, created = UserSubscription.objects.update_or_create(
            user=user,
            defaults={
                'plan': plan,
                'stripe_subscription_id': subscription_id,
                'active': True,
                'start_date': start_date,
                'end_date': end_date,
                'trial_end': trial_end
            }
        )

        serializer = UserSubscriptionSerializer(user_subscription)

        return Response({
            "message": "Subscription activated successfully.",
            "subscription": serializer.data
        }, status=status.HTTP_200_OK)