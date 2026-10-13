from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME, LLM_PROVIDER


class LLMError(RuntimeError):
    pass


def _get_client() -> Optional["OpenAI"]:
    provider = (LLM_PROVIDER or "").lower()
    if provider not in {"openai", "openai_compatible"}:
        raise LLMError(
            "Unsupported LLM provider. Set LLM_PROVIDER to 'openai' or 'openai_compatible' and provide LLM_BASE_URL/LLM_API_KEY."
        )

    api_key = (LLM_API_KEY or "").strip()
    if not api_key:
        raise LLMError("LLM_API_KEY is missing. Configure a valid OpenAI-compatible API key before calling the LLM.")

    base_url = LLM_BASE_URL.strip() if LLM_BASE_URL else None
    return OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)


def generate_text(prompt: str, system_prompt: Optional[str] = None) -> str:
    model_name = (LLM_MODEL_NAME or "").strip()
    if not model_name:
        raise LLMError("LLM_MODEL_NAME is not configured. Set the model used by the OpenAI-compatible endpoint.")

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt or "You are a precise educational tutor."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1000,
        )
    except Exception as exc:  # pragma: no cover - runtime guard for missing API or network
        raise LLMError(f"LLM request failed: {exc}") from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError, ValueError):
        raise LLMError("LLM response was malformed or empty.")

    if not content or not str(content).strip():
        raise LLMError("LLM response was empty.")

    return str(content).strip()
