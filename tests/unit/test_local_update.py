from unittest.mock import patch

from test_local import (
    build_mock_transaction,
    get_project_list_message,
    get_update_transaction,
    run_update_dry_run,
)


def test_run_update_dry_run_marks_prefix() -> None:
    with patch("test_local.handle_update_last_entry", return_value="✅ 修改成功") as mock_handle:
        reply = run_update_dry_run(
            "test_user",
            {"專案": "旅遊"},
            raw_message="專案改為旅遊",
            success_count=2,
        )

    assert reply.startswith("✅ [DRY-RUN]")
    mock_handle.assert_called_once_with(
        "test_user",
        {"專案": "旅遊"},
        raw_message="專案改為旅遊",
    )


def test_get_update_transaction_returns_mock_when_empty() -> None:
    with patch("test_local.get_last_transaction", return_value=None):
        tx, used_mock = get_update_transaction("test_user", use_mock=True)
    assert used_mock is True
    assert tx == build_mock_transaction()


def test_get_update_transaction_returns_none_when_empty_no_mock() -> None:
    with patch("test_local.get_last_transaction", return_value=None):
        tx, used_mock = get_update_transaction("test_user", use_mock=False)
    assert used_mock is False
    assert tx is None


def test_get_project_list_message_delegates() -> None:
    with patch("test_local.handle_project_list_request", return_value="ok"):
        assert get_project_list_message() == "ok"
