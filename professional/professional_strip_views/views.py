import os

import stripe

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from professional.models import Professional, ProfessionalPayout

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreateStripeConnectAccount(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        redirect_uri = request.build_absolute_uri("/api/professional/stripe/callback/")
        stripe_url = (
            f"https://connect.stripe.com/express/oauth/authorize?"
            f"client_id={os.getenv('STRIPE_CLIENT_ID')}&"
            f"state={user.id}&"
            f"redirect_uri={redirect_uri}&"
            "suggested_capabilities[]=transfers"
        )
        return Response({"url": stripe_url})

class StripeConnectCallback(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code = request.query_params.get("code")
        user_id = request.query_params.get("state")

        if not code:
            return Response({"error": "No code provided"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            response = stripe.OAuth.token(grant_type="authorization_code", code=code)
            stripe_account_id = response["stripe_user_id"]
            professional = Professional.objects.get(user_id=user_id)
            payout, created = ProfessionalPayout.objects.get_or_create(professional=professional)
            payout.stripe_account_id = stripe_account_id
            payout.onboarding_complete = True
            payout.save()

            return Response({"detail": "Stripe account connected successfully."})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
