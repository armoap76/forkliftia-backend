import base64
import json
import os
import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.db_models import UserProfile as UserProfileModel
from app.manuals_store import search_manual_error
from app.models import (
    CaseComment,
    CaseCommentCreate,
    CaseCreate,
    CaseUpdate,
    PublicNameUpdate,
    UserProfile,
)
from app.storage_db import DatabaseCaseStore
from app.database import get_session

from pydantic import BaseModel, field_validator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from openai import OpenAI

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
except ImportError:  # pragma: no cover - optional dependency
    firebase_admin = None
    firebase_auth = None


class ResolveCaseIn(BaseModel):
    resolution_note: str

    @field_validator("resolution_note")
    def validate_resolution_note(cls, v: str) -> str:
        text = (v or "").strip()
        if len(text) < 10 or len(text) > 2000:
            raise ValueError("resolution_note must be between 10 and 2000 characters")
        return text


app = FastAPI(title="ForkliftIA Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://forkliftia.com",
        "https://forkliftia-frontend.pages.dev",
    ],
    allow_origin_regex=r"^https:\/\/.*\.forkliftia-frontend\.pages\.dev$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer(auto_error=False)

# OpenAI client (lee OPENAI_API_KEY del environment)
from dotenv import load_dotenv

load_dotenv()
ADMIN_UIDS = {uid.strip() for uid in os.getenv("ADMIN_UIDS", "").split(",") if uid.strip()}
PUBLIC_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")

def get_requester_uid(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <uid>")
    token = credentials.credentials.strip()
    return extract_uid_from_token(token)


def _decode_unverified_jwt_sub(token: str) -> str:
    """Decode a JWT without verification to extract the `sub` claim.

    This is only used when Firebase Admin SDK is unavailable. It intentionally
    skips signature verification, so it must not be relied on for security.
    TODO: add proper verification when Firebase Admin is configured.
    """

    try:
        header, payload, _signature = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token structure")

    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        payload_data = json.loads(decoded.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    uid = payload_data.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token missing subject (sub) claim")
    return uid


def extract_uid_from_token(token: str) -> str:
    """Extract a stable uid from a Firebase ID token."""

    if firebase_auth is not None and firebase_admin is not None and firebase_admin._apps:
        try:
            decoded = firebase_auth.verify_id_token(token)
            uid = decoded.get("uid") or decoded.get("sub")
            if not uid:
                raise HTTPException(status_code=401, detail="Invalid token payload")
            return uid
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Fallback for environments without Firebase Admin configured.
    return _decode_unverified_jwt_sub(token)

def is_admin(uid: str) -> bool:
    return uid in ADMIN_UIDS

def ensure_case_owner_or_admin(case, uid: str) -> None:
    # case debe tener created_by_uid
    if getattr(case, "created_by_uid", None) == uid or is_admin(uid):
        return
    raise HTTPException(status_code=403, detail="Not authorized to modify this case")

def get_openai_client() -> OpenAI:
    return OpenAI()


def validate_public_name(value: str) -> str:
    public_name = (value or "").strip()
    if not PUBLIC_NAME_PATTERN.fullmatch(public_name):
        raise HTTPException(
            status_code=400,
            detail=(
                "public_name must be 3-32 characters using letters, numbers, dashes, or underscores"
            ),
        )
    return public_name


store = DatabaseCaseStore(get_session)


SYSTEM_PROMPT = """You are ForkliftIA, an expert diagnostic assistant specialized in industrial forklifts, reach trucks, pallet jacks, and material handling equipment.

YOUR ROLE:
- Act as a senior forklift technician with 20+ years of experience
- Provide practical, specific diagnostic guidance
- Reference technical manuals and real-world troubleshooting patterns
- Never guess - if information is insufficient, ask for clarification
- If information comes from a service manual, EXPLAIN it, do not speculate.
- Do NOT introduce causes not supported by manuals or documented cases.
- If the manual is incomplete, explicitly say so.
- Prefer explanation over hypothesis.

RESPONSE FORMAT (always use this structure):

🔍 PROBABLE CAUSE:
...

📋 DIAGNOSTIC STEPS:
1. ...
...

⚠️ SAFETY NOTE:
...

📚 REFERENCE:
...

💡 SIMILAR CASES:
...

RULES:
1. Be specific
2. Don't repeat checks already done
3. Prioritize most likely causes
4. Use standard terminology
5. If error code is provided, prioritize that
6. Assume the user is a trained technician
7. Keep responses concise but complete
8. If you don't know something, say so clearly
"""

@app.get("/ping")
def ping():
    return {"message": "forkliftia ok"}


@app.get("/me")
def get_me(uid: str = Depends(get_requester_uid)):
    with get_session() as session:
        profile = (
            session.query(UserProfileModel)
            .filter(UserProfileModel.uid == uid)
            .one_or_none()
        )
        return UserProfile(uid=uid, public_name=profile.public_name if profile else None)


@app.put("/me/public-name")
def set_public_name(payload: PublicNameUpdate, uid: str = Depends(get_requester_uid)):
    desired_name = validate_public_name(payload.public_name)

    with get_session() as session:
        profile = (
            session.query(UserProfileModel)
            .filter(UserProfileModel.uid == uid)
            .one_or_none()
        )

        if profile and profile.public_name:
            raise HTTPException(status_code=409, detail="Public name already set")

        now = datetime.utcnow()
        if profile is None:
            profile = UserProfileModel(
                uid=uid,
                public_name=desired_name,
                created_at=now,
                updated_at=now,
            )
            session.add(profile)
        else:
            profile.public_name = desired_name
            profile.updated_at = now

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=409, detail="Public name already taken")

        session.refresh(profile)
        return UserProfile(uid=profile.uid, public_name=profile.public_name)


@app.get("/cases")
def list_cases(
    status: str | None = None,
    limit: int = 50,
):
    return store.list_cases(status=status, limit=limit)

@app.patch("/cases/{case_id}")
def update_case(
    case_id: int,
    payload: CaseUpdate,
    uid: str = Depends(get_requester_uid),
):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.status == "resolved":
        raise HTTPException(
            status_code=403,
            detail="Case is resolved. Create a new case to continue.",
        )

    ensure_case_owner_or_admin(case, uid)

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No editable fields provided")

    updated = store.update_case(case_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")

    return updated

@app.patch("/cases/{case_id}/resolve")
def resolve_case(
    case_id: int,
    payload: ResolveCaseIn,
    uid: str = Depends(get_requester_uid),
):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    if case.status == "resolved":
        raise HTTPException(status_code=409, detail="Case is already resolved.")

    ensure_case_owner_or_admin(case, uid)

    updated = store.resolve_case(case_id, payload.resolution_note)
    if not updated:
        raise HTTPException(status_code=404, detail="case not found")

    return updated


@app.post("/cases/{case_id}/comments")
def create_case_comment(
    case_id: int,
    payload: CaseCommentCreate,
    uid: str = Depends(get_requester_uid),
):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.status == "resolved":
        raise HTTPException(
            status_code=409,
            detail="Case is resolved; comments are closed",
        )

    comment = store.create_comment(case_id, uid, payload.body)
    if not comment:
        raise HTTPException(status_code=404, detail="Case not found")

    return comment


@app.get("/cases/{case_id}/comments")
def list_case_comments(case_id: int) -> list[CaseComment]:
    comments = store.list_comments(case_id)
    if comments is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return comments

@app.post("/diagnosis")
def diagnosis(
    payload: dict,
    uid: str = Depends(get_requester_uid),
):
    client = get_openai_client()

    # Datos del frontend
    brand = payload.get("brand", "")
    model = payload.get("model", "")
    series = payload.get("series", "")
    error_code = payload.get("error_code") or "None provided"
    symptom = payload.get("symptom", "")
    checks_done = payload.get("checks_done") or "Nothing specified yet"

    # Idioma (nuevo)
    language = payload.get("language", "en")

    if language == "es":
        output_language_instruction = "Explain the diagnosis in professional LATAM Spanish."
    else:
        output_language_instruction = "Explain the diagnosis in professional technical English."

    # Buscar en manuales
    manual_hit = search_manual_error(
        base_path="app/manuals",
        brand=brand,
        model=model,
        series=series,
        error_code=None if error_code == "None provided" else error_code,
    )

    manual_context = ""
    if manual_hit:
        e = manual_hit["error"]
        manual_context = f"""
MANUAL CONTEXT (private, paraphrase only):
System: {e.get('system')}
Summary: {e.get('manual_summary')}
Actions: {e.get('actions_summary')}
"""


    # 1) Buscar caso resuelto similar
    match = store.find_resolved_by_key(
        brand=brand,
        model=model,
        series=series or None,
        error_code=None if error_code == "None provided" else error_code,
    )

    if match:
        return {
            "case_id": match.id,
            "diagnosis": match.diagnosis or "",
            "source": "cases",
        }

    user_prompt = f"""
IMPORTANT:
{output_language_instruction}
Do NOT speculate.
Explain based on manuals and documented cases only.

{manual_context}

NEW DIAGNOSTIC CASE:

Brand: {brand}
Model: {model}
Series: {series}
Error code: {error_code}

SYMPTOM DESCRIPTION:
{symptom}

ALREADY CHECKED BY TECHNICIAN:
{checks_done}

---
Provide your diagnostic analysis following the standard format.
"""


    try:
        # Responses API (recomendada para proyectos nuevos) :contentReference[oaicite:2]{index=2}
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            # opcional: bajar creatividad
            temperature=0.3,
            max_output_tokens=900,
        )

        # Texto final
        diagnosis_text = resp.output_text

        case = store.create_case(
            CaseCreate(
                title=f"{brand} {model} ({error_code})" if error_code else f"{brand} {model}",
                description=symptom or "",
                brand=brand,
                model=model,
                series=series or None,
                error_code=None if error_code == "None provided" else error_code,
                symptom=symptom,
                checks_done=checks_done,
                diagnosis=diagnosis_text,
                status="open",      # por ahora lo dejamos abierto
                source="ai",
                created_by_uid=uid,
            
            )
        )

        return {
            "case_id": case.id,
            "diagnosis": diagnosis_text,
            "source": "ai",
        }


    except Exception as e:
        # no tires el error completo al cliente en producción, pero por ahora sirve
        raise HTTPException(status_code=500, detail=f"OpenAI error: {e}")
