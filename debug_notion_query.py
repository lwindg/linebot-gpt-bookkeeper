
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def debug_query(project_name):
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    payload = {
        "filter": {
            "property": "專案",
            "select": {
                "equals": project_name
            }
        }
    }
    
    print(f"Querying for: '{project_name}'")
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status: {response.status_code}")
    data = response.json()
    results = data.get("results", [])
    print(f"Results count: {len(results)}")
    if results:
        for r in results[:2]:
            print(f"- {r['properties']['品項']['title'][0]['text']['content']}")

if __name__ == "__main__":
    debug_query("20260206-14 日本玩雪")
    debug_query("日本玩雪")
