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
            "分類": {"select": {"name": entry.分類}} if entry.分類 and entry.分類 != "NA" else None,
            "專案": {"select": {"name": entry.專案 or "日常"}},
            "交易ID": {"rich_text": [{"text": {"content": entry.交易ID or ""}}]},
            "明細說明": {"rich_text": [{"text": {"content": entry.明細說明 or ""}}]},
            "代墊狀態": {"select": {"name": entry.代墊狀態 or "無"}},
            "收款／支付對象": {"rich_text": [{"text": {"content": entry.收款支付對象 or ""}}]},
            "交易類型": {"select": {"name": entry.交易類型 or "支出"}},
            "付款方式": {"select": {"name": entry.付款方式}} if entry.付款方式 and entry.付款方式 != "NA" else None,
            "必要性": {"select": {"name": entry.必要性}} if entry.必要性 and entry.必要性 != "NA" else None,
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
                if value and value != "NA":
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
                    options = prop.get("select", {}).get("options", [])
                    return [opt["name"] for opt in options]
                elif prop.get("type") == "multi_select":
                    options = prop.get("multi_select", {}).get("options", [])
                    return [opt["name"] for opt in options]
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
                
                # Get Amount and FX with safe access
                amount = props.get("原幣金額", {}).get("number") if props.get("原幣金額") else 0
                fx = props.get("匯率", {}).get("number") if props.get("匯率") else 1.0
                fee = props.get("手續費", {}).get("number") if props.get("手續費") else 0
                
                # Ensure they are not None (in case property exists but number is null)
                amount = amount if amount is not None else 0
                fx = fx if fx is not None else 1.0
                fee = fee if fee is not None else 0
                
                # Calculate TWD amount with rounding per item (matches Notion View v2.9)
                twd_amount = round(amount * fx + fee)
                
                total_spent += twd_amount
                
                # Get Counterparty with safe access
                counterparty_rich_text = props.get("收款／支付對象", {}).get("rich_text", [])
                counterparty = "未知"
                if counterparty_rich_text:
                    text_obj = counterparty_rich_text[0].get("text")
                    if text_obj:
                        counterparty = text_obj.get("content", "未知")
                
                # Get Status with safe access
                status = props.get("代墊狀態", {}).get("select", {}).get("name") if props.get("代墊狀態") and props.get("代墊狀態").get("select") else "無"
                
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
