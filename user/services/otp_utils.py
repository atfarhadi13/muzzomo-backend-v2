from typing import Tuple, Optional
from django.utils import timezone
from ..models import OneTimeCode

def issue_otp(
    *, 
    user, 
    purpose: str, 
    new_email: Optional[str] = None, 
    length: int = 6, 
    ttl=None
) -> Tuple[OneTimeCode, str, int]:
    obj = OneTimeCode.issue(
        user=user, purpose=purpose, new_email=new_email, length=length, ttl=ttl
    )
    raw = getattr(obj, "raw_code", None)

    delta = (obj.expires_at - obj.created_at)
    ttl_minutes = max(1, int(delta.total_seconds() // 60))

    return obj, raw, ttl_minutes

def is_otp_still_valid(otp_obj: OneTimeCode) -> bool:
    return (otp_obj.used_at is None) and (timezone.now() < otp_obj.expires_at)
