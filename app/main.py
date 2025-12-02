from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI(title="ForkliftIA Backend")

client = OpenAI()

class AskRequest(BaseModel):
    question: str

@app.post("/ask")
def ask_ai(payload: AskRequest):
    try:
        completion = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": payload.question}]
        )
        return {"answer": completion.choices[0].message["content"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ping")
def ping():
    return {"message": "forkliftia ok"}

