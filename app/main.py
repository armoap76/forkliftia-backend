from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ForkliftIA Backend")

# CORS: OBLIGATORIO para frontend web
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://forkliftia-frontend.pages.dev",  # tu Pages real
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # permite Authorization
)

@app.get("/ping")
def ping():
    return {"message": "forkliftia ok"}
