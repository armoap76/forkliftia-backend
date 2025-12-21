import json
import os
from typing import Optional, Dict, Any

def search_manual_error(
    base_path: str,
    brand: str,
    model: str,
    series: Optional[str],
    error_code: Optional[str],
) -> Optional[Dict[str, Any]]:

    if not brand or not model or not error_code:
        return None

    b = brand.lower().strip()
    m = model.lower().strip()
    s = (series or "all").lower().strip()
    ecode = error_code.lower().strip()

    # orden de búsqueda: serie específica → base
    paths = [
        os.path.join(base_path, b, m, f"{s}.json"),
        os.path.join(base_path, b, m, "base.json"),
    ]

    for p in paths:
        if not os.path.exists(p):
            continue

        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        for err in data.get("errors", []):
            code = err.get("code", "").lower()
            if code == ecode or ecode in code:
                return {
                    "source": "manuals",
                    "brand": data.get("brand"),
                    "model": data.get("model"),
                    "series": data.get("series"),
                    "error": err,
                }

    return None
