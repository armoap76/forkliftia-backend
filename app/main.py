from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI(title="ForkliftIA Backend")

client = OpenAI()  # usa OPENAI_API_KEY del entorno

class AskRequest(BaseModel):
    question: str

@app.post("/ask")
def ask_ai(payload: AskRequest):
    try:
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=payload.question,
        )
        answer = resp.output[0].content[0].text
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ping")
def ping():
    return {"message": "forkliftia ok"}


