from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    role = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    cases = relationship("Case", back_populates="creator", cascade="all, delete-orphan")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_by_uid = Column(String, ForeignKey("users.uid"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    brand = Column(String, nullable=True)
    model = Column(String, nullable=True)
    series = Column(String, nullable=True)
    error_code = Column(String, nullable=True)
    symptom = Column(Text, nullable=True)
    checks_done = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    source = Column(String, nullable=True)
    tags = Column(JSONB, nullable=True)
    resolution_note = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    creator = relationship("User", back_populates="cases")

    def touch_updated_at(self):
        self.updated_at = datetime.utcnow()

    def mark_resolved(self, note: str):
        now = datetime.utcnow()
        self.status = "resolved"
        self.resolution_note = note
        self.resolved_at = now
        self.closed_at = self.closed_at or now
        self.touch_updated_at()

    def set_status(self, status: str):
        now = datetime.utcnow()
        self.status = status
        if status == "resolved":
            self.closed_at = self.closed_at or now
            self.resolved_at = self.resolved_at or now
        else:
            self.closed_at = None
            self.resolved_at = None
            self.resolution_note = None
        self.touch_updated_at()
