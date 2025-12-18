from __future__ import annotations

import json
from unittest.mock import Mock


def make_openai_client_with_content(content: str) -> Mock:
    mock_client = Mock()

    mock_completion = Mock()
    mock_completion.choices = [Mock()]
    mock_completion.choices[0].message.content = content

    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


def set_openai_mock_content(mock_openai: Mock, content: str) -> Mock:
    client = make_openai_client_with_content(content)
    mock_openai.return_value = client
    return client


def make_openai_client_with_json(payload: object) -> Mock:
    return make_openai_client_with_content(json.dumps(payload, ensure_ascii=False))
