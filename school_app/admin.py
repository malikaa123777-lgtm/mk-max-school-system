from django.contrib import admin

from .models import Attendance, Classroom, Grade, School, Student, Subject, Teacher, UserProfile


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "is_active", "logo", "background")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "role")
    list_filter = ("role", "school")
    search_fields = ("user__username",)


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "capacity")
    list_filter = ("school",)
    search_fields = ("name",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "school")
    list_filter = ("school",)
    search_fields = ("name",)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("full_name", "school", "phone")
    list_filter = ("school",)
    search_fields = ("full_name", "phone")
    filter_horizontal = ("subjects",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "school", "classroom", "is_active", "user")
    list_filter = ("school", "classroom", "is_active", "gender")
    search_fields = ("full_name", "guardian_name", "guardian_phone")
    filter_horizontal = ("guardians",)
    autocomplete_fields = ("user",)


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "exam_name", "score", "max_score", "exam_date")
    list_filter = ("subject", "exam_date")
    search_fields = ("student__full_name", "exam_name")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "status")
    list_filter = ("status", "date")
    search_fields = ("student__full_name",)
