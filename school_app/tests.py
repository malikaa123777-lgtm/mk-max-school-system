from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Classroom, Grade, Role, School, Student, Subject, UserProfile

User = get_user_model()


def make_user(username, school, role):
    user = User.objects.create_user(username=username, password="pass12345")
    UserProfile.objects.create(user=user, school=school, role=role)
    return user


class SchoolApiTests(APITestCase):
    def setUp(self):
        self.school_a = School.objects.create(name="مدرسة أ")
        self.school_b = School.objects.create(name="مدرسة ب")
        self.director = make_user("director_a", self.school_a, Role.DIRECTOR)
        self.teacher = make_user("teacher_a", self.school_a, Role.TEACHER)
        self.student_user = make_user("student_a", self.school_a, Role.STUDENT)
        self.parent_user = make_user("parent_a", self.school_a, Role.PARENT)
        self.class_a = Classroom.objects.create(school=self.school_a, name="الصف الأول")
        self.class_b = Classroom.objects.create(school=self.school_b, name="الصف الأول")

    def test_requires_authentication(self):
        self.assertIn(self.client.get(reverse("classroom-list")).status_code, (401, 403))

    def test_user_sees_only_own_school_data(self):
        self.client.force_authenticate(self.director)
        response = self.client.get(reverse("classroom-list"))
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.class_a.id])

    def test_create_assigns_school_automatically(self):
        self.client.force_authenticate(self.director)
        response = self.client.post(reverse("classroom-list"), {"name": "الصف الثاني", "capacity": 25})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["school"], self.school_a.id)

    def test_duplicate_classroom_name_rejected(self):
        self.client.force_authenticate(self.director)
        response = self.client.post(reverse("classroom-list"), {"name": "الصف الأول"})
        self.assertEqual(response.status_code, 400)

    def test_cannot_link_student_to_other_school_classroom(self):
        self.client.force_authenticate(self.director)
        response = self.client.post(
            reverse("student-list"), {"full_name": "أحمد", "classroom": self.class_b.id}
        )
        self.assertEqual(response.status_code, 400)

    def test_teacher_cannot_delete(self):
        self.client.force_authenticate(self.teacher)
        response = self.client.delete(reverse("classroom-detail", args=[self.class_a.id]))
        self.assertEqual(response.status_code, 403)

    def test_director_can_delete(self):
        self.client.force_authenticate(self.director)
        response = self.client.delete(reverse("classroom-detail", args=[self.class_a.id]))
        self.assertEqual(response.status_code, 204)

    def test_grade_score_cannot_exceed_max(self):
        student = Student.objects.create(school=self.school_a, full_name="سارة")
        subject = Subject.objects.create(school=self.school_a, name="رياضيات")
        self.client.force_authenticate(self.teacher)
        response = self.client.post(
            reverse("grade-list"),
            {"student": student.id, "subject": subject.id, "exam_name": "نصفي", "score": 120, "max_score": 100},
        )
        self.assertEqual(response.status_code, 400)

    def test_attendance_unique_per_day(self):
        student = Student.objects.create(school=self.school_a, full_name="سارة")
        self.client.force_authenticate(self.teacher)
        payload = {"student": student.id, "date": "2026-09-28", "status": "present"}
        self.assertEqual(self.client.post(reverse("attendance-list"), payload).status_code, 201)
        self.assertEqual(self.client.post(reverse("attendance-list"), payload).status_code, 400)

    def test_invalid_filter_value_returns_400(self):
        self.client.force_authenticate(self.director)
        response = self.client.get(reverse("student-list"), {"classroom": "abc"})
        self.assertEqual(response.status_code, 400)

    def test_only_superuser_can_create_school(self):
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(reverse("school-list"), {"name": "جديدة"}).status_code, 403)

    def test_director_can_update_own_school(self):
        self.client.force_authenticate(self.director)
        response = self.client.patch(
            reverse("school-detail", args=[self.school_a.id]), {"phone": "0912345678"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["phone"], "0912345678")

    def test_director_cannot_rename_or_deactivate_school(self):
        self.client.force_authenticate(self.director)
        response = self.client.patch(
            reverse("school-detail", args=[self.school_a.id]),
            {"name": "اسم جديد", "is_active": False},
        )
        self.assertEqual(response.status_code, 200)
        self.school_a.refresh_from_db()
        self.assertEqual(self.school_a.name, "مدرسة أ")
        self.assertTrue(self.school_a.is_active)

    def test_director_cannot_update_other_school(self):
        self.client.force_authenticate(self.director)
        response = self.client.patch(
            reverse("school-detail", args=[self.school_b.id]), {"phone": "0900000000"}
        )
        self.assertEqual(response.status_code, 404)  # غير ظاهرة له أصلاً (مُصفّاة بالاستعلام)

    # --- وصول الطالب وولي الأمر لسجلاتهم فقط ---

    def test_student_sees_only_own_record(self):
        own = Student.objects.create(school=self.school_a, full_name="أنا", user=self.student_user)
        Student.objects.create(school=self.school_a, full_name="غيري")
        self.client.force_authenticate(self.student_user)
        response = self.client.get(reverse("student-list"))
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [own.id])

    def test_student_cannot_write(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.post(reverse("student-list"), {"full_name": "محاولة"})
        self.assertEqual(response.status_code, 403)

    def test_parent_sees_only_linked_children_grades(self):
        child = Student.objects.create(school=self.school_a, full_name="ابني")
        other = Student.objects.create(school=self.school_a, full_name="غيره")
        child.guardians.add(self.parent_user)
        subject = Subject.objects.create(school=self.school_a, name="رياضيات")
        Grade.objects.create(student=child, subject=subject, exam_name="نصفي", score=80)
        Grade.objects.create(student=other, subject=subject, exam_name="نصفي", score=90)
        self.client.force_authenticate(self.parent_user)
        response = self.client.get(reverse("grade-list"))
        self.assertEqual(response.status_code, 200)
        student_ids = {row["student"] for row in response.data["results"]}
        self.assertEqual(student_ids, {child.id})

    def test_parent_cannot_write_grades(self):
        child = Student.objects.create(school=self.school_a, full_name="ابني")
        child.guardians.add(self.parent_user)
        subject = Subject.objects.create(school=self.school_a, name="رياضيات")
        self.client.force_authenticate(self.parent_user)
        response = self.client.post(
            reverse("grade-list"),
            {"student": child.id, "subject": subject.id, "exam_name": "نصفي", "score": 80},
        )
        self.assertEqual(response.status_code, 403)

    # --- /api/auth/me/ ---

    def test_me_endpoint_returns_role_and_school(self):
        self.client.force_authenticate(self.teacher)
        response = self.client.get(reverse("api-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], Role.TEACHER)
        self.assertEqual(response.data["school"]["id"], self.school_a.id)

    def test_me_endpoint_lists_parent_children(self):
        child = Student.objects.create(school=self.school_a, full_name="ابني")
        child.guardians.add(self.parent_user)
        self.client.force_authenticate(self.parent_user)
        response = self.client.get(reverse("api-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["children_ids"], [child.id])

    # --- تسجيل الدخول عبر JWT ---

    def test_jwt_login_returns_access_and_refresh(self):
        response = self.client.post(
            reverse("api-token"), {"username": "director_a", "password": "pass12345"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_jwt_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("api-token"), {"username": "director_a", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 401)
