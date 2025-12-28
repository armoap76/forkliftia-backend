from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, Field

CaseStatus = Literal["open", "resolved"]
CaseSource = Literal["cases", "ai", "manuals", "mixed"]

class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)

    brand: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    series: Optional[str] = None
    error_code: Optional[str] = None

    symptom: str = Field(..., min_length=1)
    checks_done: Optional[str] = None

    diagnosis: Optional[str] = None  # en open puede estar vacío
    status: CaseStatus = "open"
    source: CaseSource = "ai"

    created_by_uid: str = Field(..., min_length=1)

    tags: List[str] = Field(default_factory=list)
    created_by_uid: Optional[str] = None

class Case(CaseCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
closed_at: Optional[datetime] = None

