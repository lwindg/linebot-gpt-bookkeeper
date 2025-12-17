from __future__ import annotations

from pathlib import Path

import pytest


def _top_level_tests_group(path: Path) -> str | None:
    parts = path.parts
    try:
        tests_index = parts.index("tests")
    except ValueError:
        return None
    if tests_index + 1 >= len(parts):
        return None
    return parts[tests_index + 1]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        group = _top_level_tests_group(Path(str(item.fspath)))
        if group == "unit":
            item.add_marker(pytest.mark.unit)
        elif group == "integration":
            item.add_marker(pytest.mark.integration)
