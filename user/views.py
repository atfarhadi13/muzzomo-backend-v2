from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import ( EmailTokenObtainPairSerializer, RegisterSerializer, VerifyEmailOTPSerializer, 
                          PasswordResetRequestSerializer, PasswordResetConfirmSerializer, 
                          EmailUpdateRequestSerializer, EmailUpdateConfirmSerializer, ProfileImageUpdateSerializer, 
                          ProfileBasicUpdateSerializer )

from .services.otp_utils import issue_otp
from .services.email_utils import send_otp_email

from .models import OneTimeCode

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        obj, code, ttl_min = issue_otp(user=user, purpose=OneTimeCode.PURPOSE_LOGIN)
        try:
            send_otp_email(to_email=user.email, code=code, ttl_minutes=ttl_min, purpose="verify")
        except Exception as e:
            return Response(
                {"detail": "User created, but failed to send OTP email.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"detail": "Registration successful. OTP has been sent to your email."},
            status=status.HTTP_201_CREATED
        )
        
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

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
    def post(self, request):
        from .serializers import ResendOTPSerializer
        s = ResendOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"detail": "If an account exists, a new code was sent."})
    

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

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
    

class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer


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
        return Response(
            {"detail": "Email updated successfully.", "email": user.email},
            status=status.HTTP_200_OK,
        )
        
class ProfileImageUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = ProfileImageUpdateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        user = s.save()
        image_url = request.build_absolute_uri(user.profile_image.url) if user.profile_image else None
        return Response(
            {"detail": "Profile image updated.", "profile_image": image_url},
            status=status.HTTP_200_OK,
        )
        
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