"""Отправка промтов к API нейросетей (адаптеры OpenAI / OpenRouter / DeepSeek / Groq)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

import httpx

import db
import request_log
from models import ModelInfo


def detect_provider(api_url: str) -> str:
    host = (urlparse(api_url).hostname or "").lower()
    if "openrouter.ai" in host:
        return "openrouter"
    if "deepseek.com" in host:
        return "deepseek"
    if "groq.com" in host:
        return "groq"
    if "openai.com" in host:
        return "openai"
    return "openai_compatible"


def _build_headers(model: ModelInfo, provider: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {model.api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        referer = db.get_setting("openrouter_referer", "https://github.com/local/ChatList") or ""
        title = db.get_setting("openrouter_title", "ChatList") or "ChatList"
        headers["HTTP-Referer"] = referer
        headers["X-Title"] = title
    return headers


def _build_body(model: ModelInfo, prompt: str, provider: str) -> dict[str, Any]:
    # Все перечисленные провайдеры используют OpenAI-совместимый chat/completions.
    _ = provider
    return {
        "model": model.name,
        "messages": [{"role": "user", "content": prompt}],
    }


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


def _logging_enabled() -> bool:
    return (db.get_setting("log_requests", "1") or "1") == "1"


def send_prompt_to_model(
    model: ModelInfo,
    prompt: str,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """
    Отправляет промт в одну модель.
    Возвращает: {model_id, model_name, text, error, provider}.
    """
    base = {
        "model_id": model.id,
        "model_name": model.name,
        "provider": detect_provider(model.api_url),
    }
    provider = base["provider"]

    if not model.api_key:
        text = (
            f"Не задан API-ключ для модели «{model.name}». "
            f"Добавьте значение переменной {model.api_key_env} в файл .env и перезапустите приложение."
        )
        request_log.log_request(
            model_name=model.name,
            api_url=model.api_url,
            ok=False,
            detail=text,
            enabled=_logging_enabled(),
        )
        return {**base, "text": text, "error": True}

    headers = _build_headers(model, provider)
    body = _build_body(model, prompt, provider)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(model.api_url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            text = _extract_text(data)
            request_log.log_request(
                model_name=model.name,
                api_url=model.api_url,
                ok=True,
                detail=f"provider={provider}; chars={len(text)}",
                enabled=_logging_enabled(),
            )
            return {**base, "text": text, "error": False}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        text = f"HTTP {exc.response.status_code}: {detail}"
        request_log.log_request(
            model_name=model.name,
            api_url=model.api_url,
            ok=False,
            detail=text,
            enabled=_logging_enabled(),
        )
        return {**base, "text": text, "error": True}
    except Exception as exc:  # noqa: BLE001 — единый интерфейс ошибки для UI
        text = f"Ошибка запроса: {exc}"
        request_log.log_request(
            model_name=model.name,
            api_url=model.api_url,
            ok=False,
            detail=text,
            enabled=_logging_enabled(),
        )
        return {**base, "text": text, "error": True}


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
