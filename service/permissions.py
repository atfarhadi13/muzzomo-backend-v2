from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        try:
            if request.method in SAFE_METHODS:
                return True
            return request.user.is_authenticated and obj.user_id == request.user.id
        except Exception:
            return False