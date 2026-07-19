"""Проверка end-to-end без GUI. Значения ключей не выводятся."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

import db
import models as models_svc
import network
from models import TempResultsTable


def main() -> int:
    load_dotenv()
    db.init_db()
    models_svc.ensure_default_models()

    active = models_svc.get_active_models()
    to_call = [m for m in active if m.has_api_key][:1]
    if not to_call:
        print("Нет активной модели с ключом в .env.")
        print("Добавьте OPENROUTER_API_KEY=... или укажите переменную в диалоге «Модели».")
        print("Используемый key_env по умолчанию:", models_svc.resolve_openrouter_key_env())
        return 2

    print("Модель:", to_call[0].name)
    print("Переменная ключа:", to_call[0].api_key_env)
    responses = network.send_prompt_to_models(
        to_call,
        "Ответь одним словом: ping",
        parallel=False,
        timeout=90,
    )
    item = responses[0]
    print("provider:", item.get("provider"))
    print("error:", item.get("error"))
    print("text_len:", len(item.get("text") or ""))
    if item.get("error"):
        print("text_preview:", (item.get("text") or "")[:300])
        return 3

    prompt_id = db.add_prompt("Ответь одним словом: ping", tags="e2e")
    table = TempResultsTable()
    table.load_from_responses("Ответь одним словом: ping", responses, prompt_id=prompt_id)
    table.set_selected(0, True)
    db.save_results(prompt_id, table.to_save_items())
    table.clear()
    print("E2E OK, prompt_id=", prompt_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
