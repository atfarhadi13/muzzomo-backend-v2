from datetime import timedelta

from django.utils import timezone
from django.contrib.auth import get_user_model, password_validation
from django.core.files.storage import default_storage
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers

from .models import OneTimeCode
from .services.otp_utils import can_resend, issue_otp
from .services.email_utils import send_otp_email
from .utils.tokens import blacklist_user_tokens

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    def validate_email(self, value):
        email = value.lower()
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if existing.is_verified:
                raise serializers.ValidationError({
                    "detail": "This email is already registered and verified. Please log in.",
                    "reason": "already_verified",
                    "next_action": "login"
                })
            raise serializers.ValidationError({
                "detail": "An account with this email already exists but is not verified.",
                "reason": "unverified_exists",
                "next_action": "verify_email"
            })
        return email

    def validate(self, attrs):
        password_validation.validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            is_verified=False,
        )


class VerifyEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=10, trim_whitespace=True)

    default_error_messages = {
        "no_user": "We couldn't find an account with this email.",
        "no_code": "No verification code found. Request a new code.",
        "expired": "Your code has expired. Request a new code.",
        "used": "This code was already used. Request a new code.",
        "invalid": "The code you entered is incorrect.",
    }

    def validate(self, attrs):
        email = attrs["email"].lower()
        raw_code = attrs["code"].strip()

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                "detail": self.default_error_messages["no_user"],
                "reason": "no_user",
                "email": email,
            })

        if user.is_verified:
            attrs["user"] = user
            attrs["already_verified"] = True
            return attrs

        code_obj = (
            OneTimeCode.objects
            .filter(user=user, purpose=OneTimeCode.PURPOSE_LOGIN)
            .order_by("-created_at")
            .first()
        )
        if not code_obj:
            allow_resend = can_resend(user.id, OneTimeCode.PURPOSE_LOGIN, limit=1, window=60)
            raise serializers.ValidationError({
                "detail": self.default_error_messages["no_code"],
                "reason": "no_code",
                "email": user.email,
                "next_action": "resend_code",
                "resend_allowed": allow_resend,
            })
        if code_obj.is_used:
            allow_resend = can_resend(user.id, OneTimeCode.PURPOSE_LOGIN, limit=1, window=60)
            raise serializers.ValidationError({
                "detail": self.default_error_messages["used"],
                "reason": "used",
                "email": user.email,
                "next_action": "resend_code",
                "resend_allowed": allow_resend,
            })
        if code_obj.is_expired:
            allow_resend = can_resend(user.id, OneTimeCode.PURPOSE_LOGIN, limit=1, window=60)
            raise serializers.ValidationError({
                "detail": self.default_error_messages["expired"],
                "reason": "expired",
                "email": user.email,
                "next_action": "resend_code",
                "resend_allowed": allow_resend,
            })

        ok = OneTimeCode.verify_and_consume(
            user=user, purpose=OneTimeCode.PURPOSE_LOGIN, raw_code=raw_code
        )
        if not ok:
            raise serializers.ValidationError({
                "detail": self.default_error_messages["invalid"],
                "reason": "invalid",
                "email": user.email,
                "next_action": "reenter_or_resend",
            })

        attrs["user"] = user
        attrs["already_verified"] = False
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        if self.validated_data.get("already_verified"):
            return user
        if not user.is_verified:
            user.is_verified = True
            user.is_provider = True
            user.email_verified_at = timezone.now()
            user.save(update_fields=["is_verified", "is_provider", "email_verified_at"])
        return user


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    COOLDOWN_SECONDS = 120

    def validate(self, attrs):
        email = attrs["email"].lower()
        user = User.objects.filter(email__iexact=email).first()
        attrs["user"] = user
        attrs["already_verified"] = bool(user and user.is_verified)
        if not user or attrs["already_verified"]:
            return attrs
        last = (
            OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_LOGIN)
            .order_by("-created_at")
            .first()
        )
        if last:
            elapsed = (timezone.now() - last.created_at).total_seconds()
            remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            if remaining > 0:
                raise serializers.ValidationError(
                    {
                        "detail": f"Please wait {remaining} second(s) before requesting another code.",
                        "reason": "cooldown_active",
                        "seconds_left": remaining,
                        "next_action": "wait_and_retry",
                    }
                )
        return attrs

    def save(self, **kwargs):
        user = self.validated_data.get("user")
        if not user:
            return {"detail": "If an account exists, a new code was sent."}
        if self.validated_data.get("already_verified"):
            return {
                "detail": "Account is already verified. No code sent.",
                "email": user.email,
                "next_action": "login",
            }
        if not can_resend(user.id, OneTimeCode.PURPOSE_LOGIN, limit=1, window=self.COOLDOWN_SECONDS):
            last = (
                OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_LOGIN)
                .order_by("-created_at")
                .first()
            )
            remaining = 0
            if last:
                elapsed = (timezone.now() - last.created_at).total_seconds()
                remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            raise serializers.ValidationError(
                {
                    "detail": "Please wait before requesting another code.",
                    "reason": "rate_limited",
                    "seconds_left": remaining,
                    "next_action": "wait_and_retry",
                }
            )
        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_LOGIN)
        send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="verify")
        return {
            "detail": "Verification code sent.",
            "email": user.email,
            "otp_ttl_seconds": ttl_min * 60,
            "next_action": "verify_email",
        }


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    COOLDOWN_SECONDS = 120
    DAILY_LIMIT = 3

    def validate(self, attrs):
        email = attrs["email"].lower()
        user = User.objects.filter(email__iexact=email).first()
        attrs["user"] = user
        if not user:
            return attrs

        now = timezone.now()
        day_ago = now - timedelta(days=1)
        recent_qs = OneTimeCode.objects.filter(
            user=user, purpose=OneTimeCode.PURPOSE_RESET, created_at__gte=day_ago
        )
        if recent_qs.count() >= self.DAILY_LIMIT:
            first_in_window = recent_qs.order_by("created_at").first()
            remaining = max(0, int(86400 - (now - first_in_window.created_at).total_seconds()))
            raise serializers.ValidationError(
                {
                    "detail": "Daily password reset limit reached. Try again later.",
                    "reason": "daily_limit",
                    "seconds_left": remaining,
                    "next_action": "wait_and_retry",
                }
            )

        last = (
            OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_RESET)
            .order_by("-created_at")
            .first()
        )
        if last:
            elapsed = (now - last.created_at).total_seconds()
            remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            if remaining > 0:
                raise serializers.ValidationError(
                    {
                        "detail": f"Please wait {remaining} second(s) before requesting another reset code.",
                        "reason": "cooldown_active",
                        "seconds_left": remaining,
                        "next_action": "wait_and_retry",
                    }
                )

        return attrs

    def save(self, **kwargs):
        user = self.validated_data.get("user")
        if not user:
            return {"detail": "If an account exists, a reset code was sent."}

        if not can_resend(user.id, OneTimeCode.PURPOSE_RESET, limit=1, window=self.COOLDOWN_SECONDS):
            last = (
                OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_RESET)
                .order_by("-created_at")
                .first()
            )
            remaining = 0
            if last:
                elapsed = (timezone.now() - last.created_at).total_seconds()
                remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            raise serializers.ValidationError(
                {
                    "detail": "Please wait before requesting another reset code.",
                    "reason": "rate_limited",
                    "seconds_left": remaining,
                    "next_action": "wait_and_retry",
                }
            )

        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_RESET)
        send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="reset")
        return {
            "detail": "Password reset code sent.",
            "email": user.email,
            "otp_ttl_seconds": ttl_min * 60,
            "next_action": "confirm_reset",
        }


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=10, trim_whitespace=True)
    new_password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    default_error_messages = {
        "no_user": "No account found for this email.",
        "no_code": "No active reset code found. Request a new code.",
        "expired": "This reset code has expired. Request a new code.",
        "used": "This reset code was already used. Request a new code.",
        "invalid": "The code you entered is incorrect.",
        "too_many_attempts": "Too many incorrect attempts. Request a new code.",
        "same_password": "New password cannot be the same as your current password.",
    }

    def validate(self, attrs):
        email = attrs["email"].lower()
        raw_code = attrs["code"].strip()
        new_password = attrs["new_password"]

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": self.default_error_messages["no_user"], "reason": "no_user"})

        code_obj = (
            OneTimeCode.objects
            .filter(user=user, purpose=OneTimeCode.PURPOSE_RESET)
            .order_by("-created_at")
            .first()
        )
        if not code_obj:
            raise serializers.ValidationError({"detail": self.default_error_messages["no_code"], "reason": "no_code"})
        if code_obj.is_used:
            raise serializers.ValidationError({"detail": self.default_error_messages["used"], "reason": "used"})
        if code_obj.is_expired:
            raise serializers.ValidationError({"detail": self.default_error_messages["expired"], "reason": "expired"})
        if code_obj.verify_attempts >= code_obj.max_attempts:
            raise serializers.ValidationError({"detail": self.default_error_messages["too_many_attempts"], "reason": "too_many_attempts"})

        if user.check_password(new_password):
            raise serializers.ValidationError({"new_password": [self.default_error_messages["same_password"]]})

        password_validation.validate_password(new_password, user=user)

        ok = OneTimeCode.verify_and_consume(
            user=user,
            purpose=OneTimeCode.PURPOSE_RESET,
            raw_code=raw_code
        )
        if not ok:
            raise serializers.ValidationError({"detail": self.default_error_messages["invalid"], "reason": "invalid"})

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        new_password = self.validated_data["new_password"]
        user.set_password(new_password)
        try:
            getattr(user, "token_valid_after")
            user.token_valid_after = timezone.now()
            user.save(update_fields=["password", "token_valid_after"])
        except Exception:
            user.save(update_fields=["password"])
        blacklist_user_tokens(user)
        return user


class PasswordResetResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    COOLDOWN_SECONDS = 120
    DAILY_LIMIT = 3
    SUCCESS_LOCK_SECONDS = 900

    def validate(self, attrs):
        email = attrs["email"].lower()
        user = User.objects.filter(email__iexact=email).first()
        attrs["user"] = user
        if not user:
            return attrs

        now = timezone.now()

        recent_success = (
            OneTimeCode.objects
            .filter(user=user, purpose=OneTimeCode.PURPOSE_RESET, used_at__isnull=False)
            .order_by("-used_at")
            .first()
        )
        if recent_success:
            elapsed = (now - recent_success.used_at).total_seconds()
            remaining = max(0, int(self.SUCCESS_LOCK_SECONDS - elapsed))
            if remaining > 0:
                raise serializers.ValidationError(
                    {
                        "detail": "Password was recently reset. For security, request again later.",
                        "reason": "recently_reset",
                        "seconds_left": remaining,
                        "next_action": "wait_and_retry",
                    }
                )

        active = (
            OneTimeCode.objects.active()
            .filter(user=user, purpose=OneTimeCode.PURPOSE_RESET)
            .order_by("-created_at")
            .first()
        )
        if active:
            remaining = max(0, int((active.expires_at - now).total_seconds()))
            raise serializers.ValidationError(
                {
                    "detail": "A valid reset code already exists.",
                    "reason": "active_code_exists",
                    "seconds_left": remaining,
                    "next_action": "use_existing_code",
                }
            )

        day_ago = now - timedelta(days=1)
        daily_count = OneTimeCode.objects.filter(
            user=user, purpose=OneTimeCode.PURPOSE_RESET, created_at__gte=day_ago
        ).count()
        if daily_count >= self.DAILY_LIMIT:
            first_in_window = (
                OneTimeCode.objects.filter(
                    user=user, purpose=OneTimeCode.PURPOSE_RESET, created_at__gte=day_ago
                )
                .order_by("created_at")
                .first()
            )
            remaining = 0
            if first_in_window:
                remaining = max(0, int(86400 - (now - first_in_window.created_at).total_seconds()))
            raise serializers.ValidationError(
                {
                    "detail": "Daily password reset limit reached. Try again later.",
                    "reason": "daily_limit",
                    "seconds_left": remaining,
                    "next_action": "wait_and_retry",
                }
            )

        last = (
            OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_RESET)
            .order_by("-created_at")
            .first()
        )
        if last:
            elapsed = (now - last.created_at).total_seconds()
            remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            if remaining > 0:
                raise serializers.ValidationError(
                    {
                        "detail": f"Please wait {remaining} second(s) before requesting another reset code.",
                        "reason": "cooldown_active",
                        "seconds_left": remaining,
                        "next_action": "wait_and_retry",
                    }
                )

        return attrs

    def save(self, **kwargs):
        user = self.validated_data.get("user")
        if not user:
            return {"detail": "If an account exists, a reset code was sent."}

        if not can_resend(user.id, OneTimeCode.PURPOSE_RESET, limit=1, window=self.COOLDOWN_SECONDS):
            last = (
                OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_RESET)
                .order_by("-created_at")
                .first()
            )
            remaining = 0
            if last:
                elapsed = (timezone.now() - last.created_at).total_seconds()
                remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            raise serializers.ValidationError(
                {
                    "detail": "Please wait before requesting another reset code.",
                    "reason": "rate_limited",
                    "seconds_left": remaining,
                    "next_action": "wait_and_retry",
                }
            )

        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_RESET)
        send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="reset")
        return {
            "detail": "Password reset code sent.",
            "email": user.email,
            "otp_ttl_seconds": ttl_min * 60,
            "next_action": "confirm_reset",
        }



class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip().lower()
        password = attrs.get("password") or ""
        user = User.objects.filter(email__iexact=email).first()

        if not user:
            raise serializers.ValidationError({"detail": "This email does not exist."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "Account disabled. Contact support."})

        if getattr(user, "is_locked", False):
            delta = (user.locked_until - timezone.now()).total_seconds()
            remaining = max(0, int((delta + 59) // 60))
            raise serializers.ValidationError({
                "detail": f"Account locked. Try again in ~{remaining} minute(s) or unlock your account.",
                "requires_unlock": True,
                "minutes_left": remaining,
                "next_action": "unlock_account",
                "email": user.email,
            })

        if not user.check_password(password):
            if hasattr(user, "register_failed_login"):
                user.register_failed_login(threshold=5, lock_minutes=15)
            raise serializers.ValidationError({"detail": "Email or password is incorrect."})

        if not user.is_verified:
            obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_LOGIN)
            try:
                send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="verify")
            except Exception:
                pass
            raise serializers.ValidationError({
                "detail": "Email not verified. We sent you a new verification code.",
                "requires_verification": True,
                "next_action": "verify_email",
                "email": user.email,
                "otp_ttl_seconds": ttl_min * 60,
            })

        if hasattr(user, "reset_login_failures"):
            user.reset_login_failures()

        data = super().validate({self.username_field: email, "password": password})
        data.update({
            "user": {
                "id": str(user.pk),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_verified": user.is_verified,
                "is_provider": user.is_provider,
                "is_professional": user.is_professional,
            }
        })
        return data


class UnlockConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=10, trim_whitespace=True)

    default_error_messages = {
        "no_user": "No account found for this email.",
        "no_code": "No active unlock code found.",
        "invalid_code": "Invalid or expired unlock code.",
    }

    def validate(self, attrs):
        email = attrs["email"].lower()
        code = attrs["code"].strip()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            self.fail("no_user")
        ok = OneTimeCode.verify_and_consume(
            user=user, purpose=OneTimeCode.PURPOSE_UNLOCK, raw_code=code
        )
        if not ok:
            self.fail("invalid_code")
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.reset_login_failures()
        return {"detail": "Account unlocked."}


class UnlockRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self, **kwargs):
        email = self.validated_data["email"].lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return
        if not can_resend(user.id, OneTimeCode.PURPOSE_UNLOCK, limit=1, window=60):
            raise serializers.ValidationError({"detail": "Please wait before requesting another code."})
        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_UNLOCK)
        send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="unlock")


class EmailUpdateConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=4, max_length=10, trim_whitespace=True)

    default_error_messages = {
        "no_code": "No active email update code found. Please request a new code.",
        "invalid_code": "Invalid or expired code.",
        "email_taken": "This email is already in use. Please request a new code.",
    }

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        raw = attrs["code"].strip()
        with transaction.atomic():
            code_obj = (
                OneTimeCode.objects.select_for_update()
                .active()
                .filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL)
                .order_by("-created_at").first()
            )
            if not code_obj:
                raise serializers.ValidationError({"detail": self.default_error_messages["no_code"], "reason": "no_code"})
            if not check_password(raw, code_obj.code_hash):
                raise serializers.ValidationError({"detail": self.default_error_messages["invalid_code"], "reason": "invalid"})
            new_email = (code_obj.new_email or "").lower()
            if not new_email:
                raise serializers.ValidationError({"detail": "No pending email to apply for this code."})
            if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                raise serializers.ValidationError({"detail": self.default_error_messages["email_taken"], "reason": "email_taken"})
            attrs["code_obj"] = code_obj
            attrs["new_email"] = new_email
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        code_obj: OneTimeCode = self.validated_data["code_obj"]
        new_email: str = self.validated_data["new_email"]
        now = timezone.now()
        with transaction.atomic():
            user.email = new_email
            user.token_valid_after = now
            user.last_email_changed_at = now
            user.save(update_fields=["email", "token_valid_after", "last_email_changed_at"])
            code_obj.used_at = now
            code_obj.save(update_fields=["used_at"])
        return user

class EmailUpdateResendOTPSerializer(serializers.Serializer):
    COOLDOWN_SECONDS = 120
    DAILY_LIMIT = 3
    CHANGE_COOLDOWN = timedelta(days=5)
    SUCCESS_LOCK_SECONDS = 900

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        now = timezone.now()

        pending = (
            OneTimeCode.objects.active()
            .filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL)
            .order_by("-created_at")
            .first()
        )
        if not pending or not pending.new_email:
            raise serializers.ValidationError({
                "detail": "No pending email update to resend.",
                "reason": "no_pending",
                "next_action": "start_email_update",
            })

        if User.objects.filter(email__iexact=pending.new_email).exclude(pk=user.pk).exists():
            raise serializers.ValidationError({
                "detail": "This email is already in use. Start a new email update request.",
                "reason": "email_taken",
                "next_action": "start_email_update",
            })

        last_changed = getattr(user, "last_email_changed_at", None)
        if last_changed and now - last_changed < self.CHANGE_COOLDOWN:
            remaining = self.CHANGE_COOLDOWN - (now - last_changed)
            raise serializers.ValidationError({
                "detail": "Email was changed recently. Try again after the cooldown period.",
                "reason": "email_change_cooldown",
                "seconds_left": int(remaining.total_seconds()),
                "next_action": "wait_and_retry",
            })

        recent_success = (
            OneTimeCode.objects
            .filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL, used_at__isnull=False)
            .order_by("-used_at")
            .first()
        )
        if recent_success:
            elapsed = (now - recent_success.used_at).total_seconds()
            remaining = max(0, int(self.SUCCESS_LOCK_SECONDS - elapsed))
            if remaining > 0:
                raise serializers.ValidationError({
                    "detail": "Email was just updated. Please wait before requesting another code.",
                    "reason": "recently_updated",
                    "seconds_left": remaining,
                    "next_action": "wait_and_retry",
                })

        day_ago = now - timedelta(days=1)
        daily_count = OneTimeCode.objects.filter(
            user=user, purpose=OneTimeCode.PURPOSE_EMAIL, created_at__gte=day_ago
        ).count()
        if daily_count >= self.DAILY_LIMIT:
            first_in_window = (
                OneTimeCode.objects.filter(
                    user=user, purpose=OneTimeCode.PURPOSE_EMAIL, created_at__gte=day_ago
                ).order_by("created_at").first()
            )
            remaining = 0
            if first_in_window:
                remaining = max(0, int(86400 - (now - first_in_window.created_at).total_seconds()))
            raise serializers.ValidationError({
                "detail": "Daily email update limit reached. Try again later.",
                "reason": "daily_limit",
                "seconds_left": remaining,
                "next_action": "wait_and_retry",
            })

        last = (
            OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL)
            .order_by("-created_at").first()
        )
        if last:
            elapsed = (now - last.created_at).total_seconds()
            remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            if remaining > 0:
                raise serializers.ValidationError({
                    "detail": f"Please wait {remaining} second(s) before requesting another code.",
                    "reason": "cooldown_active",
                    "seconds_left": remaining,
                    "next_action": "wait_and_retry",
                })

        attrs["pending"] = pending
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        pending: OneTimeCode = self.validated_data["pending"]

        if not can_resend(user.id, OneTimeCode.PURPOSE_EMAIL, limit=1, window=self.COOLDOWN_SECONDS):
            last = (
                OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL)
                .order_by("-created_at").first()
            )
            remaining = 0
            if last:
                elapsed = (timezone.now() - last.created_at).total_seconds()
                remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            raise serializers.ValidationError({
                "detail": "Please wait before requesting another code.",
                "reason": "rate_limited",
                "seconds_left": remaining,
                "next_action": "wait_and_retry",
            })

        obj, code, ttl_min = issue_otp(
            user=user,
            purpose=OneTimeCode.PURPOSE_EMAIL,
            new_email=pending.new_email
        )
        send_otp_email(to_email=pending.new_email, code=code, ttl_minutes=ttl_min, purpose="email_update")

        return {
            "detail": "Verification code re-sent.",
            "new_email": pending.new_email,
            "otp_ttl_seconds": ttl_min * 60,
            "next_action": "confirm_email_update",
        }


class EmailUpdateRequestSerializer(serializers.Serializer):
    new_email = serializers.EmailField()
    COOLDOWN_SECONDS = 120
    DAILY_LIMIT = 3
    CHANGE_COOLDOWN = timedelta(days=5)

    def validate_new_email(self, value):
        request = self.context["request"]
        new_email = value.lower()
        if request.user.email.lower() == new_email:
            raise serializers.ValidationError("New email must be different from current email.")
        if User.objects.filter(email__iexact=new_email).exists():
            raise serializers.ValidationError("This email is already in use.")
        return new_email

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        now = timezone.now()

        last_changed = getattr(user, "last_email_changed_at", None)
        if last_changed and now - last_changed < self.CHANGE_COOLDOWN:
            remaining = self.CHANGE_COOLDOWN - (now - last_changed)
            raise serializers.ValidationError({
                "detail": "Email was changed recently. Try again after the cooldown period.",
                "reason": "email_change_cooldown",
                "seconds_left": int(remaining.total_seconds()),
                "next_action": "wait_and_retry",
            })

        active = (
            OneTimeCode.objects.active()
            .filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL)
            .order_by("-created_at")
            .first()
        )
        if active:
            remaining = max(0, int((active.expires_at - now).total_seconds()))
            raise serializers.ValidationError({
                "detail": "A valid email update code already exists.",
                "reason": "active_code_exists",
                "seconds_left": remaining,
                "next_action": "use_existing_code",
            })

        day_ago = now - timedelta(days=1)
        daily_count = OneTimeCode.objects.filter(
            user=user, purpose=OneTimeCode.PURPOSE_EMAIL, created_at__gte=day_ago
        ).count()
        if daily_count >= self.DAILY_LIMIT:
            first_in_window = (
                OneTimeCode.objects.filter(
                    user=user, purpose=OneTimeCode.PURPOSE_EMAIL, created_at__gte=day_ago
                ).order_by("created_at").first()
            )
            remaining = 0
            if first_in_window:
                remaining = max(0, int(86400 - (now - first_in_window.created_at).total_seconds()))
            raise serializers.ValidationError({
                "detail": "Daily email update request limit reached. Try again later.",
                "reason": "daily_limit",
                "seconds_left": remaining,
                "next_action": "wait_and_retry",
            })

        last = (
            OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL)
            .order_by("-created_at").first()
        )
        if last:
            elapsed = (now - last.created_at).total_seconds()
            remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            if remaining > 0:
                raise serializers.ValidationError({
                    "detail": f"Please wait {remaining} second(s) before requesting another code.",
                    "reason": "cooldown_active",
                    "seconds_left": remaining,
                    "next_action": "wait_and_retry",
                })

        return attrs

    def save(self, **kwargs):
        request = self.context["request"]
        user = request.user
        new_email = self.validated_data["new_email"]
        if not can_resend(user.id, OneTimeCode.PURPOSE_EMAIL, limit=1, window=self.COOLDOWN_SECONDS):
            last = (
                OneTimeCode.objects.filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL)
                .order_by("-created_at").first()
            )
            remaining = 0
            if last:
                elapsed = (timezone.now() - last.created_at).total_seconds()
                remaining = max(0, int(self.COOLDOWN_SECONDS - elapsed))
            raise serializers.ValidationError({
                "detail": "Please wait before requesting another code.",
                "reason": "rate_limited",
                "seconds_left": remaining,
                "next_action": "wait_and_retry",
            })
        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_EMAIL, new_email=new_email)
        send_otp_email(to_email=new_email, code=code, ttl_minutes=ttl_min, purpose="email_update")
        return {
            "detail": "Verification code sent to new email.",
            "new_email": new_email,
            "otp_ttl_seconds": ttl_min * 60,
            "next_action": "confirm_email_update",
        }



class ProfileImageUpdateSerializer(serializers.Serializer):
    profile_image = serializers.ImageField(required=True)

    def validate_profile_image(self, image):
        max_mb = 5
        if image.size > max_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Max file size is {max_mb}MB.")
        allowed = {"image/jpeg", "image/png", "image/webp"}
        ctype = getattr(image, "content_type", None)
        if ctype and ctype not in allowed:
            raise serializers.ValidationError("Only JPEG, PNG, or WEBP are allowed.")
        return image

    def save(self, **kwargs):
        user = self.context["request"].user
        new_file = self.validated_data["profile_image"]
        old_path = user.profile_image.name if getattr(user, "profile_image", None) else None
        user.profile_image = new_file
        user.save(update_fields=["profile_image"])
        if old_path and old_path != user.profile_image.name:
            if default_storage.exists(old_path):
                default_storage.delete(old_path)
        return user


class ProfileBasicUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=30, trim_whitespace=True)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=30, trim_whitespace=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_phone_number(self, value):
        if value in (None, ""):
            return None
        phone = value.strip()
        user = self.context["request"].user
        field = user._meta.get_field("phone_number")
        field.run_validators(phone)
        return phone

    def _clean_name(self, name):
        if name is None:
            return None
        name = name.strip()
        return name.title()

    def save(self, **kwargs):
        user = self.context["request"].user
        data = self.validated_data
        if "first_name" in data:
            user.first_name = self._clean_name(data.get("first_name", ""))
        if "last_name" in data:
            user.last_name = self._clean_name(data.get("last_name", ""))
        if "phone_number" in data:
            user.phone_number = data["phone_number"] or None
        update_fields = [k for k in ["first_name", "last_name", "phone_number"] if k in data]
        user.save(update_fields=update_fields)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    default_error_messages = {
        "incorrect_current": "Current password is incorrect.",
        "same_as_current": "New password cannot be the same as the current password.",
        "contains_email": "New password cannot contain your email address.",
        "too_soon": "Password was changed recently. Try again after the cooldown period.",
    }

    COOLDOWN = timedelta(days=5)

    def validate(self, attrs):
        user = self.context["request"].user
        current = attrs["current_password"]
        new = attrs["new_password"]

        if not user.check_password(current):
            raise serializers.ValidationError({"current_password": self.default_error_messages["incorrect_current"]})
        if current == new:
            raise serializers.ValidationError({"new_password": self.default_error_messages["same_as_current"]})
        if user.email and user.email.lower() in new.lower():
            raise serializers.ValidationError({"new_password": self.default_error_messages["contains_email"]})

        last_changed = getattr(user, "last_password_changed_at", None)
        if last_changed and timezone.now() - last_changed < self.COOLDOWN:
            remaining = self.COOLDOWN - (timezone.now() - last_changed)
            raise serializers.ValidationError({
                "detail": self.default_error_messages["too_soon"],
                "reason": "cooldown_active",
                "seconds_left": int(remaining.total_seconds()),
                "next_action": "wait_and_retry",
            })

        password_validation.validate_password(new, user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        new = self.validated_data["new_password"]
        now = timezone.now()
        user.set_password(new)
        user.token_valid_after = now
        user.last_password_changed_at = now
        user.save(update_fields=["password", "token_valid_after", "last_password_changed_at"])
        return user
    
class ReactivateAccountRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self, **kwargs):
        email = self.validated_data["email"].lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return {"detail": "If an account exists, a reactivation code was sent."}
        if user.is_active:
            return {"detail": "Account is already active. You can log in.", "next_action": "login"}
        if not can_resend(user.id, OneTimeCode.PURPOSE_REACTIVATE, limit=1, window=60):
            raise serializers.ValidationError({"detail": "Please wait before requesting another code."})
        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_REACTIVATE)
        send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="reactivate")
        return {
            "detail": "Reactivation code sent.",
            "email": user.email,
            "otp_ttl_seconds": ttl_min * 60,
            "next_action": "confirm_reactivation",
        }
    

class ReactivateAccountConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=10, trim_whitespace=True)

    default_error_messages = {
        "no_user": "No account found for this email.",
        "no_code": "No active reactivation code found. Please request a new code.",
        "invalid_code": "Invalid or expired reactivation code.",
    }

    def validate(self, attrs):
        email = attrs["email"].lower()
        raw = attrs["code"].strip()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": self.default_error_messages["no_user"], "reason": "no_user"})
        if user.is_active:
            attrs["user"] = user
            attrs["already_active"] = True
            return attrs
        code_obj = (
            OneTimeCode.objects.active()
            .filter(user=user, purpose=OneTimeCode.PURPOSE_REACTIVATE)
            .order_by("-created_at")
            .first()
        )
        if not code_obj or not check_password(raw, code_obj.code_hash):
            raise serializers.ValidationError({"detail": self.default_error_messages["invalid_code"], "reason": "invalid"})
        attrs["user"] = user
        attrs["code_obj"] = code_obj
        attrs["already_active"] = False
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        if self.validated_data.get("already_active"):
            return user
        now = timezone.now()
        user.is_active = True
        if hasattr(user, "token_valid_after"):
            user.token_valid_after = now
        user.save(update_fields=["is_active", "token_valid_after"] if hasattr(user, "token_valid_after") else ["is_active"])
        code_obj = self.validated_data["code_obj"]
        code_obj.used_at = now
        code_obj.save(update_fields=["used_at"])
        return user