from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Attendance, Classroom, Grade, Role, School, Student, Subject, Teacher
from .permissions import (
    IsSchoolMember,
    IsSchoolStaff,
    IsSuperuserOrStaffReadOnly,
    get_role,
    get_user_school,
)
from .serializers import (
    AttendanceSerializer,
    ClassroomSerializer,
    GradeSerializer,
    SchoolSerializer,
    StudentSerializer,
    SubjectSerializer,
    TeacherSerializer,
)


class SchoolScopedViewSet(viewsets.ModelViewSet):
    """كل مستخدم يرى بيانات مدرسته فقط (مدير النظام يرى الكل)."""

    permission_classes = [IsSchoolStaff]
    school_lookup = "school"      # مسار الوصول إلى المدرسة من النموذج
    assigns_school = True         # هل للنموذج حقل school مباشر؟
    filter_fields = ()            # حقول التصفية عبر ?field=value

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            school = get_user_school(user)
            if school is None:
                return qs.none()
            qs = qs.filter(**{self.school_lookup: school.pk})
            qs = self._scope_for_role(qs, user)
        return self._apply_filters(qs)

    def _scope_for_role(self, qs, user):
        """نقطة توسّع: الطالب وولي الأمر يرون فقط سجلاتهم الخاصة. الافتراضي لا يقيّد شيء إضافي."""
        return qs

    def _apply_filters(self, qs):
        for field in self.filter_fields:
            value = self.request.query_params.get(field)
            if value in (None, ""):
                continue
            if value.lower() in {"true", "false"}:
                value = value.lower() == "true"
            try:
                qs = qs.filter(**{field: value})
            except (ValueError, TypeError, DjangoValidationError):
                raise ValidationError({field: "قيمة غير صالحة."})
        return qs

    def perform_create(self, serializer):
        if not self.assigns_school:
            serializer.save()
            return
        school = get_user_school(self.request.user)
        if school is None:
            raise PermissionDenied("حسابك غير مرتبط بمدرسة.")
        serializer.save(school=school)


class SchoolViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolSerializer
    permission_classes = [IsSuperuserOrStaffReadOnly]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        qs = School.objects.annotate(
            classrooms_count=Count("classrooms", distinct=True),
            students_count=Count("students", distinct=True),
        )
        user = self.request.user
        if user.is_superuser:
            return qs
        school = get_user_school(user)
        return qs.filter(pk=school.pk) if school else qs.none()


class ClassroomViewSet(SchoolScopedViewSet):
    permission_classes = [IsSchoolMember]
    queryset = Classroom.objects.select_related("school").annotate(students_count=Count("students"))
    serializer_class = ClassroomSerializer
    search_fields = ["name"]
    ordering_fields = ["name", "capacity"]


class SubjectViewSet(SchoolScopedViewSet):
    permission_classes = [IsSchoolMember]
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    search_fields = ["name"]
    ordering_fields = ["name"]


class TeacherViewSet(SchoolScopedViewSet):
    permission_classes = [IsSchoolMember]
    queryset = Teacher.objects.prefetch_related("subjects")
    serializer_class = TeacherSerializer
    search_fields = ["full_name", "phone"]
    ordering_fields = ["full_name"]


class StudentViewSet(SchoolScopedViewSet):
    permission_classes = [IsSchoolMember]
    queryset = Student.objects.select_related("classroom")
    serializer_class = StudentSerializer
    search_fields = ["full_name", "guardian_name", "guardian_phone"]
    ordering_fields = ["full_name", "enrolled_on"]
    filter_fields = ("classroom", "is_active", "gender")

    def _scope_for_role(self, qs, user):
        role = get_role(user)
        if role == Role.STUDENT:
            return qs.filter(user=user)
        if role == Role.PARENT:
            return qs.filter(guardians=user)
        return qs


class GradeViewSet(SchoolScopedViewSet):
    permission_classes = [IsSchoolMember]
    queryset = Grade.objects.select_related("student", "subject")
    serializer_class = GradeSerializer
    school_lookup = "student__school"
    assigns_school = False
    search_fields = ["student__full_name", "exam_name"]
    ordering_fields = ["exam_date", "score"]
    filter_fields = ("student", "subject", "student__classroom", "exam_date")

    def _scope_for_role(self, qs, user):
        role = get_role(user)
        if role == Role.STUDENT:
            return qs.filter(student__user=user)
        if role == Role.PARENT:
            return qs.filter(student__guardians=user)
        return qs


class AttendanceViewSet(SchoolScopedViewSet):
    permission_classes = [IsSchoolMember]
    queryset = Attendance.objects.select_related("student")
    serializer_class = AttendanceSerializer
    school_lookup = "student__school"
    assigns_school = False
    search_fields = ["student__full_name"]
    ordering_fields = ["date"]
    filter_fields = ("student", "date", "status", "student__classroom")

    def _scope_for_role(self, qs, user):
        role = get_role(user)
        if role == Role.STUDENT:
            return qs.filter(student__user=user)
        if role == Role.PARENT:
            return qs.filter(student__guardians=user)
        return qs


class MeView(APIView):
    """بيانات المستخدم الحالي: دوره، مدرسته، وسجله المرتبط إن وجد."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = get_role(user)
        school = get_user_school(user)
        data = {
            "id": user.id,
            "username": user.username,
            "role": role,
            "school": SchoolSerializer(school, context={"request": request}).data if school else None,
        }
        if role == Role.TEACHER:
            teacher = getattr(user, "teacher_record", None)
            data["teacher_id"] = teacher.id if teacher else None
        if role == Role.STUDENT:
            student = getattr(user, "student_record", None)
            data["student_id"] = student.id if student else None
        if role == Role.PARENT:
            data["children_ids"] = list(user.children.values_list("id", flat=True))
        return Response(data)
