"""Простое логирование HTTP-запросов к моделям."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "requests.log"


def log_request(
    *,
    model_name: str,
    api_url: str,
    ok: bool,
    detail: str,
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status = "OK" if ok else "ERR"
    line = f"{stamp}\t{status}\t{model_name}\t{api_url}\t{detail.replace(chr(10), ' ')[:300]}\n"
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)
