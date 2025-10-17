from django.core.exceptions import FieldError
from django.utils.dateparse import parse_datetime

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from .serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    PasswordResetResendOTPSerializer,
    RegisterSerializer,
    UnlockConfirmSerializer,
    UnlockRequestSerializer,
    VerifyEmailOTPSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailUpdateRequestSerializer,
    EmailUpdateConfirmSerializer,
    ProfileImageUpdateSerializer,
    ProfileBasicUpdateSerializer,
    ResendOTPSerializer,
    ReactivateAccountRequestSerializer,
    ReactivateAccountConfirmSerializer,
)

from .services.otp_utils import issue_otp, can_resend
from .services.email_utils import send_otp_email
from .models import OneTimeCode, CustomUser


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "register"

    def post(self, request):
        email = (request.data.get("email") or "").lower().strip()
        if email:
            existing = CustomUser.objects.filter(email__iexact=email).first()
            if existing:
                if existing.is_verified:
                    return Response(
                        {
                            "detail": "This email is already registered and verified. Please log in.",
                            "email": existing.email,
                            "next_action": "login"
                        },
                        status=status.HTTP_200_OK,
                    )
                if not can_resend(existing.id, OneTimeCode.PURPOSE_LOGIN, limit=1, window=60):
                    return Response(
                        {
                            "detail": "Please wait before requesting another verification code.",
                            "reason": "rate_limited",
                            "next_action": "wait_and_retry"
                        },
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                obj, code, ttl_min = issue_otp(user=existing, purpose=OneTimeCode.PURPOSE_LOGIN)
                try:
                    send_otp_email(to_email=existing.email, code=code, ttl_minutes=ttl_min, purpose="verify")
                except Exception:
                    pass
                return Response(
                    {
                        "detail": "Account exists but is not verified. A new verification code has been sent.",
                        "requires_verification": True,
                        "next_action": "verify_email",
                        "email": existing.email,
                        "otp_ttl_seconds": ttl_min * 60,
                    },
                    status=status.HTTP_200_OK,
                )

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_LOGIN)
        try:
            send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="verify")
        except Exception as e:
            return Response(
                {
                    "detail": "User created, but failed to send verification code.",
                    "error": str(e),
                    "next_action": "resend_code"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "detail": "Registration successful. Verification code sent.",
                "requires_verification": True,
                "next_action": "verify_email",
                "email": user.email,
                "otp_ttl_seconds": ttl_min * 60,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = VerifyEmailOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        already = serializer.validated_data.get("already_verified", False)
        return Response(
            {
                "detail": "Account is already verified. You can login." if already else "Email verified successfully.",
                "email": user.email,
                "is_verified": True,
                "is_provider": user.is_provider,
                "next_action": "login",
            },
            status=status.HTTP_200_OK,
        )


class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        s = ResendOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response(result, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        s = PasswordResetRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response(result, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response(
            {
                "detail": "Password has been reset successfully.",
                "email": user.email,
                "next_action": "login",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetResendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = PasswordResetResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer
    throttle_scope = "login"


class TokenRefreshAPIView(TokenRefreshView):
    permission_classes = [AllowAny]


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except Exception:
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


class EmailUpdateRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "otp"

    def post(self, request):
        s = EmailUpdateRequestSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response(result, status=status.HTTP_200_OK)


class EmailUpdateConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = EmailUpdateConfirmSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response(
            {
                "detail": "Email updated successfully.",
                "email": user.email,
                "next_action": "relogin",
            },
            status=status.HTTP_200_OK,
        )


class EmailUpdateResendOTPView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "otp"

    def post(self, request):
        user = request.user
        pending = OneTimeCode.objects.active().filter(
            user=user, purpose=OneTimeCode.PURPOSE_EMAIL
        ).order_by("-created_at").first()
        if not pending or not pending.new_email:
            return Response({"detail": "No pending email update to resend."}, status=400)
        if not can_resend(user.id, OneTimeCode.PURPOSE_EMAIL, limit=1, window=60):
            return Response({"detail": "Please wait before requesting another code."}, status=429)
        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_EMAIL, new_email=pending.new_email)
        send_otp_email(to_email=pending.new_email, code=code, ttl_minutes=ttl_min, purpose="email_update")
        return Response({"detail": "Verification code re-sent."}, status=200)


class ProfileImageUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = ProfileImageUpdateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        user = s.save()
        image_url = request.build_absolute_uri(user.profile_image.url) if user.profile_image else None
        return Response({"detail": "Profile image updated.", "profile_image": image_url}, status=status.HTTP_200_OK)


class ProfileBasicUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        s = ProfileBasicUpdateSerializer(data=request.data, context={"request": request}, partial=True)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response(
            {
                "detail": "Profile updated.",
                "user": {
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        return self.patch(request)


class UnlockRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        s = UnlockRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"detail": "If the account exists, an unlock code was sent."})


class UnlockConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        s = UnlockConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response(result, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "login"

    def post(self, request):
        s = ChangePasswordSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"detail": "Password updated."}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response(
            {
                "id": str(u.pk),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone_number": u.phone_number,
                "is_verified": u.is_verified,
                "email_verified_at": u.email_verified_at,
                "profile_image": request.build_absolute_uri(u.profile_image.url) if u.profile_image else None,
            }
        )


class DeactivateAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user.is_active = False
        user.save(update_fields=["is_active"])
        from .utils.tokens import blacklist_user_tokens
        blacklist_user_tokens(user)
        return Response({"detail": "Account deactivated."})

class SessionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = OutstandingToken.objects.filter(user=request.user)

            include_blacklisted = request.query_params.get("include_blacklisted", "true").lower() == "true"
            if not include_blacklisted:
                qs = qs.exclude(blacklistedtoken__isnull=False)

            created_after = request.query_params.get("created_after")
            created_before = request.query_params.get("created_before")
            if created_after:
                dt = parse_datetime(created_after)
                if not dt:
                    return Response({"detail": "Invalid 'created_after' datetime."}, status=400)
                qs = qs.filter(created_at__gte=dt)
            if created_before:
                dt = parse_datetime(created_before)
                if not dt:
                    return Response({"detail": "Invalid 'created_before' datetime."}, status=400)
                qs = qs.filter(created_at__lte=dt)

            try:
                qs = qs.order_by("-created_at")
            except FieldError:
                return Response({"detail": "Ordering field invalid."}, status=400)
            
            page = max(1, int(request.query_params.get("page", 1)))
            size = max(1, min(100, int(request.query_params.get("size", 50))))
            start = (page - 1) * size
            end = start + size
            total = qs.count()
            items = qs[start:end]

            data = []
            blacklisted_map = set(BlacklistedToken.objects.filter(token__in=items).values_list("token_id", flat=True))
            for t in items:
                data.append({
                    "id": t.jti,
                    "created_at": t.created_at,
                    "expires_at": t.expires_at,
                    "blacklisted": t.id in blacklisted_map,
                })

            return Response({
                "results": data,
                "page": page,
                "size": size,
                "total": total,
                "has_next": end < total,
            }, status=200)

        except Exception as e:
            return Response({"detail": "Failed to fetch sessions.", "error": str(e)}, status=500)


class RevokeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        jti = (request.data.get("jti") or "").strip()
        if not jti:
            return Response({"detail": "jti required."}, status=400)

        try:
            t = OutstandingToken.objects.filter(user=request.user, jti=jti).first()
            if not t:
                return Response({"detail": "Session not found."}, status=404)

            bl, created = BlacklistedToken.objects.get_or_create(token=t)
            return Response(
                {"detail": "Session revoked." if created else "Session already revoked.", "jti": jti},
                status=200
            )
        except Exception as e:
            return Response({"detail": "Failed to revoke session.", "error": str(e)}, status=500)
        
class ReactivateAccountRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        s = ReactivateAccountRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response(result, status=status.HTTP_200_OK)
    
class ReactivateAccountConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        s = ReactivateAccountConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response(
            {
                "detail": "Account reactivated." if not s.validated_data.get("already_active") else "Account is already active.",
                "email": user.email,
                "next_action": "login",
            },
            status=status.HTTP_200_OK,
        )