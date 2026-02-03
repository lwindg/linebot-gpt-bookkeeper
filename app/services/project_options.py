# -*- coding: utf-8 -*-
"""
Project options service (Make.com -> Notion select options).
"""

from __future__ import annotations

import logging
from typing import Tuple, List, Optional

import requests

from app.config import PROJECT_OPTIONS_WEBHOOK_URL, PROJECT_OPTIONS_TTL, WEBHOOK_TIMEOUT
from app.services.kv_store import KVStore

logger = logging.getLogger(__name__)

_PROJECT_OPTIONS_CACHE_KEY = "project_options"


def get_project_options(kv_store: Optional[KVStore] = None) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Fetch project options from Make.com webhook, with KV cache.

    Returns:
        (options, error_code)
    """
    if not PROJECT_OPTIONS_WEBHOOK_URL:
        return None, "missing_webhook"

    kv_store = kv_store or KVStore()
    cached = kv_store.get(_PROJECT_OPTIONS_CACHE_KEY) if kv_store else None
    if isinstance(cached, dict):
        options = cached.get("options")
        if isinstance(options, list):
            return options, None

    try:
        response = requests.post(
            PROJECT_OPTIONS_WEBHOOK_URL,
            json={},
            timeout=WEBHOOK_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.error(f"Project options request failed: {exc}")
        return None, "request_failed"

    if response.status_code not in (200, 201, 202):
        logger.error(
            "Project options webhook failed: %s %s",
            response.status_code,
            response.text,
        )
        return None, "http_error"

    try:
        payload = response.json()
    except ValueError:
        logger.error("Project options response is not valid JSON")
        return None, "invalid_json"

    if isinstance(payload, list):
        options = payload
    elif isinstance(payload, dict):
        options = payload.get("options")
    else:
        options = None
    if not isinstance(options, list):
        logger.error("Project options response missing options list")
        return None, "invalid_response"

    cleaned = [str(option).strip() for option in options if str(option).strip()]
    if kv_store:
        kv_store.set(_PROJECT_OPTIONS_CACHE_KEY, {"options": cleaned}, ttl=PROJECT_OPTIONS_TTL)

    return cleaned, None
