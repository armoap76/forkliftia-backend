import os
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from openai import OpenAI

app = FastAPI(title="ForkliftIA Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://forkliftia-frontend.pages.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# OpenAI client (lee OPENAI_API_KEY del environment)
client = OpenAI()

SYSTEM_PROMPT = """You are ForkliftIA, an expert diagnostic assistant specialized in industrial forklifts, reach trucks, pallet jacks, and material handling equipment.

YOUR ROLE:
- Act as a senior forklift technician with 20+ years of experience
- Provide practical, specific diagnostic guidance
- Reference technical manuals and real-world troubleshooting patterns
- Never guess - if information is insufficient, ask for clarification

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

@app.post("/diagnosis")
def diagnosis(
    payload: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    # Armado del prompt con tus campos actuales del frontend
    brand = payload.get("brand", "")
    model = payload.get("model", "")
    series = payload.get("series", "")
    error_code = payload.get("error_code") or "None provided"
    symptom = payload.get("symptom", "")
    checks_done = payload.get("checks_done") or "Nothing specified yet"

    user_prompt = f"""NEW DIAGNOSTIC CASE:

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

        case_id = f"CASE-{int(datetime.utcnow().timestamp() * 1000)}"

        return {
            "case_id": case_id,
            "diagnosis": diagnosis_text,
            "source": "ai",
        }

    except Exception as e:
        # no tires el error completo al cliente en producción, pero por ahora sirve
        raise HTTPException(status_code=500, detail=f"OpenAI error: {e}")
