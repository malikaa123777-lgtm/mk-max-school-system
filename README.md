# نظام إدارة المدارس (Django + DRF)

واجهة برمجية (API) متعددة المدارس — كل مدرسة بياناتها معزولة تمامًا عن غيرها، بأربعة أدوار:
مدير النظام (superuser) ← مدير المدرسة ← المعلم ← الطالب/ولي الأمر (قراءة فقط لسجلاتهم الخاصة).

## التشغيل محليًا
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # عدّل DJANGO_SECRET_KEY على الأقل
python manage.py makemigrations school_app
python manage.py migrate
python manage.py createsuperuser  # هذا هو مدير النظام العام
python manage.py test             # يفترض تنجح كل الاختبارات
python manage.py runserver
```

## المصادقة (JWT)
```
POST /api/auth/token/            { "username": "...", "password": "..." }
→ { "access": "...", "refresh": "..." }
```
أرسل التوكن في كل طلب: `Authorization: Bearer <access>`
التوكن القصير (`access`) صالح 8 ساعات. عند انتهائه:
```
POST /api/auth/token/refresh/    { "refresh": "..." }
→ { "access": "..." }
```
كل تجديد يُبطل توكن التجديد القديم تلقائيًا (rotation + blacklist).

## من أنا؟
```
GET /api/auth/me/
```
يرجّع الدور والمدرسة، بالإضافة لـ `student_id` (للطالب) أو `children_ids` (لولي الأمر) أو
`teacher_id` (للمعلم) — الواجهة الأمامية تحتاج هذا مباشرة بعد تسجيل الدخول.

## المسارات
`/api/schools/ classrooms/ subjects/ teachers/ students/ grades/ attendance/`
كلها تدعم `?search=` و `?ordering=` والترقيم `?page=`، وبعضها تصفية مثل `?classroom=1&is_active=true`.

## الصلاحيات
| الدور | القراءة | الكتابة | الحذف | النطاق |
|---|---|---|---|---|
| مدير النظام | الكل | الكل | الكل | كل المدارس |
| مدير المدرسة | مدرسته | مدرسته (+ تعديل بيانات مدرسته نفسها، عدا الاسم والتفعيل) | مدرسته | مدرسة واحدة |
| المعلم | مدرسته | مدرسته | ممنوع | مدرسة واحدة |
| الطالب | سجله فقط (بياناته، درجاته، حضوره) | ممنوع | ممنوع | نفسه فقط |
| ولي الأمر | سجلات أبنائه المرتبطين فقط | ممنوع | ممنوع | أبناؤه فقط |

لإنشاء مدرسة جديدة: فقط مدير النظام (عبر لوحة الأدمن أو `POST /api/schools/`).
مدير المدرسة يقدر لاحقًا يرفع شعار وخلفية مدرسته بنفسه عبر `PATCH /api/schools/<id>/`
(حقلا `logo` و`background`، كملفات multipart/form-data).

## ربط المستخدمين بالمدرسة والدور
كل حساب دخول يحتاج "ملف مستخدم" (UserProfile) يربطه بمدرسة ودور — يُضاف من لوحة الأدمن:
- **مدير/معلم**: أنشئ المستخدم ثم أضف له UserProfile بالدور المناسب.
- **طالب**: أنشئ المستخدم، أضف UserProfile بدور "طالب"، ثم من صفحة الطالب (Student) اربط
  حقل "حساب الدخول" (`user`) بنفس هذا المستخدم.
- **ولي أمر**: أنشئ المستخدم، أضف UserProfile بدور "ولي أمر"، ثم من صفحة كل طالب أضف هذا
  المستخدم لحقل "أولياء الأمور" (`guardians`) — يمكن ربط أكثر من طالب (إخوة) بنفس الحساب.

## رفع الملفات (الشعار والخلفية)
محليًا تُخدم الملفات المرفوعة تلقائيًا أثناء التطوير (`DJANGO_DEBUG=1`).
في الإنتاج: Whitenoise يخدم الملفات الثابتة (CSS/JS) فقط، وليس الوسائط المرفوعة — يجب أن
يخدم مجلد `media/` إما الخادم نفسه (nginx) أو خدمة تخزين سحابية (مثل S3)، حسب منصة النشر.

## الواجهة الأمامية (CORS)
إذا كانت الواجهة الأمامية (موقع/تطبيق) على نطاق مختلف عن الـ API، اضبط في `.env`:
```
CORS_ALLOWED_ORIGINS=https://app.example.com
```
محليًا (`DJANGO_DEBUG=1`) مفعّل تلقائيًا السماح لأي نطاق لتسهيل التطوير فقط.

## قاعدة البيانات
الافتراضي SQLite — يعمل تمام لمدرسة أو عدة مدارس بحمل متوسط، بدون أي إعداد إضافي.
للانتقال إلى PostgreSQL (موصى به لعدد كبير من المستخدمين المتزامنين) بدون تعديل أي كود:
```
DATABASE_URL=postgres://user:password@host:5432/dbname
```

## النشر على Render (خطوة بخطوة، من الجوال بالكامل)

⚠️ **مهم قبل البدء**: قاعدة بيانات Render المجانية (PostgreSQL) تُحذف نهائيًا بعد 30 يومًا من إنشائها
ما لم تدفع لترقيتها — خطر حقيقي ببيانات طلاب فعليين. الحل: استخدم **Neon** (قاعدة بيانات PostgreSQL
مجانية تبقى بدون انتهاء) مع **Render** للخادم نفسه (مجاني أيضًا). الخطوات تالياً تستخدم هذا المزيج.

ملاحظة ثانية: الخدمة المجانية على Render "تنام" بعد 15 دقيقة بدون طلبات، وتحتاج نحو دقيقة
لتستيقظ عند أول طلب جديد — مقبول لمرحلة تجربة/إطلاق أولي، لكن إذا احتجت الموقع يستجيب فورًا
طول الوقت، هذا يتطلب خطة مدفوعة لاحقًا ($7/شهر تقريبًا).

### ١. ارفع الكود إلى GitHub (عبر Termux)
```bash
cd school_project
pkg install git
git init
git add .
git commit -m "نسخة أولى جاهزة للنشر"
```
أنشئ مستودع فارغ جديد من موقع GitHub (عبر متصفح الجوال: github.com → New repository)، ثم:
```bash
git remote add origin https://github.com/<اسمك>/<اسم-المستودع>.git
git branch -M main
git push -u origin main
```
(سيطلب منك GitHub اسم المستخدم و Personal Access Token بدل كلمة المرور — تولّده من
Settings → Developer settings → Personal access tokens في حساب GitHub).

### ٢. أنشئ قاعدة بيانات مجانية على Neon
من neon.tech (عبر متصفح الجوال): أنشئ حساب → New Project → انسخ "Connection string"
(يبدأ بـ `postgres://` أو `postgresql://`) — هذا هو `DATABASE_URL`.

### ٣. أنشئ الخدمة على Render
من render.com: أنشئ حساب (اربطه بحساب GitHub) → **New → Blueprint** → اختر المستودع اللي رفعته.
Render سيقرأ ملف `render.yaml` الموجود بالمشروع تلقائيًا ويجهّز كل شيء تقريبًا بنفسه.
قبل الضغط على Apply، املأ الحقول المطلوبة يدويًا:
- `DATABASE_URL`: الصقه من Neon (خطوة ٢)
- `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD`:
  بيانات حساب مدير النظام الذي سيُنشأ تلقائيًا عند أول نشر

### ٤. بعد اكتمال النشر
Render يعطيك رابط مثل `https://school-system-api.onrender.com`. جرّب:
```
POST https://school-system-api.onrender.com/api/auth/token/
{ "username": "<اللي حطيته بـ DJANGO_SUPERUSER_USERNAME>", "password": "..." }
```
لو رجّع `access` و`refresh`، النظام شغّال فعليًا على الإنترنت.

### ٥. بعد التأكد إنه شغّال
احذف متغيرات `DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD` من إعدادات Render (مو إلزامي، لكن
أفضل أمنيًا) بما إن مدير النظام صار موجود فعليًا ولا حاجة لإبقائها.

## النشر الفعلي (إنتاج) — يدويًا على أي منصة أخرى
```bash
export DJANGO_DEBUG=0
python manage.py collectstatic --noinput
gunicorn school_system.wsgi:application --bind 0.0.0.0:8000
```
تأكد قبل النشر من:
- `DJANGO_SECRET_KEY` قيمة عشوائية طويلة فعلية (لا القيمة الافتراضية).
- `DJANGO_ALLOWED_HOSTS` يحتوي نطاقك الحقيقي.
- `CORS_ALLOWED_ORIGINS` يحتوي نطاق الواجهة الأمامية فقط (لا تتركه فارغًا ولا تفتحه للجميع).
- المشروع خلف HTTPS فعليًا (الإعدادات تفرض كوكيز آمنة وإعادة توجيه HTTPS تلقائيًا خارج وضع DEBUG).
