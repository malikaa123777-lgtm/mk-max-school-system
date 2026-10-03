from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("schools", views.SchoolViewSet, basename="school")
router.register("classrooms", views.ClassroomViewSet, basename="classroom")
router.register("subjects", views.SubjectViewSet, basename="subject")
router.register("teachers", views.TeacherViewSet, basename="teacher")
router.register("students", views.StudentViewSet, basename="student")
router.register("grades", views.GradeViewSet, basename="grade")
router.register("attendance", views.AttendanceViewSet, basename="attendance")

urlpatterns = [
    path("auth/me/", views.MeView.as_view(), name="api-me"),
    path("", include(router.urls)),
]
