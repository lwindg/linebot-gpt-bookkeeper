from app.shared.category_resolver import apply_health_medical_default, resolve_category_autocorrect


def test_apply_health_medical_default_self() -> None:
    assert (
        apply_health_medical_default("健康/醫療", context_text="中醫掛號費")
        == "健康/醫療/本人"
    )


def test_apply_health_medical_default_family() -> None:
    assert (
        apply_health_medical_default("健康/醫療", context_text="妹妹掛號費")
        == "健康/醫療/家庭成員"
    )


def test_resolve_category_autocorrect_applies_medical_default() -> None:
    assert (
        resolve_category_autocorrect("健康/醫療", context_text="弟掛號費")
        == "健康/醫療/家庭成員"
    )


def test_resolve_category_autocorrect_never_returns_top_level_family() -> None:
    # Even if AI/user gives a top-level category like "家庭", it should resolve to a leaf option.
    resolved = resolve_category_autocorrect("家庭", context_text="送朋友的木頭玩具")
    assert resolved != "家庭"
    assert "/" in resolved


def test_resolve_category_autocorrect_never_returns_intermediate_path() -> None:
    # Intermediate paths like "家庭/餐飲" must resolve to a concrete leaf.
    resolved = resolve_category_autocorrect("家庭/餐飲", context_text="午餐")
    assert resolved.startswith("家庭/餐飲")
    assert resolved in (
        "家庭/餐飲/早餐",
        "家庭/餐飲/午餐",
        "家庭/餐飲/晚餐",
    )


def test_resolve_category_autocorrect_avoids_top_level_family() -> None:
    # It should not stay at the top-level (must be a concrete leaf).
    resolved = resolve_category_autocorrect("家庭")
    assert resolved != "家庭"
    assert "/" in resolved
