# -*- coding: utf-8 -*-
"""
Integration tests for Edit Last Transaction feature (001-edit-last-transaction)

Test coverage:
- US1: Edit item name (品項)
- US2: Edit category (分類)
- US3: Edit project (專案)
- US4: Edit amount (原幣金額)
- Error handling: empty fields, not found, expired, concurrency
"""

import pytest
from unittest.mock import MagicMock, patch
from app.line_handler import handle_update_last_entry
from app.kv_store import KVStore


class TestEditItemName:
    """US1: Edit item name (品項)"""

    @patch('app.line_handler.KVStore')
    def test_edit_item_name_success(self, mock_kv_store_class):
        """
        TC-US1-001: Edit item name success scenario

        Given: KV contains transaction with 品項="午餐", 原幣金額=100.0, 交易ID="20251129-140000"
        When: Call handle_update_last_entry(user_id, {"品項": "工作午餐"})
        Then:
          - KV transaction updated with 品項="工作午餐"
          - 原幣金額 remains 100.0 (unchanged)
          - Success message contains "修改成功"
        """
        # Arrange: Setup mock KV store
        user_id = "test_user_123"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "午餐",
            "原幣金額": 100.0,
            "付款方式": "現金",
            "分類": "飲食",
            "日期": "2025-11-29"
        }

        # Mock KVStore instance
        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store

        # First get: return original transaction
        # Second get: return original transaction (for optimistic lock check)
        mock_kv_store.get.side_effect = [original_transaction, original_transaction]
        mock_kv_store.set.return_value = True

        # Act: Update item name
        result_message = handle_update_last_entry(user_id, {"品項": "工作午餐"})

        # Assert: Verify success message
        assert "修改成功" in result_message
        assert "品項" in result_message
        assert "工作午餐" in result_message

        # Verify KV operations
        assert mock_kv_store.get.call_count == 2  # Read original, then re-read for lock check
        mock_kv_store.get.assert_called_with(f"last_transaction:{user_id}")

        # Verify set was called with updated transaction
        assert mock_kv_store.set.call_count == 1
        call_args = mock_kv_store.set.call_args
        updated_tx = call_args[0][1]  # Second argument is the updated transaction

        # Verify updated fields
        assert updated_tx["品項"] == "工作午餐"  # Updated
        assert updated_tx["原幣金額"] == 100.0  # Unchanged
        assert updated_tx["付款方式"] == "現金"  # Unchanged
        assert updated_tx["交易ID"] == "20251129-140000"  # Unchanged

    @patch('app.line_handler.KVStore')
    def test_edit_item_name_not_found(self, mock_kv_store_class):
        """
        TC-US1-002: Edit item name when no transaction exists

        Given: KV contains no transaction for user
        When: Call handle_update_last_entry(user_id, {"品項": "工作午餐"})
        Then: Error message "找不到最近的記帳記錄"
        """
        # Arrange
        user_id = "test_user_456"

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store
        mock_kv_store.get.return_value = None  # No transaction found

        # Act
        result_message = handle_update_last_entry(user_id, {"品項": "工作午餐"})

        # Assert
        assert "找不到最近的記帳記錄" in result_message
        assert mock_kv_store.set.call_count == 0  # Should not attempt to save

    @patch('app.line_handler.KVStore')
    def test_edit_item_name_empty_fields(self, mock_kv_store_class):
        """
        TC-US1-003: Edit item name with empty fields_to_update

        Given: User provides empty fields_to_update
        When: Call handle_update_last_entry(user_id, {})
        Then: Error message "未指定要更新的欄位"
        """
        # Arrange
        user_id = "test_user_789"

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store

        # Act
        result_message = handle_update_last_entry(user_id, {})

        # Assert
        assert "未指定要更新的欄位" in result_message
        assert mock_kv_store.get.call_count == 0  # Should not even try to read


class TestEditCategory:
    """US2: Edit category (分類)"""

    @patch('app.line_handler.KVStore')
    def test_edit_category_success(self, mock_kv_store_class):
        """
        TC-US2-001: Edit category success scenario

        Given: KV contains transaction with 分類="飲食", 品項="午餐"
        When: Call handle_update_last_entry(user_id, {"分類": "交通"})
        Then: 分類="交通", 品項="午餐" (unchanged)
        """
        # Arrange
        user_id = "test_user_category"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "午餐",
            "分類": "飲食",
            "原幣金額": 120.0
        }

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store
        mock_kv_store.get.side_effect = [original_transaction, original_transaction]
        mock_kv_store.set.return_value = True

        # Act
        result_message = handle_update_last_entry(user_id, {"分類": "交通"})

        # Assert
        assert "修改成功" in result_message
        assert "分類" in result_message
        assert "交通" in result_message

        # Verify updated transaction
        call_args = mock_kv_store.set.call_args
        updated_tx = call_args[0][1]
        assert updated_tx["分類"] == "交通"  # Updated
        assert updated_tx["品項"] == "午餐"  # Unchanged

    @patch('app.line_handler.KVStore')
    def test_edit_category_preserve_on_empty(self, mock_kv_store_class):
        """
        TC-US2-002: Edit category with empty value preserves original

        Given: KV contains transaction with 分類="飲食"
        When: Call handle_update_last_entry(user_id, {"分類": ""})
        Then: 分類="飲食" (preserved, no update)
        """
        # Arrange
        user_id = "test_user_empty_cat"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "午餐",
            "分類": "飲食",
            "原幣金額": 120.0
        }

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store
        mock_kv_store.get.side_effect = [original_transaction, original_transaction]
        mock_kv_store.set.return_value = True

        # Act
        result_message = handle_update_last_entry(user_id, {"分類": ""})

        # Assert: Still shows success (but field not actually updated due to empty check)
        assert "修改成功" in result_message

        # Verify transaction preserves original category
        call_args = mock_kv_store.set.call_args
        updated_tx = call_args[0][1]
        assert updated_tx["分類"] == "飲食"  # Preserved (empty value skipped)


class TestEditProject:
    """US3: Edit project (專案)"""

    @patch('app.line_handler.KVStore')
    def test_edit_project_success(self, mock_kv_store_class):
        """
        TC-US3-001: Edit project success scenario

        Given: KV contains transaction with 專案="日常"
        When: Call handle_update_last_entry(user_id, {"專案": "Q4 行銷活動"})
        Then: 專案="Q4 行銷活動"
        """
        # Arrange
        user_id = "test_user_project"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "印刷費",
            "專案": "日常",
            "原幣金額": 500.0
        }

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store
        mock_kv_store.get.side_effect = [original_transaction, original_transaction]
        mock_kv_store.set.return_value = True

        # Act
        result_message = handle_update_last_entry(user_id, {"專案": "Q4 行銷活動"})

        # Assert
        assert "修改成功" in result_message
        assert "專案" in result_message
        assert "Q4 行銷活動" in result_message

        # Verify updated transaction
        call_args = mock_kv_store.set.call_args
        updated_tx = call_args[0][1]
        assert updated_tx["專案"] == "Q4 行銷活動"  # Updated


class TestEditAmount:
    """US4: Edit amount (原幣金額)"""

    @patch('app.line_handler.KVStore')
    def test_edit_amount_success(self, mock_kv_store_class):
        """
        TC-US4-001: Edit amount success scenario

        Given: KV contains transaction with 原幣金額=100.0
        When: Call handle_update_last_entry(user_id, {"原幣金額": 350.0})
        Then: 原幣金額=350.0
        """
        # Arrange
        user_id = "test_user_amount"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "午餐",
            "原幣金額": 100.0
        }

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store
        mock_kv_store.get.side_effect = [original_transaction, original_transaction]
        mock_kv_store.set.return_value = True

        # Act
        result_message = handle_update_last_entry(user_id, {"原幣金額": 350.0})

        # Assert
        assert "修改成功" in result_message
        assert "原幣金額" in result_message
        assert "350" in result_message

        # Verify updated transaction
        call_args = mock_kv_store.set.call_args
        updated_tx = call_args[0][1]
        assert updated_tx["原幣金額"] == 350.0  # Updated

    @patch('app.line_handler.KVStore')
    def test_edit_amount_zero_is_valid(self, mock_kv_store_class):
        """
        TC-US4-002: Edit amount to zero (valid for free items)

        Given: KV contains transaction with 原幣金額=100.0
        When: Call handle_update_last_entry(user_id, {"原幣金額": 0})
        Then: 原幣金額=0 (accepted)
        """
        # Arrange
        user_id = "test_user_zero_amount"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "免費贈品",
            "原幣金額": 100.0
        }

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store
        mock_kv_store.get.side_effect = [original_transaction, original_transaction]
        mock_kv_store.set.return_value = True

        # Act
        result_message = handle_update_last_entry(user_id, {"原幣金額": 0})

        # Assert
        assert "修改成功" in result_message

        # Verify updated transaction
        call_args = mock_kv_store.set.call_args
        updated_tx = call_args[0][1]
        assert updated_tx["原幣金額"] == 0  # Updated to zero


class TestConcurrencyControl:
    """Optimistic locking and concurrency control"""

    @patch('app.line_handler.KVStore')
    def test_optimistic_lock_detects_concurrent_update(self, mock_kv_store_class):
        """
        TC-CONCURRENCY-001: Optimistic lock detects concurrent modification

        Given: Transaction exists with 交易ID="20251129-140000"
        When: Another update changes the transaction during our update (交易ID changes)
        Then: Error message "交易已變更，請重新操作"
        """
        # Arrange
        user_id = "test_user_concurrency"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "午餐",
            "原幣金額": 100.0
        }

        # Simulate concurrent update: different transaction ID on re-read
        updated_by_someone_else = {
            "交易ID": "20251129-140100",  # Changed by concurrent update
            "品項": "晚餐",
            "原幣金額": 150.0
        }

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store

        # First get: return original
        # Second get (optimistic lock check): return updated version
        mock_kv_store.get.side_effect = [original_transaction, updated_by_someone_else]

        # Act
        result_message = handle_update_last_entry(user_id, {"品項": "工作午餐"})

        # Assert
        assert "交易已變更" in result_message
        assert mock_kv_store.set.call_count == 0  # Should NOT save

    @patch('app.line_handler.KVStore')
    def test_transaction_expired_during_update(self, mock_kv_store_class):
        """
        TC-CONCURRENCY-002: Transaction expired during update

        Given: Transaction exists initially
        When: Transaction expires (TTL) during update process
        Then: Error message "交易記錄已過期"
        """
        # Arrange
        user_id = "test_user_expired"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "午餐",
            "原幣金額": 100.0
        }

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store

        # First get: return original
        # Second get (optimistic lock check): return None (expired)
        mock_kv_store.get.side_effect = [original_transaction, None]

        # Act
        result_message = handle_update_last_entry(user_id, {"品項": "工作午餐"})

        # Assert
        assert "已過期" in result_message
        assert mock_kv_store.set.call_count == 0  # Should NOT save


class TestMultiFieldUpdate:
    """Test updating multiple fields at once"""

    @patch('app.line_handler.KVStore')
    def test_update_multiple_fields(self, mock_kv_store_class):
        """
        TC-MULTI-001: Update multiple fields in one operation

        Given: Transaction with 品項="午餐", 分類="飲食", 原幣金額=100.0
        When: Call handle_update_last_entry(user_id, {"品項": "工作午餐", "原幣金額": 150.0})
        Then: Both fields updated, other fields unchanged
        """
        # Arrange
        user_id = "test_user_multi"
        original_transaction = {
            "交易ID": "20251129-140000",
            "品項": "午餐",
            "分類": "飲食",
            "原幣金額": 100.0,
            "付款方式": "現金"
        }

        mock_kv_store = MagicMock()
        mock_kv_store_class.return_value = mock_kv_store
        mock_kv_store.get.side_effect = [original_transaction, original_transaction]
        mock_kv_store.set.return_value = True

        # Act
        result_message = handle_update_last_entry(user_id, {
            "品項": "工作午餐",
            "原幣金額": 150.0
        })

        # Assert
        assert "修改成功" in result_message

        # Verify both fields updated
        call_args = mock_kv_store.set.call_args
        updated_tx = call_args[0][1]
        assert updated_tx["品項"] == "工作午餐"  # Updated
        assert updated_tx["原幣金額"] == 150.0  # Updated
        assert updated_tx["分類"] == "飲食"  # Unchanged
        assert updated_tx["付款方式"] == "現金"  # Unchanged
