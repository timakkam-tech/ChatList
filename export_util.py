"""Экспорт результатов в Markdown и JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def results_to_markdown(rows: list[dict[str, Any]], prompt_text: str = "") -> str:
    lines = ["# ChatList — результаты", ""]
    if prompt_text:
        lines.extend(["## Промт", "", prompt_text, ""])
    lines.append("## Ответы")
    lines.append("")
    for row in rows:
        name = row.get("model_name") or row.get("model") or f"model#{row.get('model_id')}"
        text = row.get("response") or row.get("text") or ""
        lines.append(f"### {name}")
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def results_to_json(rows: list[dict[str, Any]], prompt_text: str = "") -> str:
    payload = {
        "prompt": prompt_text,
        "results": [
            {
                "model_id": row.get("model_id"),
                "model_name": row.get("model_name") or row.get("model"),
                "response": row.get("response") or row.get("text"),
            }
            for row in rows
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def export_results(
    path: str | Path,
    rows: list[dict[str, Any]],
    prompt_text: str = "",
) -> Path:
    out = Path(path)
    suffix = out.suffix.lower()
    if suffix == ".md":
        content = results_to_markdown(rows, prompt_text)
    elif suffix == ".json":
        content = results_to_json(rows, prompt_text)
    else:
        raise ValueError("Поддерживаются только .md и .json")
    out.write_text(content, encoding="utf-8")
    return out
