from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI(title="ForkliftIA Backend")

client = OpenAI()  # usa OPENAI_API_KEY del entorno

class DiagnosisRequest(BaseModel):
    brand: str
    model: str
    series: str | None = None
    error_code: str | None = None
    symptom: str
    checks_done: str | None = None

class AskRequest(BaseModel):
    question: str

class Case(BaseModel):
    id: int
    brand: str
    model: str
    series: str | None = None
    error_code: str | None = None
    symptom: str
    checks_done: str | None = None
    diagnosis: str


CASES: list[Case] = []

BASE_PROMPT = """
You are ForkliftIA, an expert diagnostic assistant specialized in industrial forklifts, reach trucks, pallet jacks, and material handling equipment.

YOUR ROLE:
- Act as a senior forklift technician with 20+ years of experience.
- Provide practical, specific diagnostic guidance.
- Reference technical manuals and real-world troubleshooting patterns.
- Never guess. If information is insufficient, ask for clarification.

RESPONSE FORMAT (ALWAYS use this structure):

🔍 PROBABLE CAUSE:
[1-2 sentences identifying the most likely root cause based on symptoms]

📋 DIAGNOSTIC STEPS:
1. [First specific action to take]
2. [Second specific action]
3. [Third specific action]
4. [Additional steps if needed – max 5]

⚠️ SAFETY NOTE:
[One brief safety reminder relevant to this repair]

📚 REFERENCE:
[Mention manual section, component codes, or specifications if known]

💡 SIMILAR CASES:
[If applicable, mention common patterns or known failure modes]

Your responses must follow this structure every single time.
"""

@app.post("/diagnosis")
def diagnosis(payload: DiagnosisRequest):
    try:
        tech_prompt = f"""
{BASE_PROMPT}

Diagnose the following forklift case and answer STRICTLY in the required structured format:

Brand: {payload.brand}
Model: {payload.model}
Series: {payload.series}
Error Code: {payload.error_code}
Symptom: {payload.symptom}
Checks Already Done: {payload.checks_done}
"""
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=tech_prompt,
        )

        answer = resp.output[0].content[0].text

        # Guardar como "case" en memoria
        case_id = len(CASES) + 1
        case = Case(
            id=case_id,
            brand=payload.brand,
            model=payload.model,
            series=payload.series,
            error_code=payload.error_code,
            symptom=payload.symptom,
            checks_done=payload.checks_done,
            diagnosis=answer,
        )
        CASES.append(case)

        return {
            "case_id": case_id,
            "diagnosis": answer
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cases/{case_id}")
def get_case(case_id: int):
    for case in CASES:
        if case.id == case_id:
            return case
    raise HTTPException(status_code=404, detail="Case not found")

@app.get("/cases")
def list_cases():
    return CASES


@app.post("/ask")
def ask_ai(payload: AskRequest):
    try:
        prompt = f"{BASE_PROMPT}\n\nPregunta del técnico:\n{payload.question}"
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
        )
        answer = resp.output[0].content[0].text
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ping")
def ping():
    return {"message": "forkliftia ok"}



