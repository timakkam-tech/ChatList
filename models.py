"""Логика работы с моделями нейросетей и временной таблицей результатов."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

import db

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"

DEFAULT_OPENROUTER_MODELS = (
    ("openai/gpt-4o-mini", True),
    ("google/gemini-2.0-flash-001", True),
    ("anthropic/claude-3.5-haiku", False),
)


def reload_env() -> None:
    load_dotenv(override=True)


def resolve_openrouter_url() -> str:
    reload_env()
    raw = (os.getenv("OPENAI_BASE_URL") or OPENROUTER_URL).rstrip("/")
    if raw.endswith("/chat/completions"):
        return raw
    return f"{raw}/chat/completions"


def resolve_openrouter_key_env() -> str:
    """Какую переменную использовать для OpenRouter (с учётом уже заполненного .env)."""
    reload_env()
    if os.getenv("OPENROUTER_API_KEY"):
        return "OPENROUTER_API_KEY"
    if os.getenv("OPENAI_API_KEY"):
        return "OPENAI_API_KEY"
    return OPENROUTER_KEY_ENV


reload_env()


@dataclass
class ModelInfo:
    id: int
    name: str
    api_url: str
    api_key_env: str
    is_active: bool
    api_key: str | None = None

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


def _to_model_info(row: dict[str, Any], resolve_key: bool = True) -> ModelInfo:
    api_key = None
    if resolve_key:
        api_key = os.getenv(row["api_key_env"]) or None
    return ModelInfo(
        id=int(row["id"]),
        name=row["name"],
        api_url=row["api_url"],
        api_key_env=row["api_key_env"],
        is_active=bool(row["is_active"]),
        api_key=api_key,
    )


def ensure_default_models() -> None:
    """Добавляет модели OpenRouter, если их ещё нет."""
    key_env = resolve_openrouter_key_env()
    api_url = resolve_openrouter_url()
    existing = db.list_models()

    has_openrouter = any(
        "openrouter" in (row.get("api_url") or "").lower() for row in existing
    )
    if not has_openrouter:
        for name, is_active in DEFAULT_OPENROUTER_MODELS:
            if db.get_model_by_name(name) is None:
                db.add_model(
                    name=name,
                    api_url=api_url,
                    api_key_env=key_env,
                    is_active=is_active,
                )

    # Подтянуть имя переменной ключа для уже существующих OpenRouter-моделей.
    for row in db.list_models():
        url = (row.get("api_url") or "").lower()
        if "openrouter" not in url:
            continue
        updates: dict = {}
        if not os.getenv(row["api_key_env"]) and os.getenv(key_env):
            if key_env != row["api_key_env"]:
                updates["api_key_env"] = key_env
        if api_url and row.get("api_url") != api_url and "openrouter" in api_url.lower():
            # Нормализуем URL из OPENAI_BASE_URL, если задан.
            if not (row.get("api_url") or "").rstrip("/").endswith("chat/completions"):
                updates["api_url"] = api_url
            elif "openrouter.ai" in api_url.lower():
                updates["api_url"] = api_url
        if updates:
            db.update_model(int(row["id"]), **updates)


def get_all_models() -> list[ModelInfo]:
    return [_to_model_info(row) for row in db.list_models()]


def get_active_models() -> list[ModelInfo]:
    """Активные модели с ключами из .env (ключ может быть None)."""
    reload_env()
    return [_to_model_info(row) for row in db.list_active_models()]


def models_missing_keys(models: list[ModelInfo] | None = None) -> list[ModelInfo]:
    items = models if models is not None else get_active_models()
    return [m for m in items if not m.has_api_key]


def create_model(
    name: str,
    api_url: str,
    api_key_env: str,
    is_active: bool = True,
) -> ModelInfo:
    model_id = db.add_model(name, api_url, api_key_env, is_active=is_active)
    row = db.get_model(model_id)
    assert row is not None
    return _to_model_info(row)


def edit_model(
    model_id: int,
    name: str | None = None,
    api_url: str | None = None,
    api_key_env: str | None = None,
    is_active: bool | None = None,
) -> ModelInfo:
    db.update_model(
        model_id,
        name=name,
        api_url=api_url,
        api_key_env=api_key_env,
        is_active=is_active,
    )
    row = db.get_model(model_id)
    assert row is not None
    return _to_model_info(row)


def remove_model(model_id: int) -> None:
    db.delete_model(model_id)


# --- Временная таблица результатов (в памяти, не в SQLite) ---


@dataclass
class TempResultRow:
    model_id: int
    model_name: str
    response: str
    selected: bool = False
    error: bool = False


@dataclass
class TempResultsTable:
    """Сессионная таблица ответов до сохранения в БД."""

    rows: list[TempResultRow] = field(default_factory=list)
    prompt_id: int | None = None
    prompt_text: str = ""

    def clear(self) -> None:
        self.rows.clear()
        self.prompt_id = None
        self.prompt_text = ""

    def load_from_responses(
        self,
        prompt_text: str,
        responses: list[dict[str, Any]],
        prompt_id: int | None = None,
    ) -> None:
        """
        Создаёт таблицу заново из ответов network.
        responses: [{model_id, model_name, text, error}, ...]
        """
        self.clear()
        self.prompt_text = prompt_text
        self.prompt_id = prompt_id
        for item in responses:
            self.rows.append(
                TempResultRow(
                    model_id=int(item["model_id"]),
                    model_name=item["model_name"],
                    response=item["text"],
                    selected=False,
                    error=bool(item.get("error", False)),
                )
            )

    def set_selected(self, index: int, selected: bool) -> None:
        self.rows[index].selected = selected

    def selected_rows(self) -> list[TempResultRow]:
        return [row for row in self.rows if row.selected and not row.error]

    def to_save_items(self) -> list[dict[str, Any]]:
        return [
            {"model_id": row.model_id, "response": row.response}
            for row in self.selected_rows()
        ]

    def to_export_rows(self, only_selected: bool = True) -> list[dict[str, Any]]:
        source = self.selected_rows() if only_selected else [r for r in self.rows if not r.error]
        return [
            {
                "model_id": row.model_id,
                "model_name": row.model_name,
                "response": row.response,
            }
            for row in source
        ]
