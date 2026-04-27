from __future__ import annotations

import json
import os

import requests


OPENAI_API_BASE = "https://api.openai.com/v1/responses"


def load_openai_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")
    return api_key


def create_response(payload: dict) -> dict:
    api_key = load_openai_api_key()
    response = requests.post(
        OPENAI_API_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def first_output_text(response: dict) -> str:
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")
    return ""


def first_refusal(response: dict) -> str:
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                return content.get("refusal", "")
    return ""


def dump_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True)
