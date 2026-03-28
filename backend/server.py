"""
server.py
FastAPI 서버: 이미지 업로드 → SVD 프레임 생성 → 스프라이트 시트 출력
"""
import asyncio
import io
import json
import os
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

load_dotenv()

# ─────────────────────────────────────────────────────────────
# 앱 & 설정
# ─────────────────────────────────────────────────────────────
app = FastAPI(title="Animation Generator API", version="1.0.0")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 완료된 결과물을 정적 파일로 서빙
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# 동시에 1개 작업만 처리 (GPU 메모리 보호)
executor = ThreadPoolExecutor(max_workers=1)


# ─────────────────────────────────────────────────────────────
# 모델 (전역 싱글턴)
# ─────────────────────────────────────────────────────────────
_generator = None


def get_generator():
    global _generator
    if _generator is None:
        from models.frame_generator import FrameGenerator
        _generator = FrameGenerator()
    return _generator


# ─────────────────────────────────────────────────────────────
# 작업 상태 관리
# ─────────────────────────────────────────────────────────────
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class Job(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    message: str = "대기 중..."
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = ""


jobs: dict[str, Job] = {}


# ─────────────────────────────────────────────────────────────
# 요청/응답 스키마
# ─────────────────────────────────────────────────────────────
class GenerateResponse(BaseModel):
    job_id: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    result: Optional[dict] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# 생성 핵심 로직 (동기 함수, ThreadPoolExecutor에서 실행)
# ─────────────────────────────────────────────────────────────
def run_generation_sync(
    job_id: str,
    image_bytes: bytes,
    num_frames: int,
    motion_strength: int,
    fps: int,
    use_rembg: bool,
):
    """실제 모델 추론 + 파일 저장 (동기)"""
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def progress_cb(p: int, msg: str):
        if job_id in jobs:
            jobs[job_id].progress = p
            jobs[job_id].message = msg
            print(f"[{job_id}] {p}% - {msg}")

    try:
        jobs[job_id].status = JobStatus.RUNNING
        progress_cb(5, "이미지 로딩 중...")

        # 이미지 로드
        image = Image.open(io.BytesIO(image_bytes))

        # 배경 제거 (선택)
        if use_rembg:
            progress_cb(10, "배경 제거 중 (rembg)...")
            from models.preprocessor import remove_background
            image = remove_background(image)
        else:
            image = image.convert("RGBA")

        # 프레임 생성
        generator = get_generator()
        frames = generator.generate(
            image=image,
            num_frames=num_frames,
            motion_bucket_id=motion_strength,
            fps=fps,
            seed=42,
            use_luminance_alpha=True,
            progress_cb=progress_cb,
        )

        # 스프라이트 시트 생성
        progress_cb(95, "스프라이트 시트 조립 중...")
        from models.sprite_sheet_builder import build_sprite_sheet, create_preview_gif

        sheet, metadata = build_sprite_sheet(frames, cols=4, frame_size=512)
        metadata["fps"] = fps
        metadata["motion_strength"] = motion_strength
        metadata["use_rembg"] = use_rembg

        # 파일 저장
        sheet_path = job_dir / "sprite_sheet.png"
        meta_path = job_dir / "metadata.json"
        gif_path = job_dir / "preview.gif"

        sheet.save(str(sheet_path), "PNG", optimize=False)
        meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        gif_bytes = create_preview_gif(frames, fps=fps, frame_size=256)
        gif_path.write_bytes(gif_bytes)

        progress_cb(100, "완료!")

        jobs[job_id].status = JobStatus.DONE
        jobs[job_id].result = {
            "sprite_sheet_url": f"/outputs/{job_id}/sprite_sheet.png",
            "metadata_url": f"/outputs/{job_id}/metadata.json",
            "preview_gif_url": f"/outputs/{job_id}/preview.gif",
            "num_frames": num_frames,
            "sheet_size": f"{sheet.width}×{sheet.height}",
        }

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[{job_id}] 오류 발생:\n{error_detail}")
        jobs[job_id].status = JobStatus.ERROR
        jobs[job_id].error = str(e)
        jobs[job_id].message = f"오류: {str(e)}"


# ─────────────────────────────────────────────────────────────
# API 엔드포인트
# ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    """서버 상태 및 GPU 정보 확인"""
    import torch
    gpu_info = {}
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        gpu_info = {
            "name": props.name,
            "vram_gb": round(props.total_memory / (1024 ** 3), 1),
            "cuda_version": torch.version.cuda,
        }
    return {
        "status": "ok",
        "gpu": gpu_info or "CPU only",
        "model": os.getenv("SVD_MODEL", "stabilityai/stable-video-diffusion-img2vid-xt"),
    }


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(
    image: UploadFile = File(..., description="폭발 이펙트 PNG 이미지"),
    num_frames: int = Form(8, ge=4, le=16, description="출력 프레임 수 (4~16)"),
    motion_strength: int = Form(127, ge=1, le=255, description="모션 강도 (1~255)"),
    fps: int = Form(12, ge=6, le=30, description="초당 프레임 수"),
    use_rembg: bool = Form(True, description="AI 배경 제거 사용 여부"),
):
    # 이미지 유효성 검사
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")

    image_bytes = await image.read()
    if len(image_bytes) > 20 * 1024 * 1024:  # 20MB 제한
        raise HTTPException(status_code=400, detail="파일 크기는 20MB 이하이어야 합니다")

    # 이미지 유효성 확인
    try:
        img = Image.open(io.BytesIO(image_bytes))
        from models.preprocessor import validate_input_image
        is_valid, err_msg = validate_input_image(img)
        if not is_valid:
            raise HTTPException(status_code=400, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"이미지 파일이 손상되었습니다: {e}")

    # 작업 생성
    job_id = str(uuid.uuid4())
    jobs[job_id] = Job(
        job_id=job_id,
        created_at=datetime.utcnow().isoformat(),
    )

    # 백그라운드 실행
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor,
        run_generation_sync,
        job_id,
        image_bytes,
        num_frames,
        motion_strength,
        fps,
        use_rembg,
    )

    return GenerateResponse(job_id=job_id, message="생성 시작됨")


@app.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    job = jobs[job_id]
    return StatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        message=job.message,
        result=job.result,
        error=job.error,
    )


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """작업 기록 및 생성 파일 삭제"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    job_dir = OUTPUT_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)

    del jobs[job_id]
    return {"message": f"작업 {job_id} 삭제 완료"}


@app.get("/api/jobs")
async def list_jobs():
    """모든 작업 목록 조회"""
    return [
        {
            "job_id": j.job_id,
            "status": j.status.value,
            "progress": j.progress,
            "created_at": j.created_at,
        }
        for j in jobs.values()
    ]


@app.get("/")
async def root():
    return {"message": "Animation Generator API", "docs": "/docs"}
