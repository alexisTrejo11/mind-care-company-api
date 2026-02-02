from rest_framework.permissions import BasePermission


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "patient"


class IsSpecialist(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "specialist"


class IsAdminOrStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in [
            "admin",
            "staff",
        ]


class IsSpecialistOrStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in [
            "specialist",
            "staff",
            "admin",
        ]


class IsAdminStaffOrSpecialist(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in [
            "admin",
            "staff",
            "specialist",
        ]
