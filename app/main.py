from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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

@app.get("/ping")
def ping():
    return {"message": "forkliftia ok"}

@app.post("/diagnosis")
def diagnosis(
    payload: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    # por ahora no validamos el token, solo comprobamos que llega
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    return {
        "status": "ok",
        "received": payload,
    }
