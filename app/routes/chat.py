from fastapi import APIRouter
from app.schemas.chat_schema import ChatRequest
from app.services.openai_service import generate_reply

router = APIRouter()

@router.post('/chat')
def chat(req: ChatRequest):
    return generate_reply(req.message, req.history)
