def infer_project(category: str) -> str:
    """
    Infer project name from category path.

    Rules (3A):
    - 健康/* -> 健康檢查
    - 行程/* -> 登山行程
    - 禮物/* -> 紀念日／送禮
    - otherwise -> 日常
    """
    if not category:
        return "日常"

    normalized = category.strip().replace("／", "/")
    if not normalized:
        return "日常"

    if normalized.startswith("健康/"):
        return "健康檢查"
    if normalized.startswith("行程/"):
        return "登山行程"
    if normalized.startswith("禮物/"):
        return "紀念日／送禮"

    return "日常"

