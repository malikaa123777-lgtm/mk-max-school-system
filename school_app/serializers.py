from rest_framework import serializers

from .models import Attendance, Classroom, Grade, School, Student, Subject, Teacher
from .permissions import SUPERUSER, get_role, get_user_school


class SchoolSerializer(serializers.ModelSerializer):
    classrooms_count = serializers.IntegerField(read_only=True)
    students_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = School
        fields = [
            "id", "name", "address", "phone", "is_active", "logo", "background",
            "classrooms_count", "students_count", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_fields(self):
        # مدير المدرسة يقدر يعدّل بيانات مدرسته (شعار، خلفية، عنوان، هاتف) لكن لا يعيد تسميتها
        # ولا يعطّلها — هذا محصور بمدير النظام.
        fields = super().get_fields()
        request = self.context.get("request")
        if request is not None and get_role(request.user) != SUPERUSER:
            fields["name"].read_only = True
            fields["is_active"].read_only = True
        return fields


class SchoolScopedSerializer(serializers.ModelSerializer):
    """أساس المحوّلات: يمنع ربط سجل بعناصر تتبع مدرسة أخرى، ويمنع تكرار الأسماء."""

    related_school_fields = ()
    unique_name_per_school = False

    def _school(self):
        request = self.context.get("request")
        if request is None:
            return None
        school = get_user_school(request.user)
        if school is None and self.instance is not None:
            school = getattr(self.instance, "school", None)
        return school

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self._school()
        if school is None:
            return attrs

        for name in self.related_school_fields:
            value = attrs.get(name)
            if value is None:
                continue
            items = value if isinstance(value, (list, tuple)) else [value]
            if any(item.school_id != school.id for item in items):
                raise serializers.ValidationError({name: "العنصر المحدد لا يتبع مدرستك."})

        if self.unique_name_per_school and "name" in attrs:
            qs = self.Meta.model.objects.filter(school=school, name=attrs["name"])
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"name": "هذا الاسم مستخدم مسبقاً في المدرسة."})
        return attrs


class ClassroomSerializer(SchoolScopedSerializer):
    unique_name_per_school = True
    students_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Classroom
        fields = ["id", "school", "name", "capacity", "students_count", "created_at", "updated_at"]
        read_only_fields = ["school", "created_at", "updated_at"]


class SubjectSerializer(SchoolScopedSerializer):
    unique_name_per_school = True

    class Meta:
        model = Subject
        fields = ["id", "school", "name", "created_at", "updated_at"]
        read_only_fields = ["school", "created_at", "updated_at"]


class TeacherSerializer(SchoolScopedSerializer):
    related_school_fields = ("subjects",)

    class Meta:
        model = Teacher
        fields = ["id", "school", "full_name", "phone", "subjects", "created_at", "updated_at"]
        read_only_fields = ["school", "created_at", "updated_at"]


class StudentSerializer(SchoolScopedSerializer):
    related_school_fields = ("classroom",)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True, default=None)

    class Meta:
        model = Student
        fields = [
            "id", "school", "classroom", "classroom_name", "full_name", "gender",
            "date_of_birth", "guardian_name", "guardian_phone", "enrolled_on",
            "is_active", "user", "guardians", "created_at", "updated_at",
        ]
        read_only_fields = ["school", "created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        classroom = attrs.get("classroom")
        if classroom is not None and not self.instance:
            if classroom.students.filter(is_active=True).count() >= classroom.capacity:
                raise serializers.ValidationError({"classroom": "الصف وصل إلى سعته القصوى."})
        return attrs


class GradeSerializer(SchoolScopedSerializer):
    related_school_fields = ("student", "subject")
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Grade
        fields = [
            "id", "student", "student_name", "subject", "subject_name", "exam_name",
            "score", "max_score", "exam_date", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        score = attrs.get("score", getattr(self.instance, "score", None))
        max_score = attrs.get("max_score", getattr(self.instance, "max_score", None))
        if max_score is not None and max_score <= 0:
            raise serializers.ValidationError({"max_score": "الدرجة العظمى يجب أن تكون أكبر من صفر."})
        if score is not None and max_score is not None and score > max_score:
            raise serializers.ValidationError({"score": "الدرجة لا يمكن أن تتجاوز الدرجة العظمى."})
        return attrs


class AttendanceSerializer(SchoolScopedSerializer):
    related_school_fields = ("student",)
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = Attendance
        fields = ["id", "student", "student_name", "date", "status", "note", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
