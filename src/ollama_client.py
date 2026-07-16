"""Minimal Ollama client for structured JSON narrative generation."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests
from dotenv import load_dotenv

from src.db import REPO_ROOT

load_dotenv(REPO_ROOT / ".env")

DEFAULT_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")


def generate_json(
    prompt: str,
    schema: dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 300,
) -> dict[str, Any]:
    """Ask Ollama for JSON constrained by the provided schema."""
    json_schema = to_json_schema(schema)
    response = requests.post(
        f"{base_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": json_schema,
            "options": {
                "temperature": 0.2,
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful music-data narrating assistant. "
                        "Return only valid JSON that matches the required schema. "
                        "Do not include markdown, explanations, or thinking tags."
                    ),
                },
                {
                    "role": "user",
                    # /no_think reduces qwen3 chain-of-thought leakage into the reply.
                    "content": f"/no_think\n{prompt}",
                },
            ],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("message", {}).get("content", "")
    return _parse_json_content(content)


def to_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert our shorthand schema into a JSON Schema object for Ollama."""
    properties: dict[str, Any] = {}
    for key, expected in schema.items():
        if isinstance(expected, list):
            item = expected[0] if expected else "string"
            properties[key] = {
                "type": "array",
                "items": {"type": "string" if item in {"string", "YYYY-MM"} else "object"},
            }
        elif expected in {"string", "YYYY-MM"}:
            properties[key] = {"type": "string"}
        else:
            properties[key] = {"type": "object"}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
    }


def _parse_json_content(content: str) -> dict[str, Any]:
    """Parse model output into a JSON object, tolerating light wrapping."""
    text = content.strip()
    # Strip accidental markdown fences.
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1)
    # Drop leftover thinking blocks if the model ignored /no_think.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return json.loads(text)


def validate_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> None:
    """Require every top-level schema key to be present with a matching type."""
    for key, expected in schema.items():
        if key not in data:
            raise ValueError(f"Missing required key: {key}")
        value = data[key]
        if isinstance(expected, list):
            if not isinstance(value, list):
                raise ValueError(f"Key {key!r} must be a list")
        elif expected in {"string", "YYYY-MM"}:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Key {key!r} must be a non-empty string")
        else:
            # Nested object schemas are uncommon in our jobs; accept dicts.
            if expected == "object" and not isinstance(value, dict):
                raise ValueError(f"Key {key!r} must be an object")
