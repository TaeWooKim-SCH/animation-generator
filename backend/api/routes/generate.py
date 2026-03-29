"""
api/routes/generate.py

이미지 업로드 → 애니메이션 생성 시작 엔드포인트.

  POST /api/generate
    — 이미지 파일 유효성 검사
    — Job 생성
    — 백그라운드 스레드에서 generation_service.run_generation_sync 실행
    — job_id 즉시 반환
"""

from __future__ import annotations

import asyncio
import io
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from api.schemas import GenerateResponse
from services.generation_service import run_generation_sync
from services.job_service import job_store

router = APIRouter(prefix="/api", tags=["generate"])

# GPU 메모리 보호: 동시에 1개 작업만 처리
_executor = ThreadPoolExecutor(max_workers=1)


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    image: UploadFile = File(..., description="폭발 이펙트 PNG 이미지"),
    num_frames: int = Form(8, ge=4, le=16, description="출력 프레임 수 (4~16)"),
    motion_strength: int = Form(127, ge=1, le=255, description="모션 강도 (1~255)"),
    fps: int = Form(12, ge=6, le=30, description="초당 프레임 수"),
    use_rembg: bool = Form(True, description="AI 배경 제거 사용 여부"),
) -> GenerateResponse:
    """이미지를 업로드하여 애니메이션 생성 작업을 시작합니다."""

    # ── 이미지 유효성 검사 ───────────────────────────────────
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")

    image_bytes = await image.read()
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="파일 크기는 20MB 이하이어야 합니다")

    try:
        img = Image.open(io.BytesIO(image_bytes))
        from models.preprocessor import validate_input_image
        is_valid, err_msg = validate_input_image(img)
        if not is_valid:
            raise HTTPException(status_code=400, detail=err_msg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"이미지 파일이 손상되었습니다: {e}")

    # ── Job 생성 및 백그라운드 실행 ──────────────────────────
    job_id = str(uuid.uuid4())
    job_store.create(job_id)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        run_generation_sync,
        job_id,
        image_bytes,
        num_frames,
        motion_strength,
        fps,
        use_rembg,
    )

    return GenerateResponse(job_id=job_id, message="생성 시작됨")
