
import os
import sys
import logging
import yaml

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.notion_service import NotionService

logging.basicConfig(level=logging.INFO)

def check_categories():
    # 1. Load categories from YAML
    yaml_path = "app/config/classifications.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    yaml_categories = set()
    for top_level, items in config.get("categories", {}).items():
        for item in items:
            yaml_categories.add(item.replace("／", "/").strip())

    # 2. Fetch options from Notion
    service = NotionService()
    notion_options = service.get_database_options("分類")
    notion_categories = set(notion_options)

    print("\n--- Category Comparison Report ---")
    
    # 3. Categories in YAML but NOT in Notion
    missing_in_notion = yaml_categories - notion_categories
    print(f"\n[YAML 內有，但 Notion 下拉選單沒出現的] ({len(missing_in_notion)}):")
    for cat in sorted(missing_in_notion):
        print(f" - {cat}")

    # 4. Categories in Notion but NOT in YAML
    missing_in_yaml = notion_categories - yaml_categories
    print(f"\n[Notion 下拉選單有，但 YAML 沒定義的] ({len(missing_in_yaml)}):")
    for cat in sorted(missing_in_yaml):
        print(f" - {cat}")
    
    # 5. Check actual usage in Notion (last 1000 items)
    print("\n[掃描 Notion 最近 100 筆資料的實際使用狀況...]")
    url = f"https://api.notion.com/v1/databases/{service.database_id}/query"
    headers = {
        "Authorization": f"Bearer {service.token}",
        "Notion-Version": "2022-06-28"
    }
    response = requests.post(url, json={"page_size": 100}, headers=headers)
    used_in_last_100 = set()
    if response.status_code == 200:
        results = response.json().get("results", [])
        for res in results:
            cat_prop = res["properties"].get("分類", {}).get("select")
            if cat_prop:
                used_in_last_100.add(cat_prop["name"])
        
        unused_options = notion_categories - used_in_last_100
        print(f"\n[最近 100 筆沒用到的選單項目] ({len(unused_options)}):")
        # (This is just a hint, doesn't mean they are never used)
        for cat in sorted(unused_options):
            if cat in notion_categories:
                print(f" - {cat}")

if __name__ == "__main__":
    import requests
    check_categories()
