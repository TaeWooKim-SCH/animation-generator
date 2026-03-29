"""
api/app.py

FastAPI 애플리케이션 인스턴스.

책임:
  - FastAPI 앱 생성 및 메타데이터 설정
  - CORS 미들웨어 등록
  - 정적 파일 마운트 (/outputs)
  - 라우터 등록
  - 루트 엔드포인트

이 모듈은 애플리케이션 설정만을 담당합니다.
비즈니스 로직은 services/, HTTP 스키마는 api/routes/에 있습니다.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from api.routes import health, generate, jobs

# ─────────────────────────────────────────────────────────────
# 출력 디렉토리 준비
# ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# FastAPI 앱
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Animation Generator API",
    description=(
        "2D 이펙트 이미지 한 장으로 Unity 스프라이트 시트를 자동 생성합니다.\n\n"
        "지원 플랫폼: Ubuntu + NVIDIA GPU (CUDA) / macOS Apple Silicon (MPS) / CPU"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────────────────────────────────────────
# 미들웨어
# ─────────────────────────────────────────────────────────────
_cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# 정적 파일
# ─────────────────────────────────────────────────────────────
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# ─────────────────────────────────────────────────────────────
# 라우터 등록
# ─────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(generate.router)
app.include_router(jobs.router)


# ─────────────────────────────────────────────────────────────
# 루트
# ─────────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "message": "Animation Generator API v2.0",
        "docs": "/docs",
        "health": "/api/health",
    }
