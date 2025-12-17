from __future__ import annotations

from unittest.mock import Mock


def make_openai_client_with_content(content: str) -> Mock:
    mock_client = Mock()

    mock_completion = Mock()
    mock_completion.choices = [Mock()]
    mock_completion.choices[0].message.content = content

    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client

