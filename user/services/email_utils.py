from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import send_mail

PROJECT_NAME = getattr(settings, "PROJECT_NAME", "Muzzomo")
BRAND_LOGO_URL = getattr(settings, "BRAND_LOGO_URL", "https://via.placeholder.com/120x40?text=Logo")
SUPPORT_EMAIL = getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL)

def send_plain_email(*, to_email: str, subject: str, body: str) -> None:
    if not to_email:
        raise ValueError("to_email is required")
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        recipient_list=[to_email],
        fail_silently=False,
    )

def send_otp_email(
    *, 
    to_email: str, 
    code: str, 
    ttl_minutes: int = 10, 
    purpose: str = "verify"
) -> None:
    purpose = (purpose or "verify").lower()
    if purpose not in {"verify", "reset", "email_update"}:
        purpose = "verify"

    subjects = {
        "verify":       f"Verify your email • {PROJECT_NAME}",
        "reset":        f"Password reset code • {PROJECT_NAME}",
        "email_update": f"Confirm your new email • {PROJECT_NAME}",
    }
    headlines = {
        "verify":       "Verify your email address",
        "reset":        "Reset your password",
        "email_update": "Confirm your new email",
    }
    subtexts = {
        "verify":       "Use this code to verify your account.",
        "reset":        "Use this code to complete your password reset.",
        "email_update": "Use this code to confirm your new email address.",
    }

    subject = subjects[purpose]
    headline = headlines[purpose]
    subtext = subtexts[purpose]

    text_body = (
        f"{headline}\n\n"
        f"{subtext}\n"
        f"Code: {code}\n"
        f"This code expires in {ttl_minutes} minutes.\n\n"
        f"If you didn’t request this, please ignore this email."
    )

    html_body = render_to_string(
        "emails/otp_email.html",
        {
            "code": code,
            "ttl": ttl_minutes,
            "headline": headline,
            "subtext": subtext,
            "purpose": purpose,
            "brand_name": PROJECT_NAME,
            "logo_url": BRAND_LOGO_URL,
            "support_email": SUPPORT_EMAIL,
            "preheader": f"{subtext} Expires in {ttl_minutes} minutes.",
        },
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        to=[to_email],
        reply_to=[SUPPORT_EMAIL] if SUPPORT_EMAIL else None,
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
