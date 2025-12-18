from app.project_resolver import infer_project


def test_infer_project_default_daily() -> None:
    assert infer_project("") == "日常"
    assert infer_project("家庭/餐飲/午餐") == "日常"


def test_infer_project_health_mapping() -> None:
    assert infer_project("健康/醫療") == "健康檢查"
    assert infer_project("健康/運動") == "健康檢查"


def test_infer_project_trip_mapping() -> None:
    assert infer_project("行程/登山") == "登山行程"
    assert infer_project("行程/交通") == "登山行程"


def test_infer_project_gift_mapping() -> None:
    assert infer_project("禮物/節慶") == "紀念日／送禮"
    assert infer_project("禮物/生日") == "紀念日／送禮"


def test_infer_project_normalize_fullwidth_separator() -> None:
    assert infer_project("健康／醫療") == "健康檢查"

