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
