from typing import Tuple, Optional

from django.utils import timezone
from django.core.cache import cache

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

def can_resend(user_id, purpose, limit=1, window=60):
    key = f"otp_resend:{purpose}:{user_id}"
    count = cache.get(key, 0)
    if count >= limit: 
        return False
    cache.incr(key) if cache.get(key) else cache.set(key, 1, timeout=window)
    return True