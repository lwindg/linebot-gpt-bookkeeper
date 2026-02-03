# -*- coding: utf-8 -*-
"""
Category resolving and validation utilities.

This module enforces "do not create new categories" by resolving user-provided
category inputs into an existing category path derived from the current
classification rules.

v2.0: Now loads categories from YAML config file (app/config/classifications.yaml)
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml

# Legacy import for fallback (will be removed after migration)
from app.gpt.prompts import CLASSIFICATION_RULES


def _normalize_separators(value: str) -> str:
    return value.replace("／", "/").strip()


@lru_cache(maxsize=1)
def _load_config_from_yaml() -> dict:
    """Load full config from YAML file."""
    config_path = Path(__file__).resolve().parents[1] / "config" / "classifications.yaml"
    if not config_path.exists():
        return {}
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_health_medical_rules() -> dict:
    data = _load_config_from_yaml()
    rules = data.get("rules") if isinstance(data, dict) else None
    health_rules = rules.get("health_medical") if isinstance(rules, dict) else None
    return health_rules if isinstance(health_rules, dict) else {}


@lru_cache(maxsize=1)
def _health_family_keyword_pattern() -> re.Pattern[str] | None:
    rules = _load_health_medical_rules()
    keywords = rules.get("family_keywords")
    if not keywords:
        return None
    return re.compile(keywords)


@lru_cache(maxsize=1)
def _health_medical_categories() -> tuple[str, str]:
    rules = _load_health_medical_rules()
    category_self = rules.get("category_self") or "健康/醫療/本人"
    category_family = rules.get("category_family") or "健康/醫療/家庭成員"
    return (category_self, category_family)


def _load_categories_from_yaml() -> set[str]:
    """Load categories from YAML config file."""
    data = _load_config_from_yaml()
    categories: set[str] = set()
    if data and "categories" in data:
        for top_level, items in data["categories"].items():
            if isinstance(items, list):
                for item in items:
                    categories.add(_normalize_separators(item))
    return categories


@lru_cache(maxsize=1)
def get_classification_rules_description() -> str:
    """
    Get formatted classification rules description for AI prompt.
    Reads from 'rules' section in YAML.
    """
    data = _load_config_from_yaml()
    if not data or "rules" not in data:
        return ""

    descriptions: list[str] = []
    rules = data.get("rules") or {}
    
    # 1. 餐飲三層規則
    if "meal_three_layer" in rules:
        r = rules.get("meal_three_layer") or {}
        title = r.get("description")
        if title:
            descriptions.append(f"### {title}")
        forbid = r.get("禁止")
        if forbid:
            descriptions.append(f"**禁止事項**: {forbid}")
        patterns = r.get("patterns") or []
        if patterns:
            descriptions.append("規則：")
            for p in patterns:
                pattern = p.get("pattern")
                category = p.get("category")
                if pattern and category:
                    descriptions.append(f"- 遇到「{pattern}」時，必須分類為 `{category}`")
        descriptions.append("")

    # 2. 飲品與點心規則
    if "beverages_snacks" in rules:
        items = rules.get("beverages_snacks") or []
        if items:
            descriptions.append("### 飲品與點心規則")
            for r in items:
                pattern = r.get("pattern")
                category = r.get("category")
                if not pattern or not category:
                    continue
                desc = f"- 遇到「{pattern}」時，分類為 `{category}`"
                exception = r.get("exception")
                if exception:
                    desc += f" (例外：{exception})"
                descriptions.append(desc)
            descriptions.append("")

    # 3. 特殊關鍵字規則
    if "special_cases" in rules:
        items = rules.get("special_cases") or []
        if items:
            descriptions.append("### 特殊關鍵字規則")
            for r in items:
                pattern = r.get("pattern")
                category = r.get("category")
                if not pattern or not category:
                    continue
                descriptions.append(f"- 遇到「{pattern}」時，分類為 `{category}`")
            descriptions.append("")

    # 4. 健康/醫療規則
    if "health_medical" in rules:
        r = rules.get("health_medical") or {}
        title = r.get("description") or "健康/醫療分類規則"
        medical_patterns = r.get("medical_patterns")
        family_keywords = r.get("family_keywords")
        category_self = r.get("category_self") or "健康/醫療/本人"
        category_family = r.get("category_family") or "健康/醫療/家庭成員"
        descriptions.append(f"### {title}")
        if medical_patterns:
            descriptions.append(f"- 遇到「{medical_patterns}」時，分類為 `{category_self}`")
        if family_keywords:
            keyword_text = str(family_keywords).replace("|", "、")
            descriptions.append(f"- 若同時包含家人關鍵字（{keyword_text}）→ `{category_family}`")
        descriptions.append("")
        
    return "\n".join(descriptions)


def _iter_category_tokens_from_rules(rules_text: str) -> Iterable[str]:
    """Legacy: Parse categories from prompt text."""
    for token in re.findall(r"`([^`]+)`", rules_text):
        token = token.strip()
        if not token:
            continue
        if "/" in token or "／" in token or token == "家庭支出":
            yield token


@lru_cache(maxsize=1)
def allowed_categories() -> set[str]:
    """Get all allowed categories (from YAML or legacy fallback)."""
    # Try loading from YAML first
    categories = _load_categories_from_yaml()
    
    # Fallback to legacy if YAML is empty
    if not categories:
        categories = {_normalize_separators(token) for token in _iter_category_tokens_from_rules(CLASSIFICATION_RULES)}

    # Expand to include parent paths (e.g., "家庭/餐飲/午餐" -> also "家庭/餐飲", "家庭")
    expanded: set[str] = set()
    for category in categories:
        expanded.add(category)
        if "/" in category:
            parts = [part for part in category.split("/") if part]
            for i in range(1, len(parts)):
                expanded.add("/".join(parts[:i]))
    return expanded


def resolve_category_input(value: str, *, original_category: str | None = None) -> str:
    """
    Resolve a user-provided category input to an allowed category path.

    - Accepts both "/" and "／" separators.
    - If the input is a short label (e.g. "水果"), tries to map it to the most
      suitable existing category path (e.g. "家庭/水果").
    - Rejects unknown categories to avoid creating new categories.
    """

    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty category")

    normalized = _normalize_separators(raw)
    allowed = allowed_categories()

    if normalized in allowed:
        if "/" not in normalized:
            if normalized in _TOP_LEVEL_DEFAULTS:
                return _TOP_LEVEL_DEFAULTS[normalized]
            children = sorted([c for c in allowed if c.startswith(f"{normalized}/")])
            if children:
                return children[0]
        return normalized

    original_normalized = _normalize_separators(original_category) if original_category else None

    candidates = _candidates_for_short_label(normalized, allowed)
    if candidates:
        preferred = _pick_best_candidate(candidates, original_normalized)
        if preferred:
            return preferred

    suggestions = _suggest_categories(normalized, allowed, limit=5)
    suggestion_text = "、".join(suggestions) if suggestions else "（無）"
    raise ValueError(f"unknown category: {raw} (suggestions: {suggestion_text})")


def apply_health_medical_default(category: str, *, context_text: str | None = None) -> str:
    """
    Normalize health medical categories to a third-level path when needed.

    Only applies when category is exactly "健康/醫療" and context_text is provided.
    """
    if not category:
        return category
    normalized = _normalize_separators(str(category).strip())
    if normalized != "健康/醫療":
        return category
    if not context_text:
        return category
    family_pattern = _health_family_keyword_pattern()
    category_self, category_family = _health_medical_categories()
    if family_pattern and family_pattern.search(str(context_text)):
        return category_family
    return category_self


def resolve_category_autocorrect(
    value: str,
    *,
    original_category: str | None = None,
    fallback: str = "家庭支出",
    context_text: str | None = None,
) -> str:
    """
    Resolve a category to an allowed path, auto-correcting to the closest match.

    Intended for new bookkeeping flows where we prefer a best-effort correction
    rather than rejecting the record.
    """

    try:
        resolved = resolve_category_input(value, original_category=original_category)
        return apply_health_medical_default(resolved, context_text=context_text)
    except ValueError:
        raw = (value or "").strip()
        normalized = _normalize_separators(raw)
        allowed = allowed_categories()

        # If it looks like a path, try reducing specificity: "A/B/C" -> "A/B" -> "A"
        if "/" in normalized:
            parts = [part for part in normalized.split("/") if part]
            for i in range(len(parts) - 1, 0, -1):
                candidate = "/".join(parts[:i])
                if candidate in allowed:
                    return candidate

            # Also try resolving the top token as a short label (e.g. "水果/香蕉" -> "水果" -> "家庭/水果")
            short = parts[0] if parts else ""
            if short:
                candidates = _candidates_for_short_label(short, allowed)
                best = _pick_best_candidate(candidates, _normalize_separators(original_category) if original_category else None)
                if best:
                    return best

        # Fallback: best-effort suggestions
        suggestions = _suggest_categories(normalized, allowed, limit=1)
        if suggestions:
            return apply_health_medical_default(suggestions[0], context_text=context_text)

        return apply_health_medical_default(_normalize_separators(fallback), context_text=context_text)

_TOP_LEVEL_DEFAULTS: dict[str, str] = {
    "交通": "交通/接駁",
}


def _candidates_for_short_label(label: str, allowed: set[str]) -> list[str]:
    if "/" in label:
        return []

    candidates: list[str] = []
    for category in allowed:
        parts = category.split("/")
        if not parts:
            continue
        if parts[-1] == label:
            candidates.append(category)
    return sorted(set(candidates))


def _pick_best_candidate(candidates: list[str], original_category: str | None) -> str | None:
    if len(candidates) == 1:
        return candidates[0]

    if original_category:
        original_top = original_category.split("/")[0] if "/" in original_category else None
        if original_top:
            scoped = [c for c in candidates if c.startswith(f"{original_top}/") or c == original_top]
            if len(scoped) == 1:
                return scoped[0]

    preferred_order = ("家庭/", "個人/", "行程/")
    for prefix in preferred_order:
        scoped = [c for c in candidates if c.startswith(prefix)]
        if len(scoped) == 1:
            return scoped[0]

    return None


def _suggest_categories(query: str, allowed: set[str], *, limit: int) -> list[str]:
    if not query:
        return []

    query_lower = query.lower()

    def score(category: str) -> tuple[int, int]:
        category_lower = category.lower()
        if category_lower == query_lower:
            return (0, len(category))
        if category_lower.endswith(f"/{query_lower}") or category_lower.endswith(query_lower):
            return (1, len(category))
        if query_lower in category_lower:
            return (2, len(category))
        return (3, len(category))

    matches = [c for c in allowed if query_lower in c.lower()]
    return [c for c in sorted(matches, key=score)[:limit]]
