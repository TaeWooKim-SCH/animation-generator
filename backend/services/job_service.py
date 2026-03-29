"""
job_service.py

In-memory Job 저장소 및 상태 관리.

책임:
  - Job 생명주기 (생성 → 실행 → 완료/오류 → 삭제)
  - 진행 상태 업데이트
  - Job 목록 조회

설계:
  JobStatus  — 상태 열거형 (Enum)
  Job        — 단일 Job 데이터 모델 (Pydantic BaseModel)
  JobStore   — Job 저장소 (오직 이 클래스를 통해서만 jobs에 접근)
  job_store  — 전역 싱글턴 인스턴스
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class Job(BaseModel):
    """단일 생성 작업의 상태를 표현합니다."""

    job_id: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    message: str = "대기 중..."
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = ""


class JobStore:
    """
    In-memory Job 저장소.

    스레드 안전성: FastAPI의 ThreadPoolExecutor에서 progress_cb를 통해
    백그라운드 스레드가 job 상태를 업데이트합니다.
    현재는 GIL 덕분에 단순 dict 접근이 안전하며,
    다중 작업자로 확장 시 threading.Lock 추가를 권장합니다.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    # ── 생성 ───────────────────────────────────────────────────
    def create(self, job_id: str) -> Job:
        """신규 Job을 PENDING 상태로 생성하고 반환합니다."""
        job = Job(
            job_id=job_id,
            created_at=datetime.utcnow().isoformat(),
        )
        self._jobs[job_id] = job
        return job

    # ── 조회 ───────────────────────────────────────────────────
    def get(self, job_id: str) -> Optional[Job]:
        """Job을 반환합니다. 없으면 None을 반환합니다."""
        return self._jobs.get(job_id)

    def get_or_raise(self, job_id: str) -> Job:
        """Job을 반환합니다. 없으면 KeyError를 발생시킵니다."""
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"작업을 찾을 수 없습니다: {job_id}")
        return job

    def list_all(self) -> list[Job]:
        """모든 Job 목록을 반환합니다."""
        return list(self._jobs.values())

    # ── 상태 전이 ──────────────────────────────────────────────
    def update_progress(self, job_id: str, progress: int, message: str) -> None:
        """진행률과 메시지를 업데이트합니다."""
        if job_id in self._jobs:
            self._jobs[job_id].progress = progress
            self._jobs[job_id].message = message

    def set_running(self, job_id: str) -> None:
        """Job을 RUNNING 상태로 전이합니다."""
        if job_id in self._jobs:
            self._jobs[job_id].status = JobStatus.RUNNING

    def set_done(self, job_id: str, result: dict) -> None:
        """Job을 DONE 상태로 전이하고 결과를 저장합니다."""
        if job_id in self._jobs:
            self._jobs[job_id].status = JobStatus.DONE
            self._jobs[job_id].result = result
            self._jobs[job_id].progress = 100

    def set_error(self, job_id: str, error: str, message: str) -> None:
        """Job을 ERROR 상태로 전이하고 오류 정보를 저장합니다."""
        if job_id in self._jobs:
            self._jobs[job_id].status = JobStatus.ERROR
            self._jobs[job_id].error = error
            self._jobs[job_id].message = message

    # ── 삭제 ───────────────────────────────────────────────────
    def delete(self, job_id: str) -> None:
        """Job을 저장소에서 제거합니다."""
        self._jobs.pop(job_id, None)

    # ── 유틸 ───────────────────────────────────────────────────
    def __contains__(self, job_id: str) -> bool:
        return job_id in self._jobs

    def __len__(self) -> int:
        return len(self._jobs)


# 전역 싱글턴 — 애플리케이션 전체에서 공유
job_store = JobStore()
