from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

def blacklist_user_tokens(user):
    for t in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=t)