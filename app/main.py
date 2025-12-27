import os
from datetime import datetime


from app.manuals_store import search_manual_error
from app.models import CaseCreate
from app.storage_db import DatabaseCaseStore
from app.database import get_session

from pydantic import BaseModel

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from openai import OpenAI


class ResolveCaseIn(BaseModel):
    resolution_note: str


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

def get_requester_uid(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <uid>")
    return credentials.credentials.strip()

def is_admin(uid: str) -> bool:
    return uid in ADMIN_UIDS

def ensure_case_owner_or_admin(case, uid: str) -> None:
    # case debe tener created_by_uid
    if getattr(case, "created_by_uid", None) == uid or is_admin(uid):
        return
    raise HTTPException(status_code=403, detail="Not authorized to modify this case")

def get_openai_client() -> OpenAI:
    return OpenAI()

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

@app.get("/cases")
def list_cases(
    status: str | None = None,
    limit: int = 50,
):
    return store.list_cases(status=status, limit=limit)

@app.patch("/cases/{case_id}")
def set_case_status(
    case_id: int,
    payload: dict,
    uid: str = Depends(get_requester_uid),
):
    status = payload.get("status")
    if status not in ("open", "resolved"):
        raise HTTPException(status_code=400, detail="status must be 'open' or 'resolved'")

    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    ensure_case_owner_or_admin(case, uid)

    updated = store.update_status(case_id, status)
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

    ensure_case_owner_or_admin(case, uid)

    resolution_note = (payload.resolution_note or "").strip()
    if not resolution_note:
        raise HTTPException(status_code=400, detail="resolution_note is required")

    updated = store.resolve_case(case_id, resolution_note)
    if not updated:
        raise HTTPException(status_code=404, detail="case not found")

    return updated

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
                created_by_uid=token,
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
