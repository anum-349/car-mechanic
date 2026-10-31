from rest_framework.permissions import SAFE_METHODS, BasePermission

STAFF_ROLES = {"reviewer", "admin"}


def is_staff_role(user):
    return bool(user and user.is_authenticated
                and (user.is_superuser or user.role in STAFF_ROLES))


def is_admin_role(user):
    return bool(user and user.is_authenticated
                and (user.is_superuser or user.role == "admin"))


class IsReviewer(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.role in STAFF_ROLES)


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and (getattr(user, "is_superuser", False)
                                                or user.role == "admin"))


class IsMechanic(BasePermission):
    message = "Only users registered as mechanics can do this."

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated
                    and request.user.role == "mechanic")


# Backwards-compatible names used by the existing accounts API.
IsReviewerOrAdmin = IsReviewer
IsMechanicRole = IsMechanic


class ReadOnlyOrReviewer(BasePermission):
    """Anyone can read; only reviewers/admins can write."""
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_staff_role(request.user)


class IsOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id or is_staff_role(request.user)
