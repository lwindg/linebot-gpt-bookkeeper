
from app.shared.project_resolver import match_short_term_project

options = ['日常', '旅遊', '20260206-14 日本玩雪', '日本玩雪']
value = '20260206-14 日本玩雪'

resolved, candidates = match_short_term_project(value, options)
print(f"Input: {value}")
print(f"Resolved: {resolved}")
print(f"Candidates: {candidates}")

value2 = '日本玩雪'
resolved2, candidates2 = match_short_term_project(value2, options)
print(f"\nInput: {value2}")
print(f"Resolved: {resolved2}")
print(f"Candidates: {candidates2}")
