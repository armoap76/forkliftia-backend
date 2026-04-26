import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import (
    NO_MANUAL_ORIENTATIVE_TEXT,
    NO_SIMILAR_CASES_TEXT,
    PUBLIC_REFERENCE_TEXT_NO_MANUAL,
    PUBLIC_REFERENCE_TEXT_WITH_MANUAL,
    _normalize_public_reference_section,
    _normalize_similar_cases_section,
    _sanitize_public_diagnosis_text,
)


def test_reference_section_uses_manual_text_when_manual_present():
    diagnosis = "🔍 PROBABLE CAUSE:\nX\n\n📚 REFERENCIA:\nOld"

    normalized = _normalize_public_reference_section(
        diagnosis,
        manual_context_present=True,
    )

    assert f"📚 REFERENCIA:\n{PUBLIC_REFERENCE_TEXT_WITH_MANUAL}" in normalized


def test_reference_section_uses_no_manual_text_when_manual_missing():
    diagnosis = "🔍 PROBABLE CAUSE:\nX"

    normalized = _normalize_public_reference_section(
        diagnosis,
        manual_context_present=False,
    )

    assert f"📚 REFERENCIA:\n{PUBLIC_REFERENCE_TEXT_NO_MANUAL}" in normalized


def test_similar_cases_section_forces_no_matches_copy_when_absent():
    diagnosis = "🔍 PROBABLE CAUSE:\nX\n\n💡 SIMILAR CASES:\nEn casos similares..."

    normalized = _normalize_similar_cases_section(
        diagnosis,
        similar_case_present=False,
    )

    assert f"💡 SIMILAR CASES:\n{NO_SIMILAR_CASES_TEXT}" in normalized


def test_sanitize_removes_false_source_claims_and_injects_orientative_notice():
    raw = (
        "🔍 PROBABLE CAUSE:\n"
        "Según la referencia técnica disponible, se ha observado un fallo.\n\n"
        "💡 SIMILAR CASES:\n"
        "Casos documentados muestran el mismo patrón."
    )

    sanitized = _sanitize_public_diagnosis_text(
        raw,
        brand="Clark",
        model="TM15",
        series=None,
        controller=None,
        manual_hit=None,
        matched_case_present=False,
    )

    assert "según la referencia técnica disponible" not in sanitized.lower()
    assert "casos documentados muestran" not in sanitized.lower()
    assert NO_MANUAL_ORIENTATIVE_TEXT in sanitized
