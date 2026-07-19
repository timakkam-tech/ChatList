"""Vercel Python Function: прокси ChatList → OpenRouter (без сторонних пакетов)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler


OPENROUTER_DEFAULT = "https://openrouter.ai/api/v1/chat/completions"


def _openrouter_url() -> str:
    raw = (os.environ.get("OPENAI_BASE_URL") or OPENROUTER_DEFAULT).rstrip("/")
    if raw.endswith("/chat/completions"):
        return raw
    return f"{raw}/chat/completions"


class handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-ChatList-Proxy-Secret",
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-ChatList-Proxy-Secret",
        )
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._send(
            200,
            {
                "ok": True,
                "service": "chatlist-proxy",
                "usage": "POST /api/chat with {model, messages}",
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        expected = os.environ.get("CHATLIST_PROXY_SECRET", "").strip()
        if expected:
            got = (self.headers.get("X-ChatList-Proxy-Secret") or "").strip()
            if got != expected:
                self._send(401, {"error": "Unauthorized: bad proxy secret"})
                return

        api_key = (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        if not api_key:
            self._send(500, {"error": "OPENROUTER_API_KEY is not set on Vercel"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "Invalid JSON"})
            return

        model = payload.get("model")
        messages = payload.get("messages")
        if not model or not isinstance(messages, list):
            self._send(400, {"error": "Body must include model and messages[]"})
            return

        body = json.dumps({"model": model, "messages": messages}).encode("utf-8")
        req = urllib.request.Request(
            _openrouter_url(),
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.environ.get(
                    "OPENROUTER_HTTP_REFERER",
                    "https://github.com/timakkam-tech/ChatList",
                ),
                "X-Title": os.environ.get("OPENROUTER_TITLE", "ChatList"),
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                upstream = resp.read()
                status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")[:2000]
            self._send(
                int(exc.code),
                {"error": f"OpenRouter HTTP {exc.code}", "detail": err_body},
            )
            return
        except Exception as exc:  # noqa: BLE001
            self._send(502, {"error": f"Upstream error: {exc}"})
            return

        try:
            result = json.loads(upstream.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(
                502,
                {
                    "error": "OpenRouter returned non-JSON",
                    "detail": upstream[:500].decode("utf-8", errors="replace"),
                },
            )
            return

        self._send(int(status), result)
