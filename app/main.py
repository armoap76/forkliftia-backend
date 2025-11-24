from fastapi import FastAPI
from app.routes import health, chat, diagnosis

app = FastAPI(title='ForkliftIA Backend')

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(diagnosis.router)
