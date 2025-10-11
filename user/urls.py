from django.urls import path

from user.views import  ( RegisterView, VerifyEmailView, ResendOTPView, 
                         PasswordResetRequestView, PasswordResetConfirmView, 
                         LoginView, TokenRefreshAPIView, LogoutView, EmailUpdateRequestView,
                         EmailUpdateConfirmView, ProfileImageUpdateView, ProfileBasicUpdateView,
                         PasswordResetResendOTPView, EmailUpdateResendOTPView
                         )

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/verify-email/", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/resend-otp/", ResendOTPView.as_view(), name="auth-resend-otp"),

    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/token/refresh/", TokenRefreshAPIView.as_view(), name="auth-token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    
    path("auth/password-reset/request/", PasswordResetRequestView.as_view(), name="auth-password-reset-request"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path('password-reset/resend-otp/', PasswordResetResendOTPView.as_view(), name='password-reset-resend-otp'),
    
    path("auth/email-update/request/", EmailUpdateRequestView.as_view(), name="auth-email-update-request"),
    path("auth/email-update/confirm/", EmailUpdateConfirmView.as_view(), name="auth-email-update-confirm"),
    path('email-update/resend-otp/', EmailUpdateResendOTPView.as_view(), name='email-update-resend-otp'),
    
    path("auth/profile/image/", ProfileImageUpdateView.as_view(), name="auth-profile-image"),
    path("auth/profile/basic/", ProfileBasicUpdateView.as_view(), name="auth-profile-basic"),

]
