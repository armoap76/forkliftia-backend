from fastapi import FastAPI

app = FastAPI(title="ForkliftIA Backend")

@app.get("/ping")
def ping():
    return {"message": "forkliftia ok"}
