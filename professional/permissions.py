from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        try:
            if request.user and request.user.is_staff:
                return True
            return obj.user_id == getattr(request.user, "id", None)
        except Exception:
            return False

    def has_permission(self, request, view):
        try:
            return request.user and request.user.is_authenticated
        except Exception:
            return False

