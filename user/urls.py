from django.urls import path

from user.views import (
    RegisterView, VerifyEmailView, ResendOTPView,
    LoginView, TokenRefreshAPIView, LogoutView,

    PasswordResetRequestView, PasswordResetConfirmView, PasswordResetResendOTPView,
    ChangePasswordView,

    EmailUpdateRequestView, EmailUpdateConfirmView, EmailUpdateResendOTPView,

    ProfileImageUpdateView, ProfileBasicUpdateView, MeView,

    DeactivateAccountView, ReactivateAccountConfirmView, ReactivateAccountRequestView,

    SessionsView, RevokeSessionView,

     UnlockRequestView, UnlockConfirmView,
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
    path("auth/password-reset/resend-otp/", PasswordResetResendOTPView.as_view(), name="auth-password-reset-resend-otp"),
    path("auth/password/change/", ChangePasswordView.as_view(), name="auth-password-change"),

    path("auth/email-update/request/", EmailUpdateRequestView.as_view(), name="auth-email-update-request"),
    path("auth/email-update/confirm/", EmailUpdateConfirmView.as_view(), name="auth-email-update-confirm"),
    path("auth/email-update/resend-otp/", EmailUpdateResendOTPView.as_view(), name="auth-email-update-resend-otp"),

    path("auth/profile/image/", ProfileImageUpdateView.as_view(), name="auth-profile-image"),
    path("auth/profile/basic/", ProfileBasicUpdateView.as_view(), name="auth-profile-basic"),
    path("me/", MeView.as_view(), name="me"),

    path("account/deactivate/", DeactivateAccountView.as_view(), name="account-deactivate"),
    path("account/reactivate/request/", ReactivateAccountRequestView.as_view(), name="account-reactivate-request"),
    path("account/reactivate/confirm/", ReactivateAccountConfirmView.as_view(), name="account-reactivate-confirm"),

    path("sessions/", SessionsView.as_view(), name="sessions-list"),
    path("sessions/revoke/", RevokeSessionView.as_view(), name="sessions-revoke"),

    path("auth/unlock/request/", UnlockRequestView.as_view(), name="auth-unlock-request"),
    path("auth/unlock/confirm/", UnlockConfirmView.as_view(), name="auth-unlock-confirm"),
]