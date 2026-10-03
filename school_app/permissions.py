from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role

SUPERUSER = "superuser"
STAFF_ROLES = {SUPERUSER, Role.DIRECTOR, Role.TEACHER}
DELETE_ROLES = {SUPERUSER, Role.DIRECTOR}
ALL_SCHOOL_ROLES = {SUPERUSER, Role.DIRECTOR, Role.TEACHER, Role.STUDENT, Role.PARENT}


def get_role(user):
    """يرجع دور المستخدم، أو None إن لم يكن له دور صالح ومدرسة."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return SUPERUSER
    profile = getattr(user, "profile", None)
    if profile is None or profile.school_id is None:
        return None
    return profile.role


def get_user_school(user):
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    return profile.school if profile else None


class IsSchoolStaff(BasePermission):
    """المدير والمعلم فقط؛ الحذف للمدير فقط. الطلاب وأولياء الأمور لا وصول لهم حالياً."""

    message = "غير مصرّح لك بتنفيذ هذا الإجراء."

    def has_permission(self, request, view):
        role = get_role(request.user)
        if role is None:
            return False
        if request.method == "DELETE":
            return role in DELETE_ROLES
        return role in STAFF_ROLES


class IsSchoolMember(BasePermission):
    """كل عضو بالمدرسة (مدير/معلم/طالب/ولي أمر) يقرأ، والكتابة والحذف محصورة بالطاقم."""

    message = "غير مصرّح لك بتنفيذ هذا الإجراء."

    def has_permission(self, request, view):
        role = get_role(request.user)
        if role is None:
            return False
        if request.method in SAFE_METHODS:
            return role in ALL_SCHOOL_ROLES
        if request.method == "DELETE":
            return role in DELETE_ROLES
        return role in STAFF_ROLES


class IsSuperuserOrStaffReadOnly(BasePermission):
    """المدارس: القراءة لأي عضو. الإنشاء والحذف لمدير النظام فقط.
    التعديل (مثل رفع الشعار والخلفية) مسموح لمدير النظام على أي مدرسة،
    ولمدير المدرسة على مدرسته هو فقط (يُتحقق في has_object_permission)."""

    message = "إدارة المدارس متاحة لمدير النظام، والتعديل على مدرستك فقط لمدير المدرسة."

    def has_permission(self, request, view):
        role = get_role(request.user)
        if role is None:
            return False
        if request.method in SAFE_METHODS:
            return role in ALL_SCHOOL_ROLES
        if role == SUPERUSER:
            return True
        if role == Role.DIRECTOR and request.method in ("PUT", "PATCH"):
            return True
        return False

    def has_object_permission(self, request, view, obj):
        role = get_role(request.user)
        if role == SUPERUSER:
            return True
        if request.method in SAFE_METHODS:
            return True
        if role == Role.DIRECTOR and request.method in ("PUT", "PATCH"):
            return get_user_school(request.user) == obj
        return False
