# webapp/views.py
from __future__ import annotations

# Imports
from urllib.parse import unquote
from datetime import datetime, timezone as dt_timezone
from django.conf import settings
from .models import AIStatHelperReport
from .ai_stat_helper import build_ai_stat_snapshot, generate_ai_stat_report, snapshot_hash
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Prefetch, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from django.views.decorators.http import require_http_methods
import hashlib, json

from .auth_utils import login_user, logout_user, require_role
from .models import (
    AdaptiveAttempt,
    AdaptiveAttemptAnswer,
    AdaptiveQuestion,
    Answers,
    Groups,
    Profiles,
    Questions,
    StudentsGroups,
    Testattempts,
    Tests,
    TestSchedule,
    Topics,
    Useranswers,
    Users,
)

# Константы
BASIC_TESTS = [
    {"code": "python-basics", "title": "Python Basics"},
    {"code": "logic-structures", "title": "Logic and Data Structures"},
    {"code": "files-exceptions-functions", "title": "Files, Exceptions, Functions"},
]

TOPIC_TITLES = {x["code"]: x["title"] for x in BASIC_TESTS}

DIFFICULTY_MAP = {
    "Beginner": "easy",
    "Medium": "medium",
    "Hard": "hard",
}

LEVEL_NAME = {1: "Beginner", 2: "Medium", 3: "Advanced"}

TEST_LEN = 10
TIME_LIMIT_SEC = 10 * 60


# Общие helpers
def normalize_topic_difficulty(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return DIFFICULTY_MAP.get(raw, raw)


def _aware(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt



def _attempt_duration_sec(attempt: Testattempts) -> int | None:
    tl = attempt.test.time_limit  # минуты
    if not tl:
        return None
    tl = int(tl)
    if tl <= 0:
        return None
    return tl * 60


def _attempt_remaining_sec(attempt: Testattempts) -> int | None:
    started = attempt.started_at
    if started is None:
        started = timezone.now()
    elif timezone.is_naive(started):
        started = timezone.make_aware(started, dt_timezone.utc)

    duration = _attempt_duration_sec(attempt)
    if duration is None:
        return None

    now = timezone.now()
    elapsed = int((now - started).total_seconds())
    return max(0, duration - elapsed)


# Главная / Auth
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "webapp/index.html")


def login_as(request: HttpRequest) -> HttpResponse:
    return render(request, "webapp/login_role.html")


@require_http_methods(["GET", "POST"])
def teacher_login(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        user = Users.objects.filter(username=username, role="teacher").first()
        if not user or not check_password(password, user.password_hash):
            return render(request, "webapp/teacher_login.html", {"error": "Wrong login or password"})

        login_user(request, user)
        return redirect("teacher_menu")

    return render(request, "webapp/teacher_login.html")


@require_http_methods(["GET", "POST"])
def teacher_register(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""

        if not username or not email or not password:
            return render(request, "webapp/teacher_register.html", {"error": "Fill all fields"})

        if Users.objects.filter(username=username).exists():
            return render(request, "webapp/teacher_register.html", {"error": "Username already exists"})

        if Users.objects.filter(email=email).exists():
            return render(request, "webapp/teacher_register.html", {"error": "Email already exists"})

        try:
            with transaction.atomic():
                user = Users.objects.create(
                    username=username,
                    email=email,
                    password_hash=make_password(password),
                    role="teacher",
                )
                Profiles.objects.get_or_create(
                    user=user,
                    defaults=dict(
                        total_tests_passed=0,
                        avg_score=0,
                        total_correct_answers=0,
                        total_time_spent=0,
                        tests_created=0,
                        groups_managed=0,
                        students_total=0,
                    ),
                )
        except IntegrityError:
            return render(request, "webapp/teacher_register.html", {"error": "Database error (unique / constraints)"})

        login_user(request, user)
        return redirect("teacher_menu")

    return render(request, "webapp/teacher_register.html")


@require_http_methods(["GET", "POST"])
def student_login(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        login_value = (request.POST.get("username") or request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""

        if not login_value or not password:
            return render(request, "webapp/student_login.html", {"error": "Fill all fields"})

        user = (
            Users.objects.filter(role="student", email=login_value).first()
            or Users.objects.filter(role="student", username=login_value).first()
        )

        if not user or not check_password(password, user.password_hash):
            return render(request, "webapp/student_login.html", {"error": "Wrong login or password"})

        login_user(request, user)
        return redirect("student_menu")

    return render(request, "webapp/student_login.html")


@require_http_methods(["GET", "POST"])
def student_register(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""

        if not username or not email or not password:
            return render(request, "webapp/student_register.html", {"error": "Fill all fields"})

        if Users.objects.filter(username=username).exists():
            return render(request, "webapp/student_register.html", {"error": "Username already exists"})

        if Users.objects.filter(email=email).exists():
            return render(request, "webapp/student_register.html", {"error": "Email already exists"})

        try:
            with transaction.atomic():
                user = Users.objects.create(
                    username=username,
                    email=email,
                    password_hash=make_password(password),
                    role="student",
                )
                Profiles.objects.get_or_create(
                    user=user,
                    defaults=dict(
                        total_tests_passed=0,
                        avg_score=0,
                        total_correct_answers=0,
                        total_time_spent=0,
                        tests_created=0,
                        groups_managed=0,
                        students_total=0,
                    ),
                )
        except IntegrityError:
            return render(request, "webapp/student_register.html", {"error": "Database error (unique/constraints)"})

        login_user(request, user)
        return redirect("student_menu")

    return render(request, "webapp/student_register.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    logout_user(request)
    return redirect("login_as")


# Меню / Настройки
@require_role("teacher")
def teacher_menu(request: HttpRequest) -> HttpResponse:
    return render(request, "webapp/teacher_menu.html", {"user": request.current_user})


@require_role("student")
def student_menu(request: HttpRequest) -> HttpResponse:
    return render(request, "webapp/student_menu.html", {"user": request.current_user})


@require_role("teacher", "student")
def settings_view(request):
    lang = request.GET.get("lang")
    supported = {code for code, _ in settings.LANGUAGES}

    if lang in supported:
        request.session["django_language"] = lang
        translation.activate(lang)
        return redirect("settings")

    current_lang = translation.get_language() or "en"

    role = request.current_user.role
    back_url = "teacher_menu" if role == "teacher" else "student_menu"

    return render(request, "webapp/settings.html", {
        "lang": current_lang,
        "back_url": back_url,
    })

@require_role("teacher", "student")
@require_http_methods(["GET", "POST"])
def change_profile_data(request: HttpRequest) -> HttpResponse:
    user: Users = request.current_user
    back_url = "student_menu" if user.role == "student" else "teacher_menu"

    if request.method == "GET":
        request.session.pop("cpd_verified", None)
        return render(request, "webapp/change_profile_data.html", {"step": 1, "error": None, "back_url": back_url})

    step = int(request.POST.get("step", "1") or 1)

    if step == 1:
        current_email = (request.POST.get("current_email") or "").strip()
        current_password = request.POST.get("current_password") or ""

        if not current_email or not current_password:
            return render(request, "webapp/change_profile_data.html", {"step": 1, "error": "Fill email and password", "back_url": back_url})

        if current_email.lower() != (user.email or "").lower():
            return render(request, "webapp/change_profile_data.html", {"step": 1, "error": "Current email is wrong", "back_url": back_url})

        if not check_password(current_password, user.password_hash):
            return render(request, "webapp/change_profile_data.html", {"step": 1, "error": "Current password is wrong", "back_url": back_url})

        request.session["cpd_verified"] = True
        return render(request, "webapp/change_profile_data.html", {"step": 2, "error": None, "back_url": back_url})

    if not request.session.get("cpd_verified"):
        return render(request, "webapp/change_profile_data.html", {"step": 1, "error": "Please confirm current email/password first", "back_url": back_url})

    new_email = (request.POST.get("new_email") or "").strip()
    new_password = request.POST.get("new_password") or ""

    if not new_email and not new_password:
        return render(request, "webapp/change_profile_data.html", {"step": 2, "error": "Enter new email and/or new password", "back_url": back_url})

    updates: list[str] = []

    if new_email and new_email.lower() != (user.email or "").lower():
        if Users.objects.exclude(id=user.id).filter(email__iexact=new_email).exists():
            return render(request, "webapp/change_profile_data.html", {"step": 2, "error": "This email is already taken", "back_url": back_url})
        user.email = new_email
        updates.append("email")

    if new_password:
        user.password_hash = make_password(new_password)
        updates.append("password_hash")

    with transaction.atomic():
        user.save(update_fields=updates)

    request.session.pop("cpd_verified", None)
    return redirect("settings")


# Учитель: профиль / студенты / группы
@require_role("teacher")
def teacher_profile(request: HttpRequest) -> HttpResponse:
    teacher = request.current_user
    profile = Profiles.objects.filter(user=teacher).first()
    tests_count = Tests.objects.filter(created_by=teacher).count()
    groups_count = Groups.objects.filter(teacher=teacher).exclude(name="UNGROUPED").count()

    return render(request, "webapp/teacher_profile.html", {
        "user": teacher,
        "profile": profile,
        "tests_count": tests_count,
        "groups_count": groups_count,
        "back_url": request.GET.get("back_url"),
    })


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def teacher_students(request: HttpRequest) -> HttpResponse:
    teacher = request.current_user

    if request.method == "POST":
        group_id = request.POST.get("group_id")
        selected_ids = request.POST.getlist("selected_students")

        if group_id and group_id.isdigit() and selected_ids:
            group = get_object_or_404(Groups, id=int(group_id), teacher=teacher)
            selected_ids_int = [int(x) for x in selected_ids if str(x).isdigit()]

            existing_links = (
                StudentsGroups.objects
                .filter(student_id__in=selected_ids_int)
                .select_related("group", "group__teacher")
            )
            link_by_student_id = {l.student_id: l for l in existing_links}

            allowed_ids: list[int] = []
            for sid in selected_ids_int:
                link = link_by_student_id.get(sid)
                if not link:
                    allowed_ids.append(sid)
                else:
                    if getattr(link.group, "teacher_id", None) == teacher.id:
                        allowed_ids.append(sid)

            if allowed_ids:
                with transaction.atomic():
                    StudentsGroups.objects.filter(
                        student_id__in=allowed_ids,
                        group__teacher=teacher,
                    ).delete()

                    for sid in allowed_ids:
                        StudentsGroups.objects.get_or_create(student_id=sid, group=group)

        return redirect("teacher_students")

    students_qs = (
        Users.objects
        .filter(role="student")
        .filter(Q(studentsgroups__isnull=True) | Q(studentsgroups__group__teacher=teacher))
        .distinct()
        .order_by("username")
    )

    groups_qs = Groups.objects.filter(teacher=teacher).order_by("name")

    links = (
        StudentsGroups.objects
        .filter(student__role="student")
        .select_related("group", "group__teacher", "student")
    )
    group_by_student_id = {link.student_id: link.group for link in links}

    students = []
    for s in students_qs:
        g = group_by_student_id.get(s.id)
        s.group = g
        s.can_manage = (g is None) or (getattr(g, "teacher_id", None) == teacher.id)
        students.append(s)

    return render(request, "webapp/teacher_students.html", {
        "user": teacher,
        "students": students,
        "groups": groups_qs,
    })


def _get_or_create_ungrouped(teacher: Users) -> Groups:
    g, _ = Groups.objects.get_or_create(teacher=teacher, name="UNGROUPED")
    return g


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def teacher_groups(request: HttpRequest) -> HttpResponse:
    teacher = request.current_user

    if request.method == "POST":
        group_id = request.POST.get("group_id")
        action = request.POST.get("action")
        selected_ids = request.POST.getlist("selected_students")

        group_id_int = int(group_id) if (group_id and group_id.isdigit()) else 0
        selected_ids_int = [int(x) for x in selected_ids if str(x).isdigit()]

        if not group_id_int or not action or not selected_ids_int:
            return redirect("teacher_groups")

        group = get_object_or_404(Groups, id=group_id_int, teacher=teacher)

        if action == "remove":
            ungrouped = _get_or_create_ungrouped(teacher)
            with transaction.atomic():
                StudentsGroups.objects.filter(
                    student_id__in=selected_ids_int,
                    group__teacher=teacher,
                ).delete()

                for sid in selected_ids_int:
                    StudentsGroups.objects.get_or_create(student_id=sid, group=ungrouped)

            return redirect(f"{request.path}?group_id={ungrouped.id}")

        if action == "restore":
            target_group_id = request.POST.get("target_group_id")
            target_id = int(target_group_id) if (target_group_id and target_group_id.isdigit()) else 0
            if not target_id:
                return redirect(f"{request.path}?group_id={group.id}")

            target = get_object_or_404(Groups, id=target_id, teacher=teacher)

            with transaction.atomic():
                StudentsGroups.objects.filter(
                    student_id__in=selected_ids_int,
                    group__teacher=teacher,
                    group__name="UNGROUPED",
                ).delete()

                for sid in selected_ids_int:
                    StudentsGroups.objects.get_or_create(student_id=sid, group=target)

            return redirect(f"{request.path}?group_id={target.id}")

        return redirect("teacher_groups")

    groups = (
        Groups.objects
        .filter(teacher=teacher)
        .annotate(students_count=Count("studentsgroups"))
        .order_by("name")
        .prefetch_related("studentsgroups_set__student")
    )

    gid = request.GET.get("group_id")
    active_group = None
    if gid and gid.isdigit():
        active_group = groups.filter(id=int(gid)).first()
    if not active_group:
        active_group = groups.first() if groups else None

    return render(request, "webapp/teacher_groups.html", {
        "user": teacher,
        "groups": groups,
        "active_group": active_group,
    })


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def create_group(request: HttpRequest) -> HttpResponse:
    teacher = request.current_user

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            return render(request, "webapp/create_group.html", {
                "teacher_name": teacher.username,
                "name": name,
                "error": "Enter group name",
            })

        Groups.objects.create(name=name, teacher_id=teacher.id)
        return redirect("teacher_groups")

    return render(request, "webapp/create_group.html", {"teacher_name": teacher.username, "name": ""})


# Учитель: тесты / конструктор / расписание
@require_role("teacher")
@require_http_methods(["GET", "POST"])
def teacher_tests(request: HttpRequest) -> HttpResponse:
    teacher = request.current_user

    if request.method == "POST":
        action = request.POST.get("action")
        test_id = request.POST.get("test_id", "")
        if action == "delete" and test_id.isdigit():
            Tests.objects.filter(id=int(test_id), created_by_id=teacher.id).delete()
            return redirect("teacher_tests")

    schedules_qs = (
        TestSchedule.objects
        .select_related("group")
        .filter(group__teacher=teacher)
        .order_by("scheduled_at")
    )

    tests = (
        Tests.objects
        .filter(created_by_id=teacher.id)
        .select_related("topic")
        .annotate(questions_count=Count("questions"))
        .prefetch_related(Prefetch("schedules", queryset=schedules_qs))
        .order_by("-id")
    )

    return render(request, "webapp/teacher_tests.html", {"user": teacher, "tests": tests})


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def create_test(request: HttpRequest) -> HttpResponse:
    teacher: Users = request.current_user
    topics = Topics.objects.order_by("name")

    if request.method == "POST":
        title = (request.POST.get("name") or "").strip()
        topic_id = request.POST.get("topic")
        difficulty = (request.POST.get("difficulty") or "").strip()
        time_limit_raw = request.POST.get("time_limit")

        if not title or not topic_id or not difficulty:
            return render(request, "webapp/create_test.html", {"topics": topics, "error": "Fill all fields"})

        topic = get_object_or_404(Topics, id=topic_id)

        time_limit = None
        if time_limit_raw and str(time_limit_raw).isdigit():
            tl = int(time_limit_raw)
            time_limit = tl if tl > 0 else None

        test = Tests.objects.create(
            title=title,
            topic=topic,
            difficulty=difficulty,
            time_limit=time_limit,
            created_by=teacher,
        )
        return redirect("add_questions", test_id=test.id)

    return render(request, "webapp/create_test.html", {"topics": topics})


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def add_questions(request: HttpRequest, test_id: int) -> HttpResponse:
    teacher: Users = request.current_user
    test = get_object_or_404(Tests, id=test_id, created_by=teacher)

    if request.method == "POST":
        action = request.POST.get("action") or "add"
        if action == "finish":
            return redirect("test_preview", test_id=test.id)

        question_text = (request.POST.get("question") or "").strip()
        correct = int(request.POST.get("correct") or 1)

        answers_text = [
            (request.POST.get("answer1") or "").strip(),
            (request.POST.get("answer2") or "").strip(),
            (request.POST.get("answer3") or "").strip(),
            (request.POST.get("answer4") or "").strip(),
        ]

        if not question_text or any(not a for a in answers_text):
            questions = Questions.objects.filter(test=test).order_by("id")
            return render(request, "webapp/add_questions.html", {
                "test": test,
                "questions": questions,
                "error": "Fill question and all answers",
            })

        if correct not in (1, 2, 3, 4):
            correct = 1

        with transaction.atomic():
            q = Questions.objects.create(
                test=test,
                question_text=question_text,
                difficulty=test.difficulty,
                type="single_choice",
                time_limit=test.time_limit,
            )

            for i, txt in enumerate(answers_text, start=1):
                Answers.objects.create(question=q, answer_text=txt, is_correct=(i == correct))

        return redirect("add_questions", test_id=test.id)

    questions = (
        Questions.objects
        .filter(test=test)
        .prefetch_related("answers_set")
        .order_by("id")
    )

    return render(request, "webapp/add_questions.html", {"test": test, "questions": questions})


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def test_preview(request: HttpRequest, test_id: int) -> HttpResponse:
    teacher: Users = request.current_user
    test = get_object_or_404(Tests, id=test_id, created_by=teacher)

    questions = (
        Questions.objects
        .filter(test=test)
        .prefetch_related("answers_set")
        .order_by("id")
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "main":
            return redirect("teacher_menu")
        if action == "my_tests":
            return redirect("teacher_tests")
        return redirect("teacher_menu")

    return render(request, "webapp/test_preview.html", {"test": test, "questions": questions})


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def edit_question(request: HttpRequest, question_id: int) -> HttpResponse:
    teacher: Users = request.current_user
    question = get_object_or_404(Questions, id=question_id)

    if question.test.created_by_id != teacher.id:
        return redirect("teacher_menu")

    answers = list(Answers.objects.filter(question=question).order_by("id"))

    if request.method == "POST":
        new_text = (request.POST.get("question_text") or "").strip()
        correct_index = int(request.POST.get("correct_index") or 0)

        if new_text:
            question.question_text = new_text
            question.save(update_fields=["question_text"])

        for idx, ans in enumerate(answers):
            ans_text = (request.POST.get(f"answer_text_{idx}") or "").strip()
            if ans_text:
                ans.answer_text = ans_text
            ans.is_correct = (idx == correct_index)
            ans.save(update_fields=["answer_text", "is_correct"])

        return redirect("test_preview", test_id=question.test_id)

    return render(request, "webapp/edit_question.html", {"question": question, "answers": answers})


@require_role("teacher")
@require_http_methods(["POST", "GET"])
def delete_question(request: HttpRequest, question_id: int) -> HttpResponse:
    teacher: Users = request.current_user
    question = get_object_or_404(Questions, id=question_id)

    if question.test.created_by_id != teacher.id:
        return redirect("teacher_menu")

    test_id = question.test_id
    with transaction.atomic():
        Answers.objects.filter(question=question).delete()
        question.delete()

    return redirect("test_preview", test_id=test_id)


@require_role("teacher")
@require_http_methods(["POST", "GET"])
def delete_test(request: HttpRequest, test_id: int) -> HttpResponse:
    teacher: Users = request.current_user
    test = get_object_or_404(Tests, id=test_id, created_by=teacher)

    with transaction.atomic():
        q_ids = list(Questions.objects.filter(test=test).values_list("id", flat=True))
        Answers.objects.filter(question_id__in=q_ids).delete()
        Questions.objects.filter(id__in=q_ids).delete()
        test.delete()

    return redirect("teacher_tests")


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def schedule_test(request: HttpRequest, test_id: int) -> HttpResponse:
    teacher = request.current_user

    test = get_object_or_404(Tests, id=test_id, created_by=teacher)
    groups = Groups.objects.filter(teacher=teacher).order_by("name")

    existing = (
        TestSchedule.objects.select_related("group")
        .filter(test=test)
        .first()
    )

    if request.method == "POST":
        group_id = (request.POST.get("group_id") or "").strip()
        scheduled_at_raw = (request.POST.get("scheduled_at") or "").strip()

        if not group_id.isdigit():
            return render(request, "webapp/schedule_test.html", {"user": teacher, "test": test, "groups": groups, "existing": existing, "error": "Choose group"})

        if not scheduled_at_raw:
            return render(request, "webapp/schedule_test.html", {"user": teacher, "test": test, "groups": groups, "existing": existing, "error": "Choose date & time"})

        group = Groups.objects.filter(id=int(group_id), teacher=teacher).first()
        if not group:
            return render(request, "webapp/schedule_test.html", {"user": teacher, "test": test, "groups": groups, "existing": existing, "error": "Invalid group"})

        dt = datetime.fromisoformat(scheduled_at_raw)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())

        with transaction.atomic():
            TestSchedule.objects.update_or_create(test=test, group=group, defaults={"scheduled_at": dt})

        return redirect("teacher_tests")

    return render(request, "webapp/schedule_test.html", {"user": teacher, "test": test, "groups": groups, "existing": existing})


# Учитель: темы (Topics)
@require_role("teacher")
@require_http_methods(["GET"])
def topics_list(request: HttpRequest) -> HttpResponse:
    topics = Topics.objects.order_by("id")
    return render(request, "webapp/topics_list.html", {"topics": topics, "back_url": "teacher_menu"})


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def topic_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        difficulty_raw = request.POST.get("difficulty")
        difficulty = normalize_topic_difficulty(difficulty_raw)

        if not name:
            return render(request, "webapp/topic_form.html", {"mode": "create", "error": "Fill topic name"})

        try:
            Topics.objects.create(name=name, difficulty=difficulty)
        except IntegrityError:
            return render(request, "webapp/topic_form.html", {"mode": "create", "error": f"Invalid difficulty: {difficulty_raw}"})

        return redirect("topics_list")

    return render(request, "webapp/topic_form.html", {"mode": "create"})


@require_role("teacher")
@require_http_methods(["GET", "POST"])
def topic_edit(request: HttpRequest, topic_id: int) -> HttpResponse:
    topic = get_object_or_404(Topics, id=topic_id)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        difficulty_raw = request.POST.get("difficulty")
        difficulty = normalize_topic_difficulty(difficulty_raw)

        if not name:
            return render(request, "webapp/topic_form.html", {"mode": "edit", "topic": topic, "error": "Fill topic name"})

        topic.name = name
        topic.difficulty = difficulty

        try:
            topic.save()
        except IntegrityError:
            return render(request, "webapp/topic_form.html", {"mode": "edit", "topic": topic, "error": f"Invalid difficulty: {difficulty_raw}"})

        return redirect("topics_list")

    return render(request, "webapp/topic_form.html", {"mode": "edit", "topic": topic})


@require_role("teacher")
@require_http_methods(["POST", "GET"])
def topic_delete(request: HttpRequest, topic_id: int) -> HttpResponse:
    topic = get_object_or_404(Topics, id=topic_id)

    try:
        topic.delete()
    except Exception:
        topics = Topics.objects.order_by("id")
        return render(request, "webapp/topics_list.html", {
            "topics": topics,
            "error": "Cannot delete topic: it is used in tests",
            "back_url": "teacher_menu",
        })

    return redirect("topics_list")


# Учитель: статистика
@require_role("teacher")
@require_http_methods(["GET", "POST"])
def teacher_statistics(request: HttpRequest) -> HttpResponse:
    teacher = request.current_user
    data = request.POST if request.method == "POST" else request.GET

    draft_test = (data.get("test") or "all").strip()
    draft_group = (data.get("group") or "all").strip()
    draft_student = (data.get("student") or "all").strip()
    apply_filters = (data.get("apply") or "").strip() == "1"

    groups = Groups.objects.filter(teacher=teacher).order_by("name")
    group_ids = list(groups.values_list("id", flat=True))

    teacher_tests = Tests.objects.filter(created_by=teacher).order_by("-id")
    allowed_teacher_ids = set(teacher_tests.values_list("id", flat=True))
    allowed_basic_codes = {x["code"] for x in BASIC_TESTS}

    def sanitize_test(val: str) -> str:
        v = (val or "all").strip()
        if v.startswith("T-"):
            tid = v[2:].strip()
            if tid.isdigit() and int(tid) in allowed_teacher_ids:
                return f"T-{int(tid)}"
            return "all"
        if v.startswith("B-"):
            code = v[2:].strip()
            if code in allowed_basic_codes:
                return f"B-{code}"
            return "all"
        return "all" if v != "all" else "all"

    draft_test = sanitize_test(draft_test)

    students = (
        Users.objects
        .filter(role="student", studentsgroups__group__teacher=teacher)
        .distinct()
        .order_by("username")
    )

    if draft_group != "all" and draft_group.isdigit() and int(draft_group) in group_ids:
        gid = int(draft_group)
        students = (
            Users.objects
            .filter(role="student", studentsgroups__group_id=gid)
            .distinct()
            .order_by("username")
        )
        if draft_student != "all" and draft_student.isdigit():
            sid = int(draft_student)
            allowed_ids = set(students.values_list("id", flat=True))
            if sid not in allowed_ids:
                draft_student = "all"

    if apply_filters:
        request.session["stats_test"] = draft_test
        request.session["stats_group"] = draft_group
        request.session["stats_student"] = draft_student

    selected_test = sanitize_test(request.session.get("stats_test", "all"))
    selected_group = request.session.get("stats_group", "all")
    selected_student = request.session.get("stats_student", "all")

    if selected_group != "all":
        if not str(selected_group).isdigit() or int(selected_group) not in group_ids:
            selected_group = "all"

    if selected_student != "all":
        if not str(selected_student).isdigit():
            selected_student = "all"
        else:
            sid = int(selected_student)
            allowed_students = (
                Users.objects
                .filter(role="student", studentsgroups__group__teacher=teacher)
                .distinct()
            )
            if selected_group != "all":
                allowed_students = allowed_students.filter(studentsgroups__group_id=int(selected_group))
            if not allowed_students.filter(id=sid).exists():
                selected_student = "all"

    teacher_attempts = (
        Testattempts.objects
        .select_related("user", "test", "test__topic", "schedule", "schedule__group", "test__created_by")
        .filter(Q(schedule__group__teacher=teacher) | Q(test__created_by=teacher))
    )

    basic_attempts = (
        AdaptiveAttempt.objects
        .select_related("user")
        .filter(user__role="student", user__studentsgroups__group__teacher=teacher)
        .distinct()
    )

    if selected_group != "all":
        gid = int(selected_group)
        teacher_attempts = teacher_attempts.filter(schedule__group_id=gid)
        basic_attempts = basic_attempts.filter(user__studentsgroups__group_id=gid)

    if selected_student != "all":
        sid = int(selected_student)
        teacher_attempts = teacher_attempts.filter(user_id=sid)
        basic_attempts = basic_attempts.filter(user_id=sid)

    if selected_test.startswith("T-"):
        tid = selected_test[2:].strip()
        if tid.isdigit():
            teacher_attempts = teacher_attempts.filter(test_id=int(tid))
        basic_attempts = basic_attempts.none()
    elif selected_test.startswith("B-"):
        code = selected_test[2:].strip()
        basic_attempts = basic_attempts.filter(topic_code=code)
        teacher_attempts = teacher_attempts.none()

    t_count = teacher_attempts.count()
    b_count = basic_attempts.count()
    total_attempts = t_count + b_count

    t_avg = teacher_attempts.aggregate(a=Avg("score"))["a"] or 0.0
    b_avg = basic_attempts.aggregate(a=Avg("score_percent"))["a"] or 0.0
    avg_score = ((t_avg * t_count + b_avg * b_count) / total_attempts) if total_attempts else 0.0

    student_ids = set(teacher_attempts.values_list("user_id", flat=True)) | set(basic_attempts.values_list("user_id", flat=True))
    students_count = len(student_ids)

    teacher_test_ids = set(teacher_attempts.values_list("test_id", flat=True))
    basic_codes = set(basic_attempts.values_list("topic_code", flat=True))
    tests_count = len(teacher_test_ids) + len(basic_codes)

    basic_title_map = {x["code"]: x["title"] for x in BASIC_TESTS}

    # student -> group map (для показа группы даже если schedule пустой)
    links = (
        StudentsGroups.objects
        .select_related("group")
        .filter(group__teacher=teacher)
    )
    group_by_student = {l.student_id: l.group.name for l in links if l.group_id}

    history = []

    for a in teacher_attempts.order_by("-started_at")[:50]:
        group_name = "—"
        if a.schedule_id and a.schedule and a.schedule.group:
            group_name = a.schedule.group.name
        else:
            group_name = group_by_student.get(a.user_id, "—")

        history.append({
            "kind": "teacher",
            "attempt_id": a.id,  # <-- нужно для Preview
            "title": a.test.title if a.test else "Teacher test",
            "topic": getattr(getattr(a.test, "topic", None), "name", str(getattr(a.test, "topic", ""))),
            "author": getattr(getattr(a.test, "created_by", None), "username", "—"),
            "student": getattr(getattr(a, "user", None), "username", "—"),
            "group": group_name,
            "dt": a.finished_at or a.started_at,
            "score": a.score if a.score is not None else 0,
        })

    for a in basic_attempts.order_by("-started_at")[:50]:
     history.append({
        "kind": "basic",
        "attempt_id": a.id,   
        "title": basic_title_map.get(a.topic_code, a.topic_code),
        "author": "System",
        "student": getattr(getattr(a, "user", None), "username", "—"),
        "group": group_by_student.get(a.user_id, "—"),
        "topic": basic_title_map.get(a.topic_code, a.topic_code),
        "dt": a.finished_at or a.started_at,
        "score": int(a.score_percent or 0),
    })


    for x in history:
        x["dt"] = _aware(x.get("dt"))

    history.sort(key=lambda x: (x["dt"] is None, x["dt"]), reverse=True)
    history = history[:30]

    return render(request, "webapp/statistics.html", {
        "groups": groups,
        "students": students,
        "teacher_tests": teacher_tests,
        "basic_tests": BASIC_TESTS,

        "selected_test": draft_test,
        "selected_group": draft_group,
        "selected_student": draft_student,

        "total_attempts": total_attempts,
        "avg_score": avg_score,
        "students_count": students_count,
        "tests_count": tests_count,
        "history": history,
    })



@require_role("teacher")
@require_http_methods(["GET"])
def teacher_statistics_students(request: HttpRequest) -> HttpResponse:
    teacher = request.current_user
    group = (request.GET.get("group") or "all").strip()

    qs = (
        Users.objects
        .filter(role="student", studentsgroups__group__teacher=teacher)
        .distinct()
        .order_by("username")
    )

    if group != "all" and group.isdigit():
        qs = qs.filter(studentsgroups__group_id=int(group))

    return JsonResponse({"students": [{"id": u.id, "username": u.username} for u in qs]})


# Студент: профиль / группа / прогресс / тесты
@require_role("student")
def student_profile(request: HttpRequest) -> HttpResponse:
    user = request.current_user

    link = StudentsGroups.objects.select_related("group").filter(student=user).first()
    group = link.group if link else None

    student = type("StudentObj", (), {})()
    student.nickname = user.username
    student.user = user
    student.group = group

    return render(request, "webapp/student_profile.html", {"student": student, "back_url": "student_menu"})


@require_role("student")
def student_progress(request: HttpRequest) -> HttpResponse:
    student = request.current_user

    teacher_qs = (
        Testattempts.objects
        .filter(user=student, finished_at__isnull=False)
        .select_related("test", "test__topic", "schedule")
        .order_by("-finished_at")
    )

    basic_qs = (
        AdaptiveAttempt.objects
        .filter(user=student, finished_at__isnull=False)
        .order_by("-finished_at")
    )

    def teacher_score_percent(a: Testattempts) -> int:
        if a.score is not None:
            return int(a.score)
        total = a.total_questions or 0
        correct = a.correct_answers or 0
        return int(round((correct / total) * 100)) if total > 0 else 0

    def safe_dt(dt):
          if not dt:
              return timezone.localtime(timezone.now())
          if timezone.is_naive(dt):
                  dt = dt.replace(tzinfo=dt_timezone.utc)
          return timezone.localtime(dt)

    history = []

    for a in teacher_qs:
        history.append({
            "kind": "teacher",
            "title": a.test.title,
            "topic": getattr(a.test.topic, "name", str(a.test.topic)),
            "dt": safe_dt(a.finished_at or a.started_at),
            "score": teacher_score_percent(a),
        })

    for a in basic_qs:
        title = TOPIC_TITLES.get(a.topic_code, a.topic_code)
        history.append({
            "kind": "basic",
            "title": title,
            "topic": title,
            "dt": safe_dt(a.finished_at or a.started_at),
            "score": int(a.score_percent or 0),
        })

    history.sort(key=lambda x: x["dt"], reverse=True)

    all_scores = [h["score"] for h in history]
    total_attempts = len(history)
    completed_tests = len(history)
    avg_score = round(sum(all_scores) / total_attempts, 1) if total_attempts else 0
    best_result = max(all_scores) if total_attempts else 0

    return render(request, "webapp/student_progress.html", {
        "total_attempts": total_attempts,
        "completed_tests": completed_tests,
        "avg_score": avg_score,
        "best_result": float(best_result),
        "history": history,
    })


@require_role("student")
@require_http_methods(["GET"])
def student_my_group(request: HttpRequest) -> HttpResponse:
    user: Users = request.current_user

    link = StudentsGroups.objects.select_related("group", "group__teacher").filter(student=user).first()
    group = link.group if link else None

    student = type("StudentObj", (), {})()
    student.id = user.id
    student.nickname = user.username
    student.user = user
    student.group = group

    if not group:
        return render(request, "webapp/student_my_group.html", {
            "student": student,
            "group": None,
            "teacher": None,
            "classmates": [],
            "group_tests": [],
            "assigned_tests": [],
            "students_count": 0,
            "tests_count": 0,
            "back_url": "student_menu",
        })

    classmates_qs = (
        Users.objects
        .filter(role="student", studentsgroups__group=group)
        .exclude(id=user.id)
        .distinct()
        .order_by("username")
    )

    classmates = []
    for u in classmates_qs:
        st = type("StudentObj", (), {})()
        st.id = u.id
        st.nickname = u.username
        st.user = u
        classmates.append(st)

    students_count = (
        Users.objects
        .filter(role="student", studentsgroups__group=group)
        .distinct()
        .count()
    )

    group_tests_qs = (
        TestSchedule.objects
        .filter(group=group)
        .select_related("test", "test__topic")
        .annotate(questions_count=Count("test__questions"))
        .order_by("-scheduled_at")
    )

    group_tests = list(group_tests_qs)

    return render(request, "webapp/student_my_group.html", {
        "student": student,
        "group": group,
        "teacher": group.teacher,
        "classmates": classmates,
        "group_tests": group_tests,
        "assigned_tests": group_tests,
        "students_count": students_count,
        "tests_count": len(group_tests),
        "back_url": "student_menu",
    })


@require_role("student")
@require_http_methods(["GET"])
def student_tests(request: HttpRequest) -> HttpResponse:
    student: Users = request.current_user

    group_ids = StudentsGroups.objects.filter(student=student).values_list("group_id", flat=True)

    teacher_schedules = (
        TestSchedule.objects
        .filter(group_id__in=group_ids)
        .select_related("test", "test__topic", "group", "test__created_by")
        .annotate(questions_count=Count("test__questions"))
        .order_by("-scheduled_at")
    )

    now = timezone.localtime(timezone.now())
    for s in teacher_schedules:
        scheduled = timezone.localtime(s.scheduled_at) if s.scheduled_at else None
        s.is_open = bool(scheduled and now >= scheduled)
        s.start_url = reverse("teacher_test_start", args=[s.id])

    return render(request, "webapp/student_tests.html", {
        "user": student,
        "basic_tests": BASIC_TESTS,
        "teacher_schedules": teacher_schedules,
    })


@require_role("student")
def basic_test_info(request: HttpRequest, topic_code: str) -> HttpResponse:
    return render(request, "webapp/basic_test_info.html", {"test_code": topic_code})


@require_role("student")
@require_http_methods(["GET"])
def student_teacher_test_info(request: HttpRequest, schedule_id: int) -> HttpResponse:
    student = request.current_user

    link = StudentsGroups.objects.select_related("group").filter(student=student).first()
    if not link:
        return render(request, "webapp/student_teacher_test_info.html", {"error": "You are not in a group."})

    schedule = get_object_or_404(
        TestSchedule.objects.select_related("test", "test__topic", "group"),
        id=schedule_id,
        group=link.group,
    )

    return render(request, "webapp/student_teacher_test_info.html", {
        "user": student,
        "schedule": schedule,
        "test": schedule.test,
        "group": schedule.group,
    })


# Студент: адаптивные тесты
def _session_key(topic_code: str) -> str:
    return f"adaptive:{topic_code}"


def _q_answers(q: AdaptiveQuestion) -> list[str]:
    return [q.option_a, q.option_b, q.option_c, q.option_d]


def _pick_question(topic_code: str, level: int, asked_ids: list[int]) -> AdaptiveQuestion | None:
    qs = (
        AdaptiveQuestion.objects
        .filter(topic_code=topic_code, level=level, is_active=True)
        .exclude(id__in=asked_ids)
        .order_by("?")
    )
    q = qs.first()
    if q:
        return q
    return (
        AdaptiveQuestion.objects
        .filter(topic_code=topic_code, is_active=True)
        .exclude(id__in=asked_ids)
        .order_by("?")
        .first()
    )


@require_role("student")
@require_http_methods(["GET"])
def adaptive_start(request: HttpRequest, code: str) -> HttpResponse:
    user = request.current_user
    attempt = AdaptiveAttempt.objects.create(user=user, topic_code=code)

    request.session[_session_key(code)] = {
        "attempt_id": attempt.id,
        "level": 1,
        "streak_ok": 0,
        "streak_bad": 0,
        "asked_ids": [],
        "deadline_ts": int(timezone.now().timestamp()) + TIME_LIMIT_SEC,
    }
    return redirect("adaptive_take", code=code)


@require_role("student")
@require_http_methods(["GET", "POST"])
def adaptive_take(request: HttpRequest, code: str) -> HttpResponse:
    user = request.current_user

    skey = _session_key(code)
    state = request.session.get(skey)
    if not state:
        return redirect("adaptive_start", code=code)

    attempt = get_object_or_404(AdaptiveAttempt, id=state["attempt_id"], user=user, topic_code=code)

    now_ts = int(timezone.now().timestamp())
    remaining_sec = max(0, int(state["deadline_ts"]) - now_ts)
    if remaining_sec <= 0:
        return redirect("adaptive_finish", code=code)

    asked_ids = list(state.get("asked_ids", []))
    level = int(state.get("level", 1))

    if len(asked_ids) >= TEST_LEN:
        return redirect("adaptive_finish", code=code)

    if request.method == "POST":
        qid = int(request.POST.get("qid", "0") or 0)
        chosen = (request.POST.get("choice") or "").strip().upper()

        q = get_object_or_404(AdaptiveQuestion, id=qid, topic_code=code, is_active=True)
        is_correct = (chosen == (q.correct_option or "").strip().upper())

        AdaptiveAttemptAnswer.objects.update_or_create(
            attempt=attempt,
            question=q,
            defaults={"chosen_option": chosen, "is_correct": is_correct},
        )

        if qid not in asked_ids:
            asked_ids.append(qid)
            state["asked_ids"] = asked_ids

            if is_correct:
                state["streak_ok"] = int(state.get("streak_ok", 0)) + 1
                state["streak_bad"] = 0
                if state["streak_ok"] >= 2 and level < 3:
                    level += 1
                    state["level"] = level
                    state["streak_ok"] = 0
            else:
                state["streak_bad"] = int(state.get("streak_bad", 0)) + 1
                state["streak_ok"] = 0
                if state["streak_bad"] >= 2 and level > 1:
                    level -= 1
                    state["level"] = level
                    state["streak_bad"] = 0

        total = AdaptiveAttemptAnswer.objects.filter(attempt=attempt).count()
        correct = AdaptiveAttemptAnswer.objects.filter(attempt=attempt, is_correct=True).count()
        attempt.total_questions = total
        attempt.correct_answers = correct
        attempt.save(update_fields=["total_questions", "correct_answers"])

        request.session[skey] = state

        if len(asked_ids) >= TEST_LEN:
            return redirect("adaptive_finish", code=code)

        return redirect("adaptive_take", code=code)

    q = _pick_question(code, level, asked_ids)
    if not q:
        return redirect("adaptive_finish", code=code)

    shown_level = int(getattr(q, "level", level))

    return render(request, "webapp/basic_adaptive_test.html", {
        "topic_title": TOPIC_TITLES.get(code, code),
        "difficulty": shown_level,
        "difficulty_name": LEVEL_NAME.get(shown_level, f"Level {shown_level}"),
        "question": q,
        "answers": _q_answers(q),
        "q_index": len(asked_ids) + 1,
        "q_total": TEST_LEN,
        "remaining_sec": remaining_sec,
        "finish_url": redirect("adaptive_finish", code=code).url,
    })


@require_role("student")
@require_http_methods(["GET"])
def adaptive_finish(request: HttpRequest, code: str) -> HttpResponse:
    user = request.current_user

    skey = _session_key(code)
    state = request.session.get(skey)

    attempt = None

    # 1) пробуем взять attempt из session
    if state and state.get("attempt_id"):
        attempt = AdaptiveAttempt.objects.filter(
            id=state["attempt_id"], user=user, topic_code=code
        ).first()

    # 2) если session потерялась — берём последнюю попытку из БД
    if attempt is None:
        attempt = (
            AdaptiveAttempt.objects
            .filter(user=user, topic_code=code)
            .order_by("-id")
            .first()
        )

    if attempt is None:
        return render(request, "webapp/basic_test_finish.html", {
            "correct": 0, "incorrect": 0, "total": 0, "correct_percent": 0
        })

    total = AdaptiveAttemptAnswer.objects.filter(attempt=attempt).count()
    correct = AdaptiveAttemptAnswer.objects.filter(attempt=attempt, is_correct=True).count()
    incorrect = total - correct
    percent = int(round((correct / total) * 100)) if total else 0

    attempt.finished_at = timezone.now()
    attempt.total_questions = total
    attempt.correct_answers = correct
    attempt.score_percent = percent
    attempt.save(update_fields=["finished_at", "total_questions", "correct_answers", "score_percent"])

    # session можно очищать, но безопасно
    request.session.pop(skey, None)

    return render(request, "webapp/basic_test_finish.html", {
        "correct": correct,
        "incorrect": incorrect,
        "total": total,
        "correct_percent": percent,
    })


# Студент: teacher-tests (scheduled)
@require_role("student")
@require_http_methods(["GET"])
def teacher_test_start(request: HttpRequest, schedule_id: int) -> HttpResponse:
    student = request.current_user

    schedule = get_object_or_404(TestSchedule.objects.select_related("test", "group"), id=schedule_id)
    now = timezone.now()

    if schedule.scheduled_at and now < schedule.scheduled_at:
        return redirect("student_tests")

    attempt = (
        Testattempts.objects
        .filter(user=student, schedule=schedule)
        .order_by("-started_at", "-id")
        .first()
    )

    if attempt and attempt.finished_at:
        return redirect("teacher_test_finish", attempt_id=attempt.id)

    if attempt and not attempt.finished_at:
        return redirect("teacher_test_take", attempt_id=attempt.id)

    attempt = Testattempts.objects.create(
        user=student,
        test=schedule.test,
        schedule=schedule,
        started_at=now,
    )

    return redirect("teacher_test_take", attempt_id=attempt.id)


@require_role("student")
@require_http_methods(["GET", "POST"])
def teacher_test_take(request: HttpRequest, attempt_id: int) -> HttpResponse:
    student = request.current_user

    attempt = get_object_or_404(
        Testattempts.objects.select_related("test", "schedule"),
        id=attempt_id,
        user=student,
    )

    if attempt.finished_at:
        return redirect("teacher_test_finish", attempt_id=attempt.id)

    remaining_sec = _attempt_remaining_sec(attempt)
    if remaining_sec is not None and remaining_sec <= 0:
        return redirect("teacher_test_finish", attempt_id=attempt.id)

    answered_q_ids = set(
        Useranswers.objects
        .filter(attempt=attempt, answer__isnull=False)
        .values_list("question_id", flat=True)
    )

    question = (
        Questions.objects.filter(test=attempt.test)
        .exclude(id__in=answered_q_ids)
        .order_by("id")
        .first()
    )

    if question is None:
        return redirect("teacher_test_finish", attempt_id=attempt.id)

    answers_qs = list(Answers.objects.filter(question=question).order_by("id")[:4])

    if request.method == "POST":
        chosen_id = request.POST.get("answer_id")
        chosen = Answers.objects.filter(id=chosen_id, question=question).first() if chosen_id else None

        Useranswers.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                "answer": chosen,
                "answer_text": chosen.answer_text if chosen else None,
                "is_correct": bool(chosen and chosen.is_correct),
            }
        )
        return redirect("teacher_test_take", attempt_id=attempt.id)

    total = Questions.objects.filter(test=attempt.test).count()
    answered = len(answered_q_ids)

    return render(request, "webapp/student/tests.html", {
        "topic_title": attempt.test.title,
        "difficulty_name": attempt.test.difficulty,
        "difficulty": attempt.test.difficulty,
        "q_index": answered + 1,
        "q_total": total,
        "question": question,
        "answers": answers_qs,
        "remaining_sec": remaining_sec,
        "finish_url": reverse("teacher_test_finish", args=[attempt.id]),
    })


@require_role("student")
@require_http_methods(["GET"])
def teacher_test_finish(request: HttpRequest, attempt_id: int) -> HttpResponse:
    student = request.current_user

    attempt = get_object_or_404(
        Testattempts.objects.select_related("test", "schedule"),
        id=attempt_id,
        user=student,
    )

    total = Questions.objects.filter(test=attempt.test).count()
    answered = Useranswers.objects.filter(attempt=attempt, answer__isnull=False).count()
    correct = Useranswers.objects.filter(attempt=attempt, is_correct=True).count()
    wrong = total - correct
    score_percent = int(round((correct / total) * 100)) if total else 0

    now = timezone.now()
    if not attempt.finished_at:
        attempt.finished_at = now
        attempt.total_questions = total
        attempt.correct_answers = correct
        attempt.score = score_percent
        attempt.save(update_fields=["finished_at", "total_questions", "correct_answers", "score"])

    return render(request, "webapp/student/teacher_test_finish.html", {
        "topic_title": attempt.test.title,
        "total": total,
        "answered": answered,
        "correct": correct,
        "wrong": wrong,
        "score_percent": score_percent,
    })

# Учитель -> просмотр профиля студента
@require_role("teacher")
@require_http_methods(["GET"])
def teacher_student_profile(request: HttpRequest, student_id: int) -> HttpResponse:
    teacher = request.current_user
    student_user = get_object_or_404(Users, id=student_id, role="student")

    link = (
        StudentsGroups.objects
        .select_related("group")
        .filter(student=student_user, group__teacher=teacher)
        .first()
    )
    if not link:
        return redirect("teacher_groups")

    group = link.group

    teacher_qs = (
        Testattempts.objects
        .filter(user=student_user, finished_at__isnull=False)
        .select_related("test", "test__topic", "test__created_by", "schedule")
        .order_by("-finished_at")
    )

    basic_qs = (
        AdaptiveAttempt.objects
        .filter(user=student_user, finished_at__isnull=False)
        .order_by("-finished_at")
    )

    basic_title_map = {x["code"]: x["title"] for x in BASIC_TESTS}

    history = []

    for a in teacher_qs:
        history.append({
            "kind": "teacher",
            "attempt_id": a.id,
            "title": a.test.title,
            "topic": getattr(a.test.topic, "name", ""),
            "author": getattr(a.test.created_by, "username", "—"),
            "dt": a.finished_at or a.started_at,
            "score": int(a.score or 0),
        })

    for a in basic_qs:
        title = basic_title_map.get(a.topic_code, a.topic_code)
        history.append({
            "kind": "basic",
            "attempt_id": a.id,
            "title": title,
            "topic": title,
            "author": "System",
            "dt": a.finished_at or a.started_at,
            "score": int(a.score_percent or 0),
        })

    for x in history:
        x["dt"] = _aware(x.get("dt"))

    history.sort(key=lambda x: x["dt"], reverse=True)

    scores = [x["score"] for x in history]
    total_attempts = len(history)
    avg_score = round(sum(scores) / total_attempts, 1) if total_attempts else 0
    best_score = max(scores) if total_attempts else 0

   
    back_url = request.GET.get("back")
    if back_url:
        back_url = unquote(back_url)
    else:
        back_url = request.META.get("HTTP_REFERER") or reverse("teacher_groups")
        
        if "/preview" in back_url:
            back_url = reverse("teacher_statistics")

    return render(request, "webapp/teacher_student_profile.html", {
        "student": student_user,
        "group": group,
        "total_attempts": total_attempts,
        "avg_score": avg_score,
        "best_score": best_score,
        "history": history[:30],
        "back_url": back_url,
    })


@require_role("teacher")
@require_http_methods(["GET"])
def teacher_attempt_preview(request: HttpRequest, attempt_id: int) -> HttpResponse:
    teacher = request.current_user

    attempt = get_object_or_404(
        Testattempts.objects.select_related(
            "user",
            "test",
            "test__topic",
            "test__created_by",
            "schedule",
            "schedule__group",
            "schedule__group__teacher",
        ),
        id=attempt_id,
    )

    
    allowed = False
    if attempt.schedule_id and attempt.schedule and attempt.schedule.group_id:
        allowed = (getattr(attempt.schedule.group, "teacher_id", None) == teacher.id)
    if (not allowed) and attempt.test_id:
        allowed = (getattr(attempt.test, "created_by_id", None) == teacher.id)

    if not allowed:
        return redirect("teacher_statistics")

    
    group_name = "—"
    if attempt.schedule_id and attempt.schedule and attempt.schedule.group:
        group_name = attempt.schedule.group.name
    else:
        link = (
            StudentsGroups.objects
            .select_related("group")
            .filter(student_id=attempt.user_id, group__teacher=teacher)
            .first()
        )
        if link and link.group:
            group_name = link.group.name

    
    uas = (
        Useranswers.objects
        .filter(attempt=attempt)
        .select_related("question", "answer")
        .order_by("question_id", "id")
    )

    rows = []
    for ua in uas:
        q = ua.question
        chosen_text = "—"
        if ua.answer_id and ua.answer:
            chosen_text = ua.answer.answer_text
        elif ua.answer_text:
            chosen_text = ua.answer_text

        correct_text = (
            Answers.objects
            .filter(question=q, is_correct=True)
            .values_list("answer_text", flat=True)
            .first()
        ) or "—"

        rows.append({
            "q_text": q.question_text if q else "",
            "chosen": chosen_text,
            "correct": correct_text,
            "is_correct": bool(ua.is_correct),
        })

    return render(request, "webapp/teacher_attempt_preview.html", {
        "attempt": attempt,
        "student_name": getattr(attempt.user, "username", "—"),
        "group_name": group_name,
        "started_at": _aware(attempt.started_at),
        "finished_at": _aware(attempt.finished_at),
        "score": attempt.score if attempt.score is not None else 0,
        "rows": rows,
        "back_url":  request.GET.get("back") or request.META.get("HTTP_REFERER") or reverse("teacher_statistics"),
    })

@require_role("teacher")
@require_http_methods(["GET"])
def teacher_basic_attempt_preview(request: HttpRequest, attempt_id: int) -> HttpResponse:
    teacher = request.current_user

    attempt = get_object_or_404(
        AdaptiveAttempt.objects.select_related("user"),
        id=attempt_id,
    )

   
    allowed = StudentsGroups.objects.filter(
        student_id=attempt.user_id,
        group__teacher=teacher
    ).exists()
    if not allowed:
        return redirect("teacher_statistics")

    
    link = (
        StudentsGroups.objects
        .select_related("group")
        .filter(student_id=attempt.user_id, group__teacher=teacher)
        .first()
    )
    group_name = link.group.name if link and link.group else "—"

    answers = (
        AdaptiveAttemptAnswer.objects
        .select_related("question")
        .filter(attempt=attempt)
        .order_by("created_at", "id")
    )

    rows = []
    for a in answers:
        q = a.question
        opts = {
            "A": getattr(q, "option_a", ""),
            "B": getattr(q, "option_b", ""),
            "C": getattr(q, "option_c", ""),
            "D": getattr(q, "option_d", ""),
        }
        chosen_letter = (a.chosen_option or "").upper()
        correct_letter = (getattr(q, "correct_option", "") or "").upper()

        chosen_text = opts.get(chosen_letter, "—")
        correct_text = opts.get(correct_letter, "—")

        is_correct = bool(getattr(a, "is_correct", False))
        
        if chosen_letter and correct_letter and chosen_letter == correct_letter:
            is_correct = True

        rows.append({
            "q_text": getattr(q, "text", ""),
            "chosen_letter": chosen_letter or "—",
            "chosen_text": chosen_text or "—",
            "correct_letter": correct_letter or "—",
            "correct_text": correct_text or "—",
            "is_correct": is_correct,
        })

    return render(request, "webapp/teacher_basic_attempt_preview.html", {
        "attempt": attempt,
        "student_name": getattr(attempt.user, "username", "—"),
        "group_name": group_name,
        "topic_code": attempt.topic_code,
        "started_at": _aware(attempt.started_at),
        "finished_at": _aware(attempt.finished_at),
        "score": int(attempt.score_percent or 0),
        "rows": rows,
        "back_url":  request.GET.get("back") or request.META.get("HTTP_REFERER") or reverse("teacher_statistics"),
    })

@require_role("student")
@require_http_methods(["GET", "POST"])
def student_ai_stat_helper(request: HttpRequest) -> HttpResponse:
    student: Users = request.current_user

    
    snapshot = build_ai_stat_snapshot(student)
    snap_hash = snapshot_hash(snapshot)

    menu_url = reverse("student_menu")
    error = None

    
    latest = (
        AIStatHelperReport.objects
        .filter(student=student)
        .order_by("-created_at", "-id")
        .first()
    )

    is_stale = bool(latest and latest.snapshot_hash != snap_hash)
    has_report = bool(latest and (latest.report_json or latest.report_text))

   
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "refresh":
            
            return redirect("student_ai_stat_helper")

        if action == "analyze":
            try:
                
                report_dict, report_text = generate_ai_stat_report(student=student, snapshot=snapshot)

               
                AIStatHelperReport.objects.update_or_create(
                    student=student,
                    snapshot_hash=snap_hash,
                    defaults={
                        "report_json": report_dict or {},
                        "report_text": report_text or "",
                    }
                )

                return redirect("student_ai_stat_helper")

            except Exception as e:
                error = str(e)


    latest = (
        AIStatHelperReport.objects
        .filter(student=student)
        .order_by("-created_at", "-id")
        .first()
    )

    report = None
    if latest:
        report = latest.report_json or {}

    return render(request, "webapp/student_ai_stat_helper.html", {
        "snapshot": snapshot,         
        "report": report,             
        "has_report": bool(latest and (latest.report_json or latest.report_text)),
        "is_stale": bool(latest and latest.snapshot_hash != snap_hash),
        "error": error,
        "menu_url": menu_url,
    })
