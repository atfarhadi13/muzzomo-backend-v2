from django.utils import timezone

from django.contrib.auth import get_user_model, password_validation
from django.core.files.storage import default_storage
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.hashers import check_password

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers

from .models import OneTimeCode

from .services.otp_utils import issue_otp
from .services.email_utils import send_otp_email

User = get_user_model()

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    def validate_email(self, value):
        try:
            if User.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
            return value.lower()
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def validate(self, attrs):
        try:
            password_validation.validate_password(attrs["password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        except Exception as e:
            raise serializers.ValidationError({"password": str(e)})
        return attrs

    def create(self, validated_data):
        try:
            user = User.objects.create_user(
                email=validated_data["email"],
                password=validated_data["password"],
                is_verified=False,
            )
            return user
        except Exception as e:
            raise serializers.ValidationError(str(e))

class VerifyEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=10, trim_whitespace=True)

    default_error_messages = {
        "no_user": "No account found for this email.",
        "no_code": "No active code found. Please request a new code.",
        "invalid_code": "Invalid or expired code.",
    }

    def validate(self, attrs):
        email = attrs["email"].lower()
        code = attrs["code"].strip()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            self.fail("no_user")
        except Exception as e:
            raise serializers.ValidationError(str(e))

        try:
            has_active = OneTimeCode.objects.active().filter(
                user=user, purpose=OneTimeCode.PURPOSE_LOGIN
            ).exists()
            if not has_active:
                self.fail("no_code")

            ok = OneTimeCode.verify_and_consume(
                user=user, purpose=OneTimeCode.PURPOSE_LOGIN, raw_code=code
            )
            if not ok:
                self.fail("invalid_code")
        except Exception as e:
            raise serializers.ValidationError(str(e))

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        try:
            user = self.validated_data["user"]
            if not user.is_verified:
                user.is_verified = True
                user.is_provider = True
                user.save(update_fields=["is_verified", "is_provider"])
            return user
        except Exception as e:
            raise serializers.ValidationError(str(e))

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self, **kwargs):
        try:
            email = self.validated_data["email"].lower()
            User = get_user_model()
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                return
            obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_LOGIN)
            send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="verify")
        except Exception:
            return

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self, **kwargs):
        try:
            email = self.validated_data["email"].lower()
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                return
            obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_RESET)
            send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="reset")
        except Exception:
            return

class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=10, trim_whitespace=True)
    new_password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    default_error_messages = {
        "no_user": "No account found for this email.",
        "no_code": "No active reset code found. Please request a new code.",
        "invalid_code": "Invalid or expired code.",
    }

    def validate(self, attrs):
        email = attrs["email"].lower()
        code = attrs["code"].strip()
        new_password = attrs["new_password"]
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            self.fail("no_user")
        except Exception as e:
            raise serializers.ValidationError(str(e))

        try:
            if not OneTimeCode.objects.active().filter(user=user, purpose=OneTimeCode.PURPOSE_RESET).exists():
                self.fail("no_code")
        except Exception as e:
            raise serializers.ValidationError(str(e))

        try:
            password_validation.validate_password(new_password, user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        except Exception as e:
            raise serializers.ValidationError({"new_password": str(e)})

        try:
            ok = OneTimeCode.verify_and_consume(
                user=user,
                purpose=OneTimeCode.PURPOSE_RESET,
                raw_code=code
            )
            if not ok:
                self.fail("invalid_code")
        except Exception as e:
            raise serializers.ValidationError(str(e))

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        try:
            user = self.validated_data["user"]
            new_password = self.validated_data["new_password"]
            user.set_password(new_password)
            user.save(update_fields=["password"])
            return user
        except Exception as e:
            raise serializers.ValidationError(str(e))

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        try:
            email = (attrs.get("email") or "").lower()
            password = attrs.get("password") or ""
            data = super().validate({self.username_field: email, "password": password})
            user = self.user
            data.update({
                "user": {
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_verified": user.is_verified,
                    "is_provider": user.is_provider,
                    "is_professional": user.is_professional,
                }
            })
            return data
        except Exception as e:
            raise serializers.ValidationError(str(e))

class EmailUpdateRequestSerializer(serializers.Serializer):
    new_email = serializers.EmailField()

    def validate_new_email(self, value):
        try:
            request = self.context["request"]
            new_email = value.lower()
            if request.user.email.lower() == new_email:
                raise serializers.ValidationError("New email must be different from current email.")
            if User.objects.filter(email__iexact=new_email).exists():
                raise serializers.ValidationError("This email is already in use.")
            return new_email
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def save(self, **kwargs):
        try:
            request = self.context["request"]
            user = request.user
            new_email = self.validated_data["new_email"]
            obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_EMAIL, new_email=new_email)
            send_otp_email(to_email=new_email, code=code, ttl_minutes=ttl_min, purpose="email_update")
            return {"detail": "Verification code sent to new email."}
        except Exception as e:
            raise serializers.ValidationError(str(e))

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
        try:
            with transaction.atomic():
                code_obj = (
                    OneTimeCode.objects.select_for_update()
                    .active()
                    .filter(user=user, purpose=OneTimeCode.PURPOSE_EMAIL)
                    .first()
                )
                if not code_obj:
                    self.fail("no_code")

                if not check_password(raw, code_obj.code_hash):
                    self.fail("invalid_code")

                new_email = (code_obj.new_email or "").lower()
                if not new_email:
                    raise serializers.ValidationError({"detail": "No pending email to apply for this code."})

                if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                    self.fail("email_taken")

                attrs["code_obj"] = code_obj
                attrs["new_email"] = new_email
            return attrs
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def save(self, **kwargs):
        user = self.context["request"].user
        code_obj: OneTimeCode = self.validated_data["code_obj"]
        new_email: str = self.validated_data["new_email"]
        try:
            with transaction.atomic():
                user.email = new_email
                try:
                    user.save(update_fields=["email"])
                except IntegrityError:
                    raise serializers.ValidationError({"detail": "Email already in use. Please request a new code."})

                if hasattr(code_obj, "mark_used"):
                    code_obj.mark_used()
                else:
                    code_obj.used_at = timezone.now()
                    code_obj.save(update_fields=["used_at"])
            return user
        except Exception as e:
            raise serializers.ValidationError(str(e))

class ProfileImageUpdateSerializer(serializers.Serializer):
    profile_image = serializers.ImageField(required=True)

    def validate_profile_image(self, image):
        try:
            max_mb = 5
            if image.size > max_mb * 1024 * 1024:
                raise serializers.ValidationError(f"Max file size is {max_mb}MB.")
            allowed = {"image/jpeg", "image/png", "image/webp"}
            ctype = getattr(image, "content_type", None)
            if ctype and ctype not in allowed:
                raise serializers.ValidationError("Only JPEG, PNG, or WEBP are allowed.")
            return image
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def save(self, **kwargs):
        try:
            user = self.context["request"].user
            new_file = self.validated_data["profile_image"]
            old_path = user.profile_image.name if getattr(user, "profile_image", None) else None

            user.profile_image = new_file
            user.save(update_fields=["profile_image"])

            if old_path and old_path != user.profile_image.name:
                if default_storage.exists(old_path):
                    default_storage.delete(old_path)

            return user
        except Exception as e:
            raise serializers.ValidationError(str(e))

class ProfileBasicUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=30, trim_whitespace=True)
    last_name  = serializers.CharField(required=False, allow_blank=True, max_length=30, trim_whitespace=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_phone_number(self, value):
        try:
            if value in (None, ""):
                return None
            phone = value.strip()
            user = self.context["request"].user
            field = user._meta.get_field("phone_number")
            field.run_validators(phone)
            return phone
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def _clean_name(self, name):
        try:
            if name is None:
                return None
            name = name.strip()
            return name.title()
        except Exception:
            return None

    def save(self, **kwargs):
        try:
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
        except Exception as e:
            raise serializers.ValidationError(str(e))

