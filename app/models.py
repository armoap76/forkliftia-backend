from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

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


class Case(CaseCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    creator_public_name: Optional[str] = None


class UserProfile(BaseModel):
    uid: str
    public_name: Optional[str] = None


class PublicNameUpdate(BaseModel):
    public_name: str


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = Field(None, min_length=1)
    brand: Optional[str] = Field(None, min_length=1)
    model: Optional[str] = Field(None, min_length=1)
    series: Optional[str] = Field(None, min_length=1)
    error_code: Optional[str] = Field(None, min_length=1)
    symptom: Optional[str] = Field(None, min_length=1)
    checks_done: Optional[str] = Field(None, min_length=1)

    @field_validator(
        "title",
        "description",
        "brand",
        "model",
        "series",
        "error_code",
        "symptom",
        "checks_done",
    )
    def trim_strings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("must not be empty")
            return trimmed
        return v


class CaseCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)

    @field_validator("body")
    def trim_body(cls, v):
        text = (v or "").strip()
        if not text:
            raise ValueError("body cannot be empty")
        return text


class CaseComment(BaseModel):
    id: int
    case_id: int
    author_uid: str
    author_public_name: Optional[str] = None
    body: str
    created_at: datetime
