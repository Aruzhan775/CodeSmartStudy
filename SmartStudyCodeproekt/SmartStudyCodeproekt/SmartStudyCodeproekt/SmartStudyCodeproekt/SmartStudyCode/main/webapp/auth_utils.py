# webapp/auth_utils.py
from __future__ import annotations

from functools import wraps
from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from .models import Users


def login_user(request: HttpRequest, user: Users) -> None:
    request.session["user_id"] = user.id
    request.session["role"] = user.role


def logout_user(request: HttpRequest) -> None:
    request.session.pop("user_id", None)
    request.session.pop("role", None)


def require_role(*roles: str):
    def decorator(view_func: Callable[..., HttpResponse]):
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            user_id = request.session.get("user_id")
            if not user_id:
                return redirect("login_as")

            user = Users.objects.filter(id=user_id).first()
            if not user:
                logout_user(request)
                return redirect("login_as")

            if roles and user.role not in roles:
                return redirect("login_as")

            request.current_user = user
            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator

