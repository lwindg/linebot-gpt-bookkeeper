# -*- coding: utf-8 -*-
"""
Notion Service Module

This module provides direct integration with Notion API to create and update pages.
"""

import logging
import requests
from typing import Optional, Dict, Any, List
from app.config import NOTION_TOKEN, NOTION_DATABASE_ID
from app.gpt.types import BookkeepingEntry
from app.services.exchange_rate import ExchangeRateService

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"

class NotionService:
    def __init__(self):
        self.token = NOTION_TOKEN
        self.database_id = NOTION_DATABASE_ID
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION
        }

    def _get_batch_id(self, transaction_id: str) -> Optional[str]:
        if "-" in transaction_id and transaction_id[-3:].startswith("-"):
            return transaction_id.rsplit("-", 1)[0]
        return None

    def _get_prop_number(self, prop: Optional[Dict[str, Any]]) -> Optional[float]:
        """Safely extract number value from Notion property."""
        if prop and isinstance(prop, dict):
            return prop.get("number")
        return None

    def _get_prop_select(self, prop: Optional[Dict[str, Any]]) -> Optional[str]:
        """Safely extract select name from Notion property."""
        if prop and isinstance(prop, dict) and prop.get("select"):
            return prop.get("select", {}).get("name")
        return None

    def _get_prop_rich_text(self, prop: Optional[Dict[str, Any]]) -> str:
        """Safely extract plain text from Notion rich_text property."""
        if prop and isinstance(prop, dict) and prop.get("rich_text"):
            rich_text = prop.get("rich_text", [])
            if rich_text:
                text_obj = rich_text[0].get("text")
                if text_obj:
                    return text_obj.get("content", "").strip()
        return ""

    def _build_properties(self, entry: BookkeepingEntry) -> Dict[str, Any]:
        """
        Map BookkeepingEntry to Notion properties.
        """
        properties = {
            "品項": {"title": [{"text": {"content": entry.品項 or ""}}]},
            "日期": {"date": {"start": entry.日期}} if entry.日期 else None,
            "原幣別": {"select": {"name": entry.原幣別 or "TWD"}},
            "原幣金額": {"number": entry.原幣金額 or 0},
            "匯率": {"number": entry.匯率 or 1.0},
            "分類": {"select": {"name": entry.分類}} if entry.分類 and entry.分類 != "N/A" else None,
            "專案": {"select": {"name": entry.專案 or "日常"}},
            "交易ID": {"rich_text": [{"text": {"content": entry.交易ID or ""}}]},
            "明細說明": {"rich_text": [{"text": {"content": entry.明細說明 or ""}}]},
            "代墊狀態": {"select": {"name": entry.代墊狀態 or "無"}},
            "收款／支付對象": {"rich_text": [{"text": {"content": entry.收款支付對象 or ""}}]},
            "交易類型": {"select": {"name": entry.交易類型 or "支出"}},
            "付款方式": {"select": {"name": entry.付款方式}} if entry.付款方式 and entry.付款方式 != "N/A" else None,
            "必要性": {"select": {"name": entry.必要性}} if entry.必要性 and entry.必要性 != "N/A" else None,
            "附註": {"rich_text": [{"text": {"content": entry.附註 or ""}}]},
        }

        # Handle 手續費 if present (though not in BookkeepingEntry class, it was in mission description)
        # Wait, BookkeepingEntry doesn't have 手續費. Let me check if I missed it.
        # Mission says: "Number: 原幣金額/匯率/手續費"
        # I'll check if entry has it or if I should skip it.
        if hasattr(entry, '手續費'):
            properties["手續費"] = {"number": getattr(entry, '手續費') or 0}

        batch_id = self._get_batch_id(entry.交易ID) if entry.交易ID else None
        if batch_id:
            properties["批次ID"] = {"rich_text": [{"text": {"content": batch_id}}]}

        # Filter out None values
        return {k: v for k, v in properties.items() if v is not None}

    def create_page(self, entry: BookkeepingEntry) -> bool:
        """
        Create a new page in Notion database.
        """
        if not self.token or not self.database_id:
            logger.warning("Notion token or database ID not configured")
            return False

        url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": self._build_properties(entry)
        }

        try:
            logger.info(f"Creating Notion page for transaction {entry.交易ID}")
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Notion page created successfully: {entry.交易ID}")
                return True
            else:
                logger.error(f"Notion API failed with status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error creating Notion page: {e}")
            return False

    def archive_page(self, page_id: str) -> bool:
        """Archive a Notion page by page_id (soft delete)."""
        if not self.token:
            logger.warning("Notion token not configured")
            return False

        url = f"https://api.notion.com/v1/pages/{page_id}"
        try:
            response = requests.patch(url, json={"archived": True}, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return True
            logger.error(f"Notion API archive failed with status {response.status_code}: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error archiving Notion page: {e}")
            return False

    def archive_by_transaction_id(self, transaction_id: str, *, ignore_missing: bool = False) -> bool:
        """Archive the first page found for a given 交易ID.

        Args:
            transaction_id: Target transaction id.
            ignore_missing: If True, treat missing pages as success.
        """
        page_id = self._find_page_by_transaction_id(transaction_id)
        if not page_id:
            if ignore_missing:
                logger.info(f"No Notion page found for 交易ID: {transaction_id}, skipping archive")
                return True
            logger.error(f"Could not find Notion page with 交易ID: {transaction_id}")
            return False
        return self.archive_page(page_id)

    def update_page(self, transaction_id: str, fields_to_update: Dict[str, Any]) -> bool:
        """
        Update an existing page in Notion by finding it with 交易ID.
        """
        if not self.token or not self.database_id:
            logger.warning("Notion token or database ID not configured")
            return False

        # 1. Search for the page with the given transaction_id
        page_id = self._find_page_by_transaction_id(transaction_id)
        if not page_id:
            logger.error(f"Could not find Notion page with 交易ID: {transaction_id}")
            return False

        # 2. Update the page
        url = f"https://api.notion.com/v1/pages/{page_id}"
        
        notion_properties = {}
        for key, value in fields_to_update.items():
            # Map field names to Notion properties
            if key == "品項":
                notion_properties["品項"] = {"title": [{"text": {"content": value}}]}
            elif key in ["原幣金額", "匯率", "手續費"]:
                notion_properties[key] = {"number": value}
            elif key in ["分類", "專案", "原幣別", "代墊狀態", "交易類型", "付款方式", "必要性"]:
                if value and value != "N/A":
                    notion_properties[key] = {"select": {"name": value}}
            elif key in ["明細說明", "交易ID", "批次ID", "附註"]:
                notion_properties[key] = {"rich_text": [{"text": {"content": value}}]}
            elif key == "收款支付對象":
                notion_properties["收款／支付對象"] = {"rich_text": [{"text": {"content": value}}]}
            elif key == "日期":
                notion_properties["日期"] = {"date": {"start": value}}

        if not notion_properties:
            logger.warning("No valid fields to update for Notion")
            return True

        try:
            logger.info(f"Updating Notion page {page_id} for transaction {transaction_id}")
            response = requests.patch(url, json={"properties": notion_properties}, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Notion page updated successfully: {transaction_id}")
                return True
            else:
                logger.error(f"Notion API update failed with status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error updating Notion page: {e}")
            return False

    def _find_page_by_transaction_id(self, transaction_id: str) -> Optional[str]:
        """
        Find page ID by searching for 交易ID property.
        """
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {
            "filter": {
                "property": "交易ID",
                "rich_text": {
                    "equals": transaction_id
                }
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    return results[0]["id"]
            else:
                logger.error(f"Notion API query failed: {response.text}")
        except Exception as e:
            logger.error(f"Error searching Notion page: {e}")
            
        return None

    def get_database_options(self, property_name: str) -> List[str]:
        """
        Fetch options for a select property from Notion database schema.
        """
        if not self.token or not self.database_id:
            logger.warning("Notion token or database ID not configured")
            return []

        url = f"https://api.notion.com/v1/databases/{self.database_id}"
        
        try:
            logger.info(f"Fetching Notion database schema for property: {property_name}")
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                properties = data.get("properties", {})
                prop = properties.get(property_name)
                
                if not prop:
                    logger.error(f"Property '{property_name}' not found in Notion database")
                    return []
                
                if prop.get("type") == "select":
                    select_data = prop.get("select")
                    options = select_data.get("options", []) if isinstance(select_data, dict) else []
                    return [opt["name"] for opt in options if isinstance(opt, dict) and "name" in opt]
                elif prop.get("type") == "multi_select":
                    ms_data = prop.get("multi_select")
                    options = ms_data.get("options", []) if isinstance(ms_data, dict) else []
                    return [opt["name"] for opt in options if isinstance(opt, dict) and "name" in opt]
                else:
                    logger.error(f"Property '{property_name}' is not a select or multi_select type")
                    return []
            else:
                logger.error(f"Notion API failed with status {response.status_code}: {response.text}")
                return []
        except Exception as e:
            logger.error(f"Unexpected error fetching Notion database options: {e}")
            return []

    def get_project_settlement(self, project_name: str) -> Dict[str, Any]:
        """
        Query Notion for all pages where "專案" matches.
        Calculate totals: Total Spent (Sum of Amount * FX), Grouped by Counterparty and Status (代墊, 需支付).
        """
        if not self.token or not self.database_id:
            logger.warning("Notion token or database ID not configured")
            return {}

        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {
            "filter": {
                "property": "專案",
                "select": {
                    "equals": project_name
                }
            }
        }
        
        all_results = []
        has_more = True
        start_cursor = None
        
        exchange_rate_service = ExchangeRateService()
        
        try:
            while has_more:
                if start_cursor:
                    payload["start_cursor"] = start_cursor
                
                response = requests.post(url, json=payload, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    all_results.extend(data.get("results", []))
                    has_more = data.get("has_more", False)
                    start_cursor = data.get("next_cursor")
                else:
                    logger.error(f"Notion API query failed: {response.text}")
                    break
            
            # Process results
            total_spent = 0.0
            # Grouped by Counterparty and Status
            # settlement_data = { counterparty: { status: amount } }
            settlement_data = {}
            
            for page in all_results:
                props = page.get("properties", {})
                
                # Get basic info with hardened access
                currency = self._get_prop_select(props.get("原幣別")) or "TWD"
                amount = self._get_prop_number(props.get("原幣金額")) or 0
                fee = self._get_prop_number(props.get("手續費")) or 0
                
                # Get FX with fallback
                fx = self._get_prop_number(props.get("匯率"))
                
                if fx is None or fx == 0:
                    if currency == "TWD":
                        fx = 1.0
                    else:
                        # Try to fetch from API
                        fx = exchange_rate_service.get_rate(currency)
                        if fx is None:
                            logger.warning(f"Missing exchange rate for {currency} in Notion and API. Skipping item.")
                            continue
                
                # Calculate TWD amount with rounding per item (matches Notion View v2.9)
                twd_amount = round(amount * fx + fee)
                
                # Get Status and Type with hardened access
                status = self._get_prop_select(props.get("代墊狀態")) or "無"
                tx_type = self._get_prop_select(props.get("交易類型")) or "支出"
                
                # Only include "Spending" types in total_spent
                # (Ignore Withdrawal, Transfer, Income)
                if tx_type in ("支出", "代墊", "需支付"):
                    total_spent += twd_amount
                
                # Only include in settlement grouping if status is not "無"
                if status == "無":
                    continue

                # Get Counterparty with hardened access
                counterparty = self._get_prop_rich_text(props.get("收款／支付對象")) or "未知"
                
                # Skip if counterparty is unknown and it's not a status that requires settlement
                if counterparty == "未知" and status not in ("代墊", "需支付"):
                    continue
                
                if counterparty not in settlement_data:
                    settlement_data[counterparty] = {}
                
                if status not in settlement_data[counterparty]:
                    settlement_data[counterparty][status] = 0.0
                
                settlement_data[counterparty][status] += twd_amount
                
            return {
                "project_name": project_name,
                "total_spent": total_spent,
                "settlement": settlement_data
            }
            
        except Exception as e:
            logger.error(f"Error getting project settlement: {e}")
            return {}
