from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, List
import re

from pydantic import BaseModel, Field, validator

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


class MeResponse(BaseModel):
    uid: str
    public_name: Optional[str] = None


class UpdatePublicName(BaseModel):
    public_name: str

    @validator("public_name")
    def validate_public_name(cls, value: str) -> str:
        name = (value or "").strip()
        if len(name) < 3 or len(name) > 32:
            raise ValueError("public_name must be between 3 and 32 characters long")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError(
                "public_name can only contain letters, numbers, dashes and underscores"
            )
        return name

