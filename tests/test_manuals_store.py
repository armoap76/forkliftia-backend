import json

from app.manuals_store import (
    normalize_brand,
    normalize_controller,
    normalize_error_code,
    normalize_model,
    normalize_series,
    search_manual_error,
)


def test_normalization_helpers():
    assert normalize_brand(" LíNde /BT ") == "linde-bt"
    assert normalize_model("OSE 250") == "ose250"
    assert normalize_model("E-16") == "e16"
    assert normalize_series("R14-1275") == "1275"
    assert normalize_series("Serie X") == "seriex"
    assert normalize_controller(" ZAPI / Gen 4 ") == "zapi-gen-4"
    assert normalize_error_code("e 223") == "E223"


def test_search_manual_error_with_common_series(tmp_path):
    base = tmp_path
    manual_dir = base / "linde" / "common" / "1275"
    manual_dir.mkdir(parents=True)

    manual_content = {
        "brand": "Linde",
        "model": "E16/E20/E25",
        "series": "1275",
        "errors": [
            {
                "code": "E 223",
                "manual_summary": "Hydraulic pressure sensor fault",
                "actions_summary": "Check wiring",
            }
        ],
    }
    (manual_dir / "errors.json").write_text(json.dumps(manual_content), encoding="utf-8")

    hit = search_manual_error(
        base_path=str(base),
        brand="LÍNDE",
        model="E20",
        series="R14-1275",
        controller=None,
        error_code="e-223",
    )

    assert hit is not None
    assert hit["error"]["manual_summary"] == "Hydraulic pressure sensor fault"


def test_search_manual_error_prefers_controller_specific_path(tmp_path):
    base = tmp_path
    generic_dir = base / "linde" / "e20" / "1275"
    generic_dir.mkdir(parents=True)
    controller_dir = base / "linde" / "e20" / "1275" / "zapi"
    controller_dir.mkdir(parents=True)

    generic_manual = {
        "brand": "Linde",
        "model": "E20",
        "series": "1275",
        "errors": [{"code": "E223", "manual_summary": "Generic summary", "actions_summary": "Generic actions"}],
    }
    controller_manual = {
        "brand": "Linde",
        "model": "E20",
        "series": "1275",
        "errors": [{"code": "E223", "manual_summary": "ZAPI summary", "actions_summary": "ZAPI actions"}],
    }
    (generic_dir / "errors.json").write_text(json.dumps(generic_manual), encoding="utf-8")
    (controller_dir / "errors.json").write_text(json.dumps(controller_manual), encoding="utf-8")

    hit = search_manual_error(
        base_path=str(base),
        brand="Linde",
        model="E20",
        series="1275",
        controller=" ZAPI ",
        error_code="E223",
    )

    assert hit is not None
    assert hit["error"]["manual_summary"] == "ZAPI summary"
