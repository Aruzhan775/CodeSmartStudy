# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.utils import timezone

class Answers(models.Model):
    question = models.ForeignKey('Questions', models.DO_NOTHING)
    answer_text = models.TextField()
    is_correct = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'answers'


class Groups(models.Model):
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey('Users', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'groups'


class Profiles(models.Model):
    user = models.OneToOneField('Users', models.DO_NOTHING)
    total_tests_passed = models.IntegerField()
    avg_score = models.DecimalField(max_digits=5, decimal_places=2)
    total_correct_answers = models.IntegerField()
    total_time_spent = models.IntegerField()
    tests_created = models.IntegerField()
    groups_managed = models.IntegerField()
    students_total = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'profiles'


class Questions(models.Model):
    test = models.ForeignKey('Tests', models.DO_NOTHING)
    question_text = models.TextField()
    difficulty = models.CharField(max_length=10)
    type = models.CharField(max_length=20)
    time_limit = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'questions'


class StudentsGroups(models.Model):
    pk = models.CompositePrimaryKey('student_id', 'group_id')
    student = models.ForeignKey('Users', models.DO_NOTHING)
    group = models.ForeignKey(Groups, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'students_groups'


class Testattempts(models.Model):
    user = models.ForeignKey('Users', models.DO_NOTHING)
    test = models.ForeignKey('Tests', models.DO_NOTHING)

    schedule = models.ForeignKey(
        'TestSchedule',
        models.DO_NOTHING,
        db_column='schedule_id',
        null=True,
        blank=True,
        related_name='attempts'
    )

    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    score = models.IntegerField(blank=True, null=True)
    total_questions = models.IntegerField(blank=True, null=True)
    correct_answers = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'testattempts'


class Tests(models.Model):
    title = models.CharField(max_length=200)
    topic = models.ForeignKey('Topics', models.DO_NOTHING)
    difficulty = models.CharField(max_length=10)
    time_limit = models.IntegerField(blank=True, null=True)
    created_by = models.ForeignKey('Users', models.DO_NOTHING, db_column='created_by')

    class Meta:
        managed = False
        db_table = 'tests'


class Topics(models.Model):
    name = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'topics'


class Useranswers(models.Model):
    attempt = models.ForeignKey(Testattempts, models.DO_NOTHING)
    question = models.ForeignKey(Questions, models.DO_NOTHING)
    answer = models.ForeignKey(Answers, models.DO_NOTHING, blank=True, null=True)
    answer_text = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(blank=True, null=True)
    class Meta:
        managed = False
        db_table = 'useranswers'


class Users(models.Model):
    username = models.CharField(unique=True, max_length=50)
    email = models.CharField(unique=True, max_length=100)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=20)
    class Meta:
        managed = False
        db_table = 'users'


class TestSchedule(models.Model):
    test = models.ForeignKey("Tests", on_delete=models.CASCADE, related_name="schedules")
    group = models.ForeignKey("Groups", on_delete=models.CASCADE, related_name="scheduled_tests")
    scheduled_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "test_schedule"
        constraints = [
            models.UniqueConstraint(fields=["test", "group"], name="uniq_test_group_schedule")
        ]

class AdaptiveQuestion(models.Model):
    topic_code = models.CharField(max_length=64, db_index=True)
    level = models.PositiveSmallIntegerField(db_index=True)
    text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=1)
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = "adaptive_questions"
        indexes = [
            models.Index(fields=["topic_code", "level"]),
        ]


class AdaptiveAttempt(models.Model):
    user = models.ForeignKey("Users", on_delete=models.CASCADE, db_column="user_id")
    topic_code = models.CharField(max_length=64, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    total_questions = models.PositiveSmallIntegerField(default=0)
    correct_answers = models.PositiveSmallIntegerField(default=0)
    score_percent = models.PositiveSmallIntegerField(default=0)
    class Meta:
        db_table = "adaptive_attempts"


class AdaptiveAttemptAnswer(models.Model):
    attempt = models.ForeignKey(AdaptiveAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(AdaptiveQuestion, on_delete=models.CASCADE)
    chosen_option = models.CharField(max_length=1) 
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "adaptive_attempt_answers"
        unique_together = (("attempt", "question"),)


class AIStatHelperReport(models.Model):
    student = models.ForeignKey(
        "Users",
        on_delete=models.CASCADE,
        related_name="ai_stat_reports",
        db_index=True,
    )

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    snapshot_hash = models.CharField(max_length=64, db_index=True)

    report_json = models.JSONField(default=dict)

    report_text = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["student", "-created_at"]),
            models.Index(fields=["student", "snapshot_hash"]),
        ]