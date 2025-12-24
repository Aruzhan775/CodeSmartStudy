# webapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Главная / сессия
    path("", views.index, name="index"),
    path("login/", views.login_as, name="login_as"),
    path("logout/", views.logout_view, name="logout"),

    # Авторизация 
    path("teacher/login/", views.teacher_login, name="teacher_login"),
    path("teacher/register/", views.teacher_register, name="teacher_register"),
    path("student/login/", views.student_login, name="student_login"),
    path("student/register/", views.student_register, name="student_register"),

    # Меню
    path("teacher/menu/", views.teacher_menu, name="teacher_menu"),
    path("student/menu/", views.student_menu, name="student_menu"),

    # Настройки
    path("settings/", views.settings_view, name="settings"),
    path("settings/change/", views.change_profile_data, name="change_profile_data"),

    # Учитель: профиль / студенты / группы
    path("teacher/profile/", views.teacher_profile, name="teacher_profile"),
    path("teacher/students/", views.teacher_students, name="teacher_students"),
    path("teacher/students/<int:student_id>/profile/", views.teacher_student_profile, name="teacher_student_profile"),

    path("teacher/groups/", views.teacher_groups, name="teacher_groups"),
    path("teacher/groups/create/", views.create_group, name="create_group"),

    # Учитель: тесты
    path("teacher/tests/", views.teacher_tests, name="teacher_tests"),
    path("teacher/tests/create/", views.create_test, name="create_test"),
    path("teacher/tests/create/questions/<int:test_id>/", views.add_questions, name="add_questions"),
    path("teacher/tests/preview/<int:test_id>/", views.test_preview, name="test_preview"),
    path("teacher/questions/<int:question_id>/edit/", views.edit_question, name="edit_question"),
    path("teacher/questions/<int:question_id>/delete/", views.delete_question, name="delete_question"),
    path("teacher/tests/<int:test_id>/delete/", views.delete_test, name="delete_test"),
    path("teacher/tests/<int:test_id>/schedule/", views.schedule_test, name="schedule_test"),

    # Учитель: темы (topics)
    path("teacher/topics/", views.topics_list, name="topics_list"),
    path("teacher/topics/create/", views.topic_create, name="topic_create"),
    path("teacher/topics/<int:topic_id>/edit/", views.topic_edit, name="topic_edit"),
    path("teacher/topics/<int:topic_id>/delete/", views.topic_delete, name="topic_delete"),

    # Учитель: статистика
    path("teacher/statistics/", views.teacher_statistics, name="teacher_statistics"),
    path("teacher/statistics/students/", views.teacher_statistics_students, name="teacher_statistics_students"),

    # Студент: профиль / группа / прогресс / тесты
    path("student/profile/", views.student_profile, name="student_profile"),
    path("student/groups/", views.student_my_group, name="student_my_group"),
    path("student/progress/", views.student_progress, name="student_progress"),
    path("student/tests/", views.student_tests, name="student_tests"),
    path("student/teacher-tests/<int:schedule_id>/", views.student_teacher_test_info, name="student_teacher_test_info"),
    path("student/teacher-tests/<int:schedule_id>/start/", views.teacher_test_start, name="teacher_test_start"),
    path("student/teacher-tests/attempt/<int:attempt_id>/take/", views.teacher_test_take, name="teacher_test_take"),
    path("student/teacher-tests/attempt/<int:attempt_id>/finish/", views.teacher_test_finish, name="teacher_test_finish"),

    # Студент: базовые адаптивные тесты
    path("student/tests/basic/<str:code>/", views.basic_test_info, name="basic_test_info"),
    path("student/tests/basic/<str:code>/start/", views.adaptive_start, name="adaptive_start"),
    path("student/tests/basic/<str:code>/take/", views.adaptive_take, name="adaptive_take"),
    path("student/tests/basic/<str:code>/finish/", views.adaptive_finish, name="adaptive_finish"),

    path("teacher/attempts/<int:attempt_id>/preview/", views.teacher_attempt_preview, name="teacher_attempt_preview"),
    path("teacher/basic-attempts/<int:attempt_id>/preview/", views.teacher_basic_attempt_preview, name="teacher_basic_attempt_preview"),

    path("student/ai-stat-helper/", views.student_ai_stat_helper, name="student_ai_stat_helper"),
]
