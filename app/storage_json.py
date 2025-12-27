from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Optional, List, Dict, Any

from .models import Case, CaseCreate
from .storage import CaseStore


def _norm(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s2 = s.strip().lower()
    return s2 if s2 else None


class JsonCaseStore(CaseStore):
    def __init__(self, path: str = "data/cases.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({"next_id": 1, "cases": []})

    def _read(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, obj: Dict[str, Any]) -> None:
        # escritura atómica: escribe temp y renombra
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, self.path)

    def _to_case(self, raw: Dict[str, Any]) -> Case:
        # datetime viene como string, lo convertimos
        raw = dict(raw)
        raw.setdefault("created_by_uid", None)
        raw.setdefault("resolution_note", None)
        raw.setdefault("resolved_at", None)

        raw["created_at"] = datetime.fromisoformat(raw["created_at"])
        raw["updated_at"] = datetime.fromisoformat(raw["updated_at"])

        if raw.get("resolved_at"):
    raw["resolved_at"] = datetime.fromisoformat(raw["resolved_at"])
else:
    raw["resolved_at"] = None

if raw.get("closed_at"):
    raw["closed_at"] = datetime.fromisoformat(raw["closed_at"])
else:
    raw["closed_at"] = None

raw.setdefault("title", f"Case #{raw.get('id')}")
raw.setdefault("description", raw.get("symptom", ""))
raw.setdefault("brand", "unknown")
raw.setdefault("model", "unknown")
raw.setdefault("symptom", raw.get("description") or "N/A")
raw.setdefault("created_by_uid", "legacy")
raw.setdefault("tags", [])
raw.setdefault("status", "open")
raw.setdefault("source", "ai")

return Case(**raw)

       

    def update_status(self, case_id: int, status: str) -> Optional[Case]:
        db = self._read()
        now = datetime.utcnow().isoformat()

        for c in db["cases"]:
            if int(c.get("id")) == int(case_id):
                c["status"] = status
                c["updated_at"] = now
                if status == "resolved":
                    c["closed_at"] = c.get("closed_at") or now
                    c["resolved_at"] = c.get("resolved_at") or now
                else:
                    c["closed_at"] = None
                    c["resolved_at"] = None
                    c["resolution_note"] = None
                self._write(db)
                return self._to_case(c)
        return None

    def resolve_case(self, case_id: int, resolution_note: str) -> Optional[Case]:
        db = self._read()
        now = datetime.utcnow().isoformat()

        for c in db["cases"]:
            if int(c.get("id")) == int(case_id):
                c["status"] = "resolved"
                c["resolution_note"] = (resolution_note or "").strip()
                c["resolved_at"] = now
                c["closed_at"] = c.get("closed_at") or now
                c["updated_at"] = now
                self._write(db)
                return self._to_case(c)

        return None
    

        
    def create_case(self, data: CaseCreate) -> Case:
        db = self._read()
        now = datetime.utcnow()

        case_id = int(db["next_id"])
        db["next_id"] = case_id + 1

        record = {
            "id": case_id,
            "title": data.title,
            "description": data.description,
            "brand": data.brand,
            "model": data.model,
            "series": data.series,
            "error_code": data.error_code,
            "symptom": data.symptom,
            "checks_done": data.checks_done,
            "diagnosis": data.diagnosis,
            "status": data.status,
            "source": data.source,
            "tags": data.tags,
            "created_by_uid": data.created_by_uid,
            "resolution_note": None,
            "resolved_at": None,
            "closed_at": None,
            "created_by_uid": data.created_by_uid,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            

        }

        db["cases"].append(record)
        self._write(db)
        return self._to_case(record)

    def list_cases(self, status: Optional[str] = None, limit: int = 200) -> List[Case]:
        db = self._read()
        items = db["cases"]

        if status:
            items = [c for c in items if c.get("status") == status]

        # últimos primero
        items = sorted(items, key=lambda c: c.get("id", 0), reverse=True)[: max(1, limit)]
        return [self._to_case(c) for c in items]

    def get_case(self, case_id: int) -> Optional[Case]:
        db = self._read()
        for c in db["cases"]:
            if int(c.get("id")) == int(case_id):
                return self._to_case(c)
        return None

    def find_resolved_by_key(
        self,
        brand: str,
        model: str,
        series: Optional[str],
        error_code: Optional[str],
    ) -> Optional[Case]:
        nb = _norm(brand)
        nm = _norm(model)
        ns = _norm(series)
        ne = _norm(error_code)

        if not nb or not nm:
            return None

        db = self._read()
        # buscamos el más reciente que matchee
        for c in sorted(db["cases"], key=lambda x: x.get("id", 0), reverse=True):
            if c.get("status") != "resolved":
                continue

            if _norm(c.get("brand")) != nb:
                continue
            if _norm(c.get("model")) != nm:
                continue

            # series y error_code: si vienen, exigimos match; si no vienen, no filtramos
            if ns and _norm(c.get("series")) != ns:
                continue
            if ne and _norm(c.get("error_code")) != ne:
                continue

            return self._to_case(c)

        return None
