"""
api/routes/jobs.py

Job 상태 조회 및 삭제 엔드포인트.

  GET    /api/status/{job_id}  — 단일 Job 상태 조회
  DELETE /api/jobs/{job_id}    — Job 기록 및 생성 파일 삭제
  GET    /api/jobs             — 전체 Job 목록 조회
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.schemas import StatusResponse
from services.job_service import job_store

router = APIRouter(prefix="/api", tags=["jobs"])

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str) -> StatusResponse:
    """Job 진행 상태를 조회합니다."""
    try:
        job = job_store.get_or_raise(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    return StatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        message=job.message,
        result=job.result,
        error=job.error,
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> dict:
    """Job 기록 및 생성된 파일을 삭제합니다."""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    job_dir = OUTPUT_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)

    job_store.delete(job_id)
    return {"message": f"작업 {job_id} 삭제 완료"}


@router.get("/jobs")
async def list_jobs() -> list[dict]:
    """전체 Job 목록을 반환합니다."""
    return [
        {
            "job_id": j.job_id,
            "status": j.status.value,
            "progress": j.progress,
            "created_at": j.created_at,
        }
        for j in job_store.list_all()
    ]
