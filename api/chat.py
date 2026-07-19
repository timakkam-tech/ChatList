"""Vercel serverless: прокси ChatList → OpenRouter."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from flask import Flask, jsonify, request

app = Flask(__name__)

OPENROUTER_DEFAULT = "https://openrouter.ai/api/v1/chat/completions"


def _openrouter_url() -> str:
    raw = (os.environ.get("OPENAI_BASE_URL") or OPENROUTER_DEFAULT).rstrip("/")
    if raw.endswith("/chat/completions"):
        return raw
    return f"{raw}/chat/completions"


def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    resp.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, X-ChatList-Proxy-Secret"
    )
    return resp


@app.get("/")
@app.get("/api/chat")
def health():
    return _cors(
        jsonify(
            {
                "ok": True,
                "service": "chatlist-proxy",
                "usage": "POST /api/chat with {model, messages}",
            }
        )
    )


@app.route("/", methods=["OPTIONS"])
@app.route("/api/chat", methods=["OPTIONS"])
def options():
    return _cors(("", 204))


@app.post("/")
@app.post("/api/chat")
def chat():
    expected = os.environ.get("CHATLIST_PROXY_SECRET", "").strip()
    if expected:
        got = (request.headers.get("X-ChatList-Proxy-Secret") or "").strip()
        if got != expected:
            return _cors(jsonify({"error": "Unauthorized: bad proxy secret"}), 401)

    api_key = (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()
    if not api_key:
        return _cors(jsonify({"error": "OPENROUTER_API_KEY is not set on Vercel"}), 500)

    payload = request.get_json(silent=True) or {}
    model = payload.get("model")
    messages = payload.get("messages")
    if not model or not isinstance(messages, list):
        return _cors(
            jsonify({"error": "Body must include model and messages[]"}),
            400,
        )

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
            raw = resp.read()
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:2000]
        return _cors(
            jsonify({"error": f"OpenRouter HTTP {exc.code}", "detail": err_body}),
            exc.code,
        )
    except Exception as exc:  # noqa: BLE001
        return _cors(jsonify({"error": f"Upstream error: {exc}"}), 502)

    try:
        result = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return _cors(
            jsonify(
                {
                    "error": "OpenRouter returned non-JSON",
                    "detail": raw[:500].decode("utf-8", errors="replace"),
                }
            ),
            502,
        )

    return _cors(jsonify(result), int(status))
