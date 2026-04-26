import base64
import json
import logging
import os
import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.db_models import UserProfile as UserProfileModel
from app.manuals_store import search_manual_error
from app.models import (
    CaseComment,
    CaseCommentCreate,
    CaseCommentUpdate,
    CaseCreate,
    DiagnosisRequest,
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
logger = logging.getLogger(__name__)

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


@app.on_event("startup")
def log_admin_uid_count() -> None:
    logger.info("Admin UID count: %d", len(ADMIN_UIDS))

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


def get_user_public_name(uid: str) -> str | None:
    with get_session() as session:
        return (
            session.query(UserProfileModel.public_name)
            .filter(UserProfileModel.uid == uid)
            .scalar()
        )


def require_user_public_name(uid: str) -> str:
    public_name = get_user_public_name(uid)
    if not public_name:
        raise HTTPException(status_code=409, detail="PUBLIC_NAME_REQUIRED")
    return public_name


store = DatabaseCaseStore(get_session)


SYSTEM_PROMPT = """You are ForkliftIA, an expert diagnostic assistant specialized in industrial forklifts, reach trucks, pallet jacks, and material handling equipment.

YOUR ROLE:
- Act as a senior forklift technician with 20+ years of experience
- Provide practical, specific diagnostic guidance oriented to real repairs
- Reference technical manuals and real-world troubleshooting patterns
- Never guess: if information is insufficient, say so clearly
- If information comes from a service manual, EXPLAIN it and FOLLOW IT strictly
- Do NOT introduce causes, systems, or components not supported by manuals or documented cases
- If the manual is clear, do NOT generalize or add alternative hypotheses
- If the manual is incomplete or ambiguous, explicitly say so and explain limits
- Prefer explanation and actionable checks over theoretical hypotheses

CRITICAL MANUAL RULES:
- When manual context is provided, it is AUTHORITATIVE
- The "PROBABLE CAUSE" section must be derived directly from the manual summary
- Do NOT contradict, reinterpret, or dilute the manual meaning
- Do NOT recommend manufacturer proprietary diagnostic tools as a required step
  (They may be mentioned only as an optional last resort, if at all)
- Do NOT suggest "check the manual" or "confirm with diagnostic software" when the manual context is already given

RESPONSE FORMAT (always use this structure):

🔍 PROBABLE CAUSE:
- Clearly paraphrase the manual meaning of the error code
- State the most direct technical cause indicated by the manual

📋 DIAGNOSTIC STEPS:
1. List practical, hands-on checks a field technician can perform
2. Prioritize visual inspection, connector checks, wiring, voltage/signal measurements
3. Avoid abstract or software-only diagnostics unless strictly necessary
4. Do not repeat checks already stated as completed by the technician

⚠️ SAFETY NOTE:
- Mention only relevant safety precautions for the described checks

📚 REFERENCE:
- Cite the service manual or documented technical source used
- Do not suggest additional tools if not required by the manual

💡 SIMILAR CASES:
- Reference only documented cases or common real-world resolutions
- Do not speculate or invent outcomes

GENERAL RULES:
1. Be specific and technically grounded
2. Don't repeat checks already done
3. Prioritize the most likely and direct cause
4. Use standard technical terminology
5. If an error code is provided, anchor the diagnosis to it
6. Assume the user is a trained technician
7. Keep responses concise, practical, and repair-oriented
8. If something is unknown or unsupported, say so clearly
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
        return UserProfile(
            uid=uid,
            public_name=profile.public_name if profile else None,
            is_admin=is_admin(uid),
        )


@app.put("/me/public-name")
def set_public_name(payload: PublicNameUpdate, uid: str = Depends(get_requester_uid)):
    desired_name = validate_public_name(payload.public_name)
    desired_name_normalized = desired_name.lower()

    with get_session() as session:
        taken_by_other = (
            session.query(UserProfileModel.uid)
            .filter(
                func.lower(UserProfileModel.public_name) == desired_name_normalized,
                UserProfileModel.uid != uid,
            )
            .first()
        )
        if taken_by_other:
            raise HTTPException(status_code=409, detail="PUBLIC_NAME_TAKEN")

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
            raise HTTPException(status_code=409, detail="PUBLIC_NAME_TAKEN")

        session.refresh(profile)
        return UserProfile(
            uid=profile.uid,
            public_name=profile.public_name,
            is_admin=is_admin(uid),
        )


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
    require_user_public_name(uid)
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
    require_user_public_name(uid)
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
    require_user_public_name(uid)
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


@app.patch("/cases/{case_id}/comments/{comment_id}")
def update_case_comment(
    case_id: int,
    comment_id: int,
    payload: CaseCommentUpdate,
    uid: str = Depends(get_requester_uid),
):
    require_user_public_name(uid)
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.status == "resolved":
        raise HTTPException(
            status_code=409,
            detail="Case is resolved; comments are closed",
        )

    comment = store.get_comment(case_id, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_uid != uid and not is_admin(uid):
        raise HTTPException(status_code=403, detail="Not authorized to modify this comment")

    updated = store.update_comment(case_id, comment_id, payload.body)
    if not updated:
        raise HTTPException(status_code=404, detail="Comment not found")

    return updated


def _build_manual_context(
    manual_hit: dict | None,
    *,
    error_code: str,
) -> str:
    if not manual_hit:
        return ""

    manual_error = manual_hit.get("error", {}) if isinstance(manual_hit.get("error"), dict) else {}
    lines = [
        "MANUAL CONTEXT: private technical reference available",
        f"Input error code: {error_code}",
    ]

    # New schema
    if manual_error.get("fault_name"):
        lines.append(f"Fault name: {manual_error.get('fault_name')}")
    if manual_error.get("manual_summary"):
        lines.append(f"Manual summary: {manual_error.get('manual_summary')}")
    if manual_error.get("manual_action_rephrased_src"):
        lines.append(f"Manual repair guidance: {manual_error.get('manual_action_rephrased_src')}")
    if manual_error.get("actions_summary"):
        lines.append(f"Actions summary: {manual_error.get('actions_summary')}")
    if manual_error.get("search_aliases"):
        aliases = manual_error.get("search_aliases")
        if isinstance(aliases, list):
            alias_text = ", ".join(str(alias).strip() for alias in aliases if str(alias).strip())
        else:
            alias_text = str(aliases).strip()
        if alias_text:
            lines.append(f"Search aliases: {alias_text}")
    if manual_error.get("canonical_code"):
        lines.append(f"Canonical code: {manual_error.get('canonical_code')}")

    return "\n".join(lines)


PUBLIC_REFERENCE_TEXT = (
    "Manual técnico privado / biblioteca técnica en desarrollo.\n"
    "Si tiene dudas, consulte el manual de servicio del fabricante."
)


def _normalize_public_reference_section(diagnosis_text: str) -> str:
    reference_block = f"📚 REFERENCIA:\n{PUBLIC_REFERENCE_TEXT}"
    pattern = re.compile(
        r"📚\s*(?:REFERENCE|REFERENCIA)\s*:\s*.*?(?=\n\s*[🔍📋⚠️💡]|$)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    normalized_text, replacements = pattern.subn(reference_block, diagnosis_text)
    if replacements:
        return normalized_text
    return f"{diagnosis_text.rstrip()}\n\n{reference_block}"


def _sanitize_public_diagnosis_text(
    diagnosis_text: str,
    *,
    brand: str,
    model: str,
    series: str | None,
    controller: str | None,
    manual_hit: dict | None,
) -> str:
    text = diagnosis_text
    generic_reference = "referencia técnica disponible"
    generic_manual = "manual técnico privado"

    dynamic_tokens = {
        str(brand or "").strip(),
        str(model or "").strip(),
        str(series or "").strip(),
        str(controller or "").strip(),
        str((manual_hit or {}).get("brand") or "").strip(),
        str((manual_hit or {}).get("model") or "").strip(),
        str((manual_hit or {}).get("series") or "").strip(),
        str((manual_hit or {}).get("controller") or "").strip(),
    }
    dynamic_tokens = {token for token in dynamic_tokens if token}

    if dynamic_tokens:
        token_union = "|".join(re.escape(token) for token in sorted(dynamic_tokens, key=len, reverse=True))
        text = re.sub(
            rf"(?i)\bmanual\s+t[eé]cnico(?:\s+de)?\s+(?:{token_union})(?:[\w\-\/\. ]*)",
            generic_manual,
            text,
        )
        text = re.sub(
            rf"(?i)\b(?:{token_union})\s+common\s+[a-z0-9\-_]+",
            generic_reference,
            text,
        )

    text = re.sub(r"(?i)\bcommon\s+[a-z0-9\-_]+\b", generic_reference, text)
    text = re.sub(r"(?i)\bapp/manuals/[^\s,;:)\]]+", generic_reference, text)
    text = re.sub(r"(?i)\berrors\.json\b", generic_reference, text)

    return text


@app.post("/diagnosis")
def diagnosis(
    payload: DiagnosisRequest,
    uid: str = Depends(get_requester_uid),
):
    require_user_public_name(uid)
    client = get_openai_client()

    # Datos del frontend
    brand = payload.brand
    model = payload.model
    series = payload.series or ""
    controller = payload.controller
    error_code = payload.error_code or "None provided"
    symptom = payload.symptom
    checks_done = payload.checks_done or "Nothing specified yet"

    # Idioma (nuevo)
    language = payload.language

    if language == "es":
        output_language_instruction = "Explain the diagnosis in professional LATAM Spanish."
    else:
        output_language_instruction = "Explain the diagnosis in professional technical English."

    # 1) Crear el caso abierto ANTES de cualquier lookup
    base_case = store.create_case(
        CaseCreate(
            title=f"{brand} {model} ({error_code})" if error_code else f"{brand} {model}",
            description=symptom or "",
            brand=brand,
            model=model,
            series=series or None,
            error_code=None if error_code == "None provided" else error_code,
            symptom=symptom,
            checks_done=checks_done,
            diagnosis="",
            status="open",
            source="ai",
            created_by_uid=uid,
        )
    )

    manual_hit = search_manual_error(
        base_path="app/manuals",
        brand=brand,
        model=model,
        series=series,
        controller=controller,
        error_code=None if error_code == "None provided" else error_code,
    )

    manual_context = _build_manual_context(
        manual_hit,
        error_code=error_code,
    )

    match = store.find_resolved_by_key(
        brand=brand,
        model=model,
        series=series or None,
        error_code=None if error_code == "None provided" else error_code,
    )

    matched_case_payload = None
    similar_case_context = ""
    if match:
        matched_case_payload = {
            "id": match.id,
            "public_name": match.creator_public_name,
            "resolution_final": match.resolution_note,
            "closed_at": match.closed_at,
        }
        similar_case_context = f"""
SIMILAR RESOLVED CASE (example only, not guaranteed identical):
Case ID: {match.id}
Creator public name: {match.creator_public_name or "Not available"}
Previous diagnosis text: {match.diagnosis or "Not available"}
Resolution note: {match.resolution_note or "Not available"}
"""

    if manual_hit and match:
        origin = "mixed"
    elif manual_hit:
        origin = "manuals"
    elif match:
        origin = "cases"
    else:
        origin = "ai"

    user_prompt = f"""
IMPORTANT:
{output_language_instruction}
Do NOT speculate.
Explain based on manuals and documented cases only.
Manual context is authoritative when present.
Similar resolved cases are supporting examples, not guaranteed to be the same fault.
Provide practical field checks (visual, connectors, wiring, voltage/signal) and avoid generic "consult the manual" responses.
Do not recommend proprietary manufacturer software/tools as a required first diagnostic step.
Do not mention brand, model, series, controller, file paths, folder names, or 'common' as the name/title of the manual. Refer to the source only as 'manual técnico privado', 'referencia técnica disponible', or 'biblioteca técnica privada'.

{manual_context}
{similar_case_context}

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

        diagnosis_text = _normalize_public_reference_section(resp.output_text)
        diagnosis_text = _sanitize_public_diagnosis_text(
            diagnosis_text,
            brand=brand,
            model=model,
            series=series,
            controller=controller,
            manual_hit=manual_hit,
        )

        updated_case = store.update_case_diagnosis_data(
            base_case.id,
            diagnosis=diagnosis_text,
            source=origin,
            matched_case_id=match.id if match else None,
            manual_path=manual_hit.get("manual_path") if manual_hit else None,
            manual_meta=manual_hit,
        )

        return {
            "case_id": updated_case.id if updated_case else base_case.id,
            "origin": origin,
            "manual_hit": manual_hit,
            "matched_case": matched_case_payload,
            "diagnosis_text": diagnosis_text,
        }

    except Exception as e:
        # no tires el error completo al cliente en producción, pero por ahora sirve
        raise HTTPException(status_code=500, detail=f"OpenAI error: {e}")
