"""
api/schemas.py

HTTP 계층의 Pydantic 요청/응답 스키마.
내부 서비스 모델(Job)과 분리하여 API 계약을 명확히 합니다.
"""

from typing import Optional
from pydantic import BaseModel


class GenerateResponse(BaseModel):
    """POST /api/generate 응답 스키마."""
    job_id: str
    message: str


class StatusResponse(BaseModel):
    """GET /api/status/{job_id} 응답 스키마."""
    job_id: str
    status: str
    progress: int
    message: str
    result: Optional[dict] = None
    error: Optional[str] = None
