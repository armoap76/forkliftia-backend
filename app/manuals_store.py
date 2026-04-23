import json
import logging
import os
import re
import unicodedata
from typing import Optional, Dict, Any


logger = logging.getLogger(__name__)


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_brand(value: Optional[str]) -> str:
    if not value:
        return ""

    cleaned = _strip_accents(value.strip().lower())
    cleaned = re.sub(r"[\s/]+", "-", cleaned)
    return cleaned.strip("-")


def normalize_model(value: Optional[str]) -> str:
    if not value:
        return ""

    cleaned = _strip_accents(value.strip().lower())
    cleaned = re.sub(r"[\s\-/]+", "", cleaned)
    return cleaned


def normalize_series(value: Optional[str]) -> str:
    if not value:
        return ""

    cleaned = _strip_accents(value.strip().lower())
    digit_groups = re.findall(r"(\d+)", cleaned)
    if digit_groups:
        return max(digit_groups, key=len)

    fallback = re.sub(r"[^a-z0-9]+", "", cleaned)
    return fallback


def normalize_controller(value: Optional[str]) -> str:
    if not value:
        return ""

    cleaned = _strip_accents(value.strip().lower())
    cleaned = re.sub(r"[\s/]+", "-", cleaned)
    return cleaned.strip("-")


def normalize_error_code(value: Optional[str]) -> str:
    if not value:
        return ""

    cleaned = value.strip().upper()
    cleaned = re.sub(r"[\s-]+", "", cleaned)
    return cleaned

def _iter_candidate_paths(
    base_path: str,
    brand: str,
    model: str,
    series: str,
    controller: str,
) -> list:
    candidates = []
    if series and controller:
        candidates.append(os.path.join(base_path, brand, model, series, controller, "errors.json"))
        candidates.append(os.path.join(base_path, brand, "common", series, controller, "errors.json"))
    if series:
        candidates.append(os.path.join(base_path, brand, model, series, "errors.json"))
    candidates.append(os.path.join(base_path, brand, model, "errors.json"))
    if series:
        candidates.append(os.path.join(base_path, brand, "common", series, "errors.json"))
    candidates.append(os.path.join(base_path, brand, "common", "errors.json"))
    return candidates


def _load_first_existing(paths: list) -> Optional[str]:
    for path in paths:
        if os.path.exists(path):
            return path

        if path.endswith("errors.json"):
            legacy_path = path[:-len("errors.json")] + "base.json"
            if os.path.exists(legacy_path):
                return legacy_path
    return None


def search_manual_error(
    base_path: str,
    brand: str,
    model: str,
    series: Optional[str],
    controller: Optional[str],
    error_code: Optional[str],
) -> Optional[Dict[str, Any]]:

    if not brand or not model or not error_code:
        return None

    normalized_brand = normalize_brand(brand)
    normalized_model = normalize_model(model)
    normalized_series = normalize_series(series)
    normalized_controller = normalize_controller(controller)
    ecode = normalize_error_code(error_code)

    if not normalized_brand or not normalized_model or not ecode:
        return None

    paths = _iter_candidate_paths(
        base_path=base_path,
        brand=normalized_brand,
        model=normalized_model,
        series=normalized_series,
        controller=normalized_controller,
    )
    logger.info("Manual lookup candidate paths: %s", paths)

    manual_path = _load_first_existing(paths)
    if not manual_path:
        return None
    logger.info("Manual lookup selected path: %s", manual_path)

    try:
        with open(manual_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.exception("Failed to read manual JSON from %s", manual_path)
        return None

    errors = data.get("errors")

    if isinstance(errors, dict):
        for code_key, err in errors.items():
            if not isinstance(err, dict):
                continue

            code = normalize_error_code(code_key)
            if code == ecode or ecode in code:
                error_data = dict(err)
                error_data.setdefault("code", code_key)
                logger.info(
                    "Manual lookup matched file %s for brand=%s model=%s series=%s controller=%s",
                    manual_path,
                    normalized_brand,
                    normalized_model,
                    normalized_series,
                    normalized_controller,
                )
                return {
                    "source": "manuals",
                    "brand": data.get("brand"),
                    "model": data.get("model"),
                    "series": data.get("series"),
                    "error": error_data,
                    "manual_path": manual_path,
                }

    elif isinstance(errors, list):
        for err in errors:
            if not isinstance(err, dict):
                continue

            code = normalize_error_code(err.get("code", ""))
            if code == ecode or ecode in code:
                logger.info(
                    "Manual lookup matched file %s for brand=%s model=%s series=%s controller=%s",
                    manual_path,
                    normalized_brand,
                    normalized_model,
                    normalized_series,
                    normalized_controller,
                )
                return {
                    "source": "manuals",
                    "brand": data.get("brand"),
                    "model": data.get("model"),
                    "series": data.get("series"),
                    "error": err,
                    "manual_path": manual_path,
                }

    return None
