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
            if existing and not existing.is_verified:
                if not can_resend(existing.id, OneTimeCode.PURPOSE_LOGIN, limit=1, window=60):
                    return Response(
                        {"detail": "Please wait before requesting another verification code."},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                obj, code, ttl_min = issue_otp(user=existing, purpose=OneTimeCode.PURPOSE_LOGIN)
                try:
                    send_otp_email(to_email=existing.email, code=code, ttl_minutes=ttl_min, purpose="verify")
                except Exception:
                    pass
                return Response(
                    {
                        "detail": "If an account exists, a verification code has been sent.",
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
                {"detail": "User created, but failed to send OTP email.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "detail": "Registration successful. OTP sent.",
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
        return Response(
            {
                "detail": "Email verified successfully.",
                "email": user.email,
                "is_verified": user.is_verified,
                "is_provider": user.is_provider,
            },
            status=status.HTTP_200_OK,
        )


class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        from .serializers import ResendOTPSerializer
        s = ResendOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"detail": "If an account exists, a new code was sent."})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        s = PasswordResetRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"detail": "If an account exists, a reset code was sent."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"detail": "Password has been reset successfully."}, status=status.HTTP_200_OK)


class PasswordResetResendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = PasswordResetResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "A new password reset OTP code has been sent to your email."}, status=status.HTTP_200_OK)


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
        s.save()
        return Response({"detail": "Verification code sent to new email."}, status=status.HTTP_200_OK)


class EmailUpdateConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = EmailUpdateConfirmSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response({"detail": "Email updated successfully.", "email": user.email}, status=status.HTTP_200_OK)


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
        tokens = OutstandingToken.objects.filter(user=request.user).order_by("-created")
        return Response(
            [
                {
                    "id": t.jti,
                    "created_at": t.created,
                    "expires_at": t.expires_at,
                    "blacklisted": BlacklistedToken.objects.filter(token=t).exists(),
                }
                for t in tokens
            ]
        )


class RevokeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        jti = request.data.get("jti")
        if not jti:
            return Response({"detail": "jti required."}, status=400)
        t = OutstandingToken.objects.filter(user=request.user, jti=jti).first()
        if not t:
            return Response({"detail": "Not found."}, status=404)
        BlacklistedToken.objects.get_or_create(token=t)
        return Response({"detail": "Session revoked."})