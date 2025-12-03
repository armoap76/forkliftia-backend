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
        # Construcción del prompt estructurado
        tech_prompt = f"""
{BASE_PROMPT}

Diagnose the following forklift case and answer **STRICTLY in the required structured format**:

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
        return {"diagnosis": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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



