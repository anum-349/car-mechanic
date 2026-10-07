from rest_framework.permissions import BasePermission
from .models import User

class HasRole(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)

class IsMechanic(HasRole):
    allowed_roles = (User.ROLE.MECHANIC,)

class IsUser(HasRole):
    allowed_roles = (User.ROLE.USER,)

class IsAdmin(HasRole):
    allowed_roles = (User.ROLE.ADMIN,)

class IsReviewer(HasRole):
    allowed_roles = (User.ROLE.REVIEWER, User.ROLE.ADMIN)
