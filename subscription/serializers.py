from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'stripe_plan_id', 'price', 'description']

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = UserSubscription
        fields = ['id', 'user', 'plan', 'stripe_subscription_id', 'active', 'start_date', 'end_date', 'trial_end']
        read_only_fields = ['user', 'stripe_subscription_id', 'active', 'start_date', 'end_date', 'trial_end']