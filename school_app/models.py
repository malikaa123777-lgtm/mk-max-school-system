from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class School(TimeStampedModel):
    name = models.CharField("اسم المدرسة", max_length=255, unique=True)
    address = models.TextField("العنوان", blank=True)
    phone = models.CharField("الهاتف", max_length=30, blank=True)
    is_active = models.BooleanField("مفعّلة", default=True)
    logo = models.ImageField("الشعار", upload_to="schools/logos/", null=True, blank=True)
    background = models.ImageField(
        "الخلفية", upload_to="schools/backgrounds/", null=True, blank=True
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "مدرسة"
        verbose_name_plural = "المدارس"

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    DIRECTOR = "director", "مدير المدرسة"
    TEACHER = "teacher", "معلم"
    STUDENT = "student", "طالب"
    PARENT = "parent", "ولي أمر"


class UserProfile(TimeStampedModel):
    """يربط المستخدم بمدرسة ودور. مدير النظام العام هو superuser."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="profile", on_delete=models.CASCADE
    )
    school = models.ForeignKey(
        School, related_name="members", null=True, blank=True, on_delete=models.PROTECT
    )
    role = models.CharField("الدور", max_length=20, choices=Role.choices, default=Role.STUDENT)

    class Meta:
        verbose_name = "ملف مستخدم"
        verbose_name_plural = "ملفات المستخدمين"

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"


class Classroom(TimeStampedModel):
    school = models.ForeignKey(School, related_name="classrooms", on_delete=models.PROTECT)
    name = models.CharField("اسم الصف", max_length=100)
    capacity = models.PositiveIntegerField("السعة", default=30, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["school", "name"]
        verbose_name = "صف"
        verbose_name_plural = "الصفوف"
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_classroom_name_per_school")
        ]

    def __str__(self):
        return f"{self.name} - {self.school.name}"


class Subject(TimeStampedModel):
    school = models.ForeignKey(School, related_name="subjects", on_delete=models.PROTECT)
    name = models.CharField("المادة", max_length=100)

    class Meta:
        ordering = ["school", "name"]
        verbose_name = "مادة"
        verbose_name_plural = "المواد"
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_subject_name_per_school")
        ]

    def __str__(self):
        return self.name


class Teacher(TimeStampedModel):
    school = models.ForeignKey(School, related_name="teachers", on_delete=models.PROTECT)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="teacher_record",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    full_name = models.CharField("الاسم الكامل", max_length=255)
    phone = models.CharField("الهاتف", max_length=30, blank=True)
    subjects = models.ManyToManyField(Subject, related_name="teachers", blank=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "معلم"
        verbose_name_plural = "المعلمون"

    def __str__(self):
        return self.full_name


class Student(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "M", "ذكر"
        FEMALE = "F", "أنثى"

    school = models.ForeignKey(School, related_name="students", on_delete=models.PROTECT)
    classroom = models.ForeignKey(
        Classroom, related_name="students", null=True, blank=True, on_delete=models.SET_NULL
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="student_record",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    guardians = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="children",
        blank=True,
        help_text="حسابات أولياء الأمور المرتبطة بهذا الطالب",
    )
    full_name = models.CharField("الاسم الكامل", max_length=255)
    gender = models.CharField("الجنس", max_length=1, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField("تاريخ الميلاد", null=True, blank=True)
    guardian_name = models.CharField("ولي الأمر", max_length=255, blank=True)
    guardian_phone = models.CharField("هاتف ولي الأمر", max_length=30, blank=True)
    enrolled_on = models.DateField("تاريخ التسجيل", default=timezone.localdate)
    is_active = models.BooleanField("على رأس الدراسة", default=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "طالب"
        verbose_name_plural = "الطلاب"

    def __str__(self):
        return self.full_name


class Grade(TimeStampedModel):
    student = models.ForeignKey(Student, related_name="grades", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, related_name="grades", on_delete=models.PROTECT)
    exam_name = models.CharField("الامتحان", max_length=100)
    score = models.DecimalField("الدرجة", max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    max_score = models.DecimalField(
        "الدرجة العظمى", max_digits=5, decimal_places=2, default=100, validators=[MinValueValidator(0)]
    )
    exam_date = models.DateField("تاريخ الامتحان", default=timezone.localdate)

    class Meta:
        ordering = ["-exam_date", "student"]
        verbose_name = "درجة"
        verbose_name_plural = "الدرجات"
        constraints = [
            models.CheckConstraint(condition=Q(max_score__gt=0), name="grade_max_score_positive"),
            models.CheckConstraint(condition=Q(score__lte=F("max_score")), name="grade_score_lte_max"),
        ]

    def __str__(self):
        return f"{self.student} - {self.subject}: {self.score}/{self.max_score}"


class Attendance(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        ABSENT = "absent", "غائب"
        LATE = "late", "متأخر"
        EXCUSED = "excused", "غياب بعذر"

    student = models.ForeignKey(Student, related_name="attendance_records", on_delete=models.CASCADE)
    date = models.DateField("التاريخ", default=timezone.localdate)
    status = models.CharField("الحالة", max_length=10, choices=Status.choices, default=Status.PRESENT)
    note = models.CharField("ملاحظة", max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "student"]
        verbose_name = "حضور"
        verbose_name_plural = "سجل الحضور"
        constraints = [
            models.UniqueConstraint(fields=["student", "date"], name="uniq_attendance_per_student_day")
        ]

    def __str__(self):
        return f"{self.student} - {self.date}: {self.get_status_display()}"
