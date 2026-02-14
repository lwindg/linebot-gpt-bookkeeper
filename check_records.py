
import requests
import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config import NOTION_TOKEN, NOTION_DATABASE_ID

def check_records():
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
    }
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    payload = {
        "page_size": 10,
        "sorts": [{"property": "日期", "direction": "descending"}]
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        for result in data.get("results", []):
            item = result["properties"]["品項"]["title"][0]["text"]["content"]
            proj = result["properties"].get("專案", {}).get("select", {})
            proj_name = proj.get("name") if proj else "None"
            print(f"Item: '{item}', Project: {repr(proj_name)}")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    check_records()
