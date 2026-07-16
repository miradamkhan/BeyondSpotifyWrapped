"""Smoke-test Milestone 4 API endpoints."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

BASE = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY")
HEADERS = {"X-API-Key": API_KEY}


def main() -> None:
    health = requests.get(f"{BASE}/health", timeout=10)
    print("GET /health", health.status_code, health.json())

    unauthorized = requests.get(f"{BASE}/taste-dna", timeout=10)
    print("GET /taste-dna (no key)", unauthorized.status_code)

    checks = [
        ("GET", "/timeline"),
        ("GET", "/clusters"),
        ("GET", "/moments"),
        ("GET", "/narratives"),
        ("GET", "/taste-dna"),
        ("POST", "/sync"),
    ]
    for method, path in checks:
        response = requests.request(method, f"{BASE}{path}", headers=HEADERS, timeout=60)
        summary = _summarize(path, response)
        print(f"{method} {path}", response.status_code, summary)


def _summarize(path: str, response: requests.Response) -> str:
    if response.status_code >= 400:
        return response.text[:200]
    data = response.json()
    if path == "/timeline":
        return f"months={len(data['months'])} top_genres={len(data['top_genres'])}"
    if path == "/clusters":
        return f"clusters={len(data['clusters'])} points={len(data['points'])}"
    if path == "/moments":
        return f"moments={len(data['moments'])}"
    if path == "/narratives":
        return f"narratives={len(data['narratives'])}"
    if path == "/taste-dna":
        return f"headline={data['content'].get('headline', '')[:60]!r}"
    if path == "/sync":
        return json.dumps(data)
    return "ok"


if __name__ == "__main__":
    main()
