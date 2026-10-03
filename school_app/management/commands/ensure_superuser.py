import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """ينشئ مدير نظام (superuser) تلقائيًا من متغيرات البيئة عند النشر، إن لم يكن موجودًا.
    آمن للتشغيل في كل عملية نشر (idempotent) — لا يكرر الإنشاء ولا يفشل إذا كان المستخدم موجوداً.
    مفيد على منصات الاستضافة التي لا تتيح وصول shell تفاعلي (مثل Render على الخطة المجانية)."""

    help = "ينشئ مدير نظام تلقائيًا من DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD إن لم يكن موجوداً."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                "تخطّي إنشاء مدير النظام: اضبط DJANGO_SUPERUSER_USERNAME و DJANGO_SUPERUSER_PASSWORD "
                "كمتغيرات بيئة إذا أردت إنشاءه تلقائيًا عند النشر."
            ))
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(f"مدير النظام '{username}' موجود مسبقاً — لا تغيير."))
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"تم إنشاء مدير النظام '{username}' بنجاح."))
