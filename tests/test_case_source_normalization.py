import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import normalize_case_source
from app.storage_json import JsonCaseStore


def test_normalize_case_source_maps_legacy_values_to_mixed():
    assert normalize_case_source("ai+manuals") == "mixed"
    assert normalize_case_source("ai+cases") == "mixed"
    assert normalize_case_source("ai+manuals+cases") == "mixed"


def test_json_store_reads_legacy_source_as_mixed(tmp_path):
    db_path = tmp_path / "cases.json"
    db_path.write_text(
        json.dumps(
            {
                "next_id": 2,
                "cases": [
                    {
                        "id": 1,
                        "title": "Legacy case",
                        "description": "desc",
                        "brand": "Brand",
                        "model": "Model",
                        "symptom": "symptom",
                        "status": "open",
                        "source": "ai+manuals",
                        "tags": [],
                        "created_by_uid": "legacy-user",
                        "created_at": "2026-01-01T00:00:00",
                        "updated_at": "2026-01-01T00:00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = JsonCaseStore(path=str(db_path))
    cases = store.list_cases()

    assert len(cases) == 1
    assert cases[0].source == "mixed"
