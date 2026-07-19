"""Логика работы с моделями нейросетей и временной таблицей результатов."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

import db


load_dotenv()


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


def get_all_models() -> list[ModelInfo]:
    return [_to_model_info(row) for row in db.list_models()]


def get_active_models() -> list[ModelInfo]:
    """Активные модели с ключами из .env (ключ может быть None)."""
    return [_to_model_info(row) for row in db.list_active_models()]


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
