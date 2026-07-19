"""Отправка промтов к API нейросетей."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from models import ModelInfo


def _extract_text(payload: Any) -> str:
    """Достаёт текст ответа из OpenAI-совместимого JSON."""
    if not isinstance(payload, dict):
        return str(payload)

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and message.get("content"):
            return str(message["content"])
        text = choices[0].get("text") if isinstance(choices[0], dict) else None
        if text:
            return str(text)

    if "output_text" in payload:
        return str(payload["output_text"])

    return str(payload)


def send_prompt_to_model(
    model: ModelInfo,
    prompt: str,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """
    Отправляет промт в одну модель.
    Возвращает: {model_id, model_name, text, error}.
    """
    base = {
        "model_id": model.id,
        "model_name": model.name,
    }

    if not model.api_key:
        return {
            **base,
            "text": f"Не задан API-ключ: переменная {model.api_key_env}",
            "error": True,
        }

    headers = {
        "Authorization": f"Bearer {model.api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model.name,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(model.api_url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            return {**base, "text": _extract_text(data), "error": False}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        return {
            **base,
            "text": f"HTTP {exc.response.status_code}: {detail}",
            "error": True,
        }
    except Exception as exc:  # noqa: BLE001 — единый интерфейс ошибки для UI
        return {**base, "text": f"Ошибка запроса: {exc}", "error": True}


def send_prompt_to_models(
    models: list[ModelInfo],
    prompt: str,
    *,
    parallel: bool = True,
    timeout: float = 60.0,
) -> list[dict[str, Any]]:
    """
    Отправляет промт во все модели.
    По умолчанию — параллельно. Единый интерфейс ответа на модель.
    """
    if not models:
        return []

    if not parallel or len(models) == 1:
        return [send_prompt_to_model(m, prompt, timeout=timeout) for m in models]

    results: list[dict[str, Any] | None] = [None] * len(models)
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        future_map = {
            executor.submit(send_prompt_to_model, model, prompt, timeout=timeout): index
            for index, model in enumerate(models)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            results[index] = future.result()

    return [item for item in results if item is not None]
