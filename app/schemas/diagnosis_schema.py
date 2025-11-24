from pydantic import BaseModel

class DiagnosisRequest(BaseModel):
    message: str
