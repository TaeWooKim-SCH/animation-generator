"""
api/routes/health.py

서버 상태 확인 엔드포인트.

  GET /api/health
    — 현재 디바이스 정보 (CUDA / MPS / CPU) 반환
    — 사용 가능한 백엔드 목록 반환
    — 모델 로드 여부 반환
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from models.devices import BackendFactory
from services.generation_service import get_generator

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """서버 상태 및 디바이스 정보를 반환합니다 (CUDA / MPS / CPU 공통)."""
    available_backends = BackendFactory.list_available()
    active_device = os.getenv("DEVICE") or (available_backends[0] if available_backends else "cpu")

    try:
        backend = BackendFactory.create(active_device)
        info = backend.get_info()
        device_info = {
            "type": info.device_type,
            "name": info.device_name,
            "memory_gb": info.memory_gb,
            "platform": info.platform_os,
            **info.extra,
        }
    except Exception as e:
        device_info = {"error": str(e)}

    # 싱글턴이 이미 초기화되었는지 확인 (import 없이)
    from services import generation_service
    model_loaded = (
        generation_service._generator is not None
        and generation_service._generator.is_loaded
    )

    return {
        "status": "ok",
        "device": device_info,
        "available_backends": available_backends,
        "model": os.getenv("SVD_MODEL", "stabilityai/stable-video-diffusion-img2vid-xt"),
        "model_loaded": model_loaded,
    }
