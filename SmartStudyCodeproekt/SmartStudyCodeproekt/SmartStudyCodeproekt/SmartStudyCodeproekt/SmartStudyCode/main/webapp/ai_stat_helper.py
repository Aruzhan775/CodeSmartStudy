from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from openai import OpenAI

from .models import (
    AdaptiveAttempt,
    AdaptiveAttemptAnswer,
    Testattempts,
    Useranswers,
    Users,
)

# --- Настройка: какие basic-коды считать Python ---
PYTHON_BASIC_CODES = {"python-basics", "files-exceptions-functions"}

# --- Классификация вопроса -> тема (простая эвристика по ключевым словам) ---
_SKILL_RULES: list[tuple[str, list[str]]] = [
    ("Переменные и типы данных", ["variable", "переменн", "type", "тип", "int", "float", "str", "bool", "cast", "преобраз"]),
    ("Операторы и выражения", ["оператор", "operator", "арифмет", "+", "-", "*", "/", "//", "%", "**", "and", "or", "not"]),
    ("Условия if/elif/else", ["if", "elif", "else", "услови", "condition", "сравнен", "==", "!=", ">=", "<="]),
    ("Циклы for/while", ["for", "while", "loop", "цикл", "range", "итерац"]),
    ("Строки", ["string", "строк", "split", "join", "replace", "strip", "format", "f-string", "find"]),
    ("Списки и индексация", ["list", "спис", "index", "индекс", "append", "pop", "slice", "срез"]),
    ("Словари и множества", ["dict", "словар", "set", "множ", "key", "value", "items", "get("]),
    ("Функции", ["def ", "return", "function", "функц", "аргумент", "параметр"]),
    ("Исключения", ["try", "except", "finally", "raise", "ошибк", "exception"]),
    ("Файлы", ["open(", "file", "файл", "read(", "write(", "with open"]),
    ("Ввод/вывод", ["print", "input("]),
]


def _infer_skill(question_text: str | None) -> str:
    text = (question_text or "").strip().lower()
    if not text:
        return "Другое"
    text = re.sub(r"\s+", " ", text)
    for skill, keys in _SKILL_RULES:
        for k in keys:
            if k in text:
                return skill
    return "Другое"


def snapshot_hash(snapshot: dict) -> str:
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_ai_stat_snapshot(student: Users) -> dict:
    """
    Возвращает ТОЛЬКО JSON-совместимый dict.
    Без конкретных текстов вопросов/заданий — только агрегаты.
    """
    now_str = timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M")

    # Teacher attempts по Python (эвристика: title/topic содержит "python")
    teacher_attempts = (
        Testattempts.objects
        .filter(user=student, finished_at__isnull=False)
        .select_related("test", "test__topic")
        .filter(
            Q(test__title__icontains="python") |
            Q(test__topic__name__icontains="python")
        )
    )

    # Basic attempts по Python (по кодам)
    basic_attempts = (
        AdaptiveAttempt.objects
        .filter(user=student, finished_at__isnull=False, topic_code__in=PYTHON_BASIC_CODES)
    )

    total_by_skill: dict[str, int] = {}
    wrong_by_skill: dict[str, int] = {}

    # Teacher: Useranswers
    uas = (
        Useranswers.objects
        .filter(attempt__in=teacher_attempts)
        .select_related("question")
        .only("is_correct", "question__question_text")
    )
    for ua in uas:
        skill = _infer_skill(getattr(ua.question, "question_text", ""))
        total_by_skill[skill] = total_by_skill.get(skill, 0) + 1
        if not bool(getattr(ua, "is_correct", False)):
            wrong_by_skill[skill] = wrong_by_skill.get(skill, 0) + 1

    # Basic: AdaptiveAttemptAnswer
    bas = (
        AdaptiveAttemptAnswer.objects
        .filter(attempt__in=basic_attempts)
        .select_related("question")
        .only("is_correct", "question__text")
    )
    for a in bas:
        skill = _infer_skill(getattr(a.question, "text", ""))
        total_by_skill[skill] = total_by_skill.get(skill, 0) + 1
        if not bool(getattr(a, "is_correct", False)):
            wrong_by_skill[skill] = wrong_by_skill.get(skill, 0) + 1

    ranked = sorted(
        total_by_skill.keys(),
        key=lambda s: (wrong_by_skill.get(s, 0), total_by_skill.get(s, 0)),
        reverse=True,
    )

    weak_skills = []
    for s in ranked[:6]:
        total = int(total_by_skill.get(s, 0))
        wrong = int(wrong_by_skill.get(s, 0))
        if total <= 0:
            continue
        weak_skills.append({
            "skill": s,
            "wrong": wrong,
            "total": total,
            "wrong_rate": round((wrong / total) * 100, 1),
        })

    return {
        "stats": {
            "student": getattr(student, "username", "—"),
            "generated_at": now_str,
            "teacher_python_attempts": int(teacher_attempts.count()),
            "basic_python_attempts": int(basic_attempts.count()),
        },
        "weak_skills": weak_skills,
    }


# -------- OpenRouter client (КЛЮЧ ИЗ settings.py) --------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _get_openrouter_client() -> OpenAI:
    key = (getattr(settings, "OPENROUTER_API_KEY", "") or "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is empty in settings.py")

    site_url = (getattr(settings, "OPENROUTER_SITE_URL", "") or "http://127.0.0.1:8000").strip()
    app_title = (getattr(settings, "OPENROUTER_APP_TITLE", "") or "SmartCodeStudy").strip()

    return OpenAI(
        api_key=key,
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": site_url,
            "X-Title": app_title,
        },
    )


def _extract_json_object(text: str) -> dict:
    """
    Модель иногда добавляет лишний текст.
    Пытаемся вытащить первый JSON-объект вида {...}.
    """
    text = (text or "").strip()
    # 1) пробуем прямой json
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) вырезаем первый { ... } (жадно, но с минимальной защитой)
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        chunk = m.group(0).strip()
        try:
            return json.loads(chunk)
        except Exception:
            pass

    # 3) fallback
    return {
        "summary": "Не удалось корректно сформировать отчёт. Нажми «Обновить» и попробуй ещё раз.",
        "weak_topics": [],
        "priority_plan": [],
    }


def _normalize_report(d: dict) -> dict:
    """
    Гарантируем нужные поля + правильные типы.
    """
    if not isinstance(d, dict):
        return {"summary": "Отчёт пуст.", "weak_topics": [], "priority_plan": []}

    summary = d.get("summary") or ""
    if not isinstance(summary, str):
        summary = str(summary)

    weak_topics = d.get("weak_topics") or []
    if not isinstance(weak_topics, list):
        weak_topics = []

    norm_topics = []
    for t in weak_topics[:6]:
        if not isinstance(t, dict):
            continue
        topic = t.get("topic") or ""
        why_weak = t.get("why_weak") or ""
        explanation = t.get("explanation") or ""
        mini_tasks = t.get("mini_tasks") or []
        if not isinstance(mini_tasks, list):
            mini_tasks = []
        norm_topics.append({
            "topic": str(topic),
            "why_weak": str(why_weak),
            "explanation": str(explanation),
            "mini_tasks": [str(x) for x in mini_tasks[:5]],
        })

    priority_plan = d.get("priority_plan") or []
    if not isinstance(priority_plan, list):
        priority_plan = []
    priority_plan = [str(x) for x in priority_plan[:7]]

    return {
        "summary": summary.strip(),
        "weak_topics": norm_topics,
        "priority_plan": priority_plan,
    }


def generate_ai_stat_report(*, student: Users, snapshot: dict) -> tuple[dict, str]:
    """
    Возвращает (report_dict, report_text).
    report_dict — для красивого отображения в шаблоне.
    report_text — плоская версия (можно хранить в БД).
    """
    client = _get_openrouter_client()
    model = (getattr(settings, "OPENROUTER_MODEL", "") or "openai/gpt-4o-mini").strip()

    system = (
        "Ты — AIStatHelper, помощник по обучению Python.\n"
        "Ты анализируешь ТОЛЬКО агрегированные данные и объясняешь, какие темы Python проседают.\n\n"
        "СТРОГИЕ ПРАВИЛА:\n"
        "1) Пиши ТОЛЬКО на русском языке. Никакого английского (кроме кода в `...`).\n"
        "2) НЕ раскрывай конкретные вопросы/формулировки/задания и НЕ говори «ты ошибся в вопросе ...».\n"
        "3) Говори только про темы/навыки и общие паттерны.\n"
        "4) Делай читабельно: короткие абзацы, списки, переносы строк.\n"
        "5) Верни ТОЛЬКО валидный JSON без markdown.\n\n"
        "СХЕМА JSON:\n"
        "{\n"
        '  "summary": "2-5 коротких абзацев, используй \\n\\n",\n'
        '  "weak_topics": [\n'
        "    {\n"
        '      "topic": "название темы",\n'
        '      "why_weak": "1-2 предложения",\n'
        '      "explanation": "краткая теория 6-10 строк с \\n, можно вставить 1-2 мини-примера кода",\n'
        '      "mini_tasks": ["3-5 коротких практических заданий"]\n'
        "    }\n"
        "  ],\n"
        '  "priority_plan": ["5-7 пунктов плана"]\n'
        "}\n"
    )

    user_payload = {
        "student_name": getattr(student, "username", "—"),
        "stats": snapshot.get("stats", {}),
        "weak_skills": snapshot.get("weak_skills", []),
        "note": "Это агрегаты по Python. Нельзя раскрывать конкретные вопросы/формулировки. Только темы.",
    }

    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    )

    content = (resp.choices[0].message.content or "").strip()
    report_raw = _extract_json_object(content)
    report_dict = _normalize_report(report_raw)

    # плоский текст (чтобы красиво читалось и в БД, и в логах)
    parts: list[str] = []
    if report_dict.get("summary"):
        parts.append(report_dict["summary"])

    for t in report_dict.get("weak_topics", []) or []:
        parts.append(
            "\n\n"
            f"Тема: {t.get('topic','')}\n"
            f"Почему проседаешь: {t.get('why_weak','')}\n"
            f"Краткая теория:\n{t.get('explanation','')}\n"
            f"Мини-задания:\n- " + "\n- ".join(t.get("mini_tasks", []) or [])
        )

    if report_dict.get("priority_plan"):
        parts.append("\n\nПлан:\n- " + "\n- ".join(report_dict["priority_plan"]))

    report_text = "\n".join([p for p in parts if p]).strip()
    return report_dict, report_text
