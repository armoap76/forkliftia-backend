from fastapi import APIRouter
from app.schemas.diagnosis_schema import DiagnosisRequest
from app.services.openai_service import generate_diagnosis

router = APIRouter()

@router.post('/diagnosis')
def diagnosis(req: DiagnosisRequest):
    return generate_diagnosis(req)
