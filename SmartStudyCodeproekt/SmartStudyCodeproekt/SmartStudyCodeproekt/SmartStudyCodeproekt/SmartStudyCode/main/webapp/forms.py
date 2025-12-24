from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group

class RegisterForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[("student", "Студент"), ("teacher", "Преподаватель")]
    )

class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ("username", "password1", "password2", "role")


class DifficultyForm(forms.Form):
    difficulty = forms.ChoiceField(
        choices=[
            ("Beginner", "Легкий"),
            ("Medium", "Средний"),
            ("Advanced", "Сложный")
        ]
    )

class StudentRegisterForm(forms.Form):
    email = forms.EmailField(label="Email")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repeat password", widget=forms.PasswordInput)

    nickname = forms.CharField(label="Nickname", max_length=255)
    group = forms.ModelChoiceField(
        label="Group",
        queryset=Group.objects.all(),
        required=False
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match")
        return cleaned