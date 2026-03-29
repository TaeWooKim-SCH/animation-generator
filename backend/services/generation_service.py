"""
generation_service.py

프레임 생성 비즈니스 로직.

책임:
  - FrameGenerator 싱글턴 관리 (get_generator)
  - 이미지 → 스프라이트 시트 전체 파이프라인 실행 (run_generation_sync)
  - 파일 저장 및 메타데이터 기록

이 모듈은 HTTP 계층(api/)과 완전히 분리되어 있어
REST API, WebSocket, CLI 등 어디서든 재사용할 수 있습니다.
"""

from __future__ import annotations

import io
import json
import os
import traceback
from pathlib import Path
from typing import Optional

from PIL import Image

from services.job_service import job_store

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# FrameGenerator 싱글턴
# ─────────────────────────────────────────────────────────────
_generator = None


def get_generator():
    """
    전역 FrameGenerator 싱글턴을 반환합니다.

    DEVICE 환경변수로 백엔드를 강제 지정할 수 있습니다.
      DEVICE=cuda  — NVIDIA GPU (Ubuntu 서버)
      DEVICE=mps   — Apple Silicon (Mac Mini M-series)
      DEVICE=cpu   — CPU 전용 (Fallback)
      (미설정)     — 자동 감지: CUDA → MPS → CPU 우선순위
    """
    global _generator
    if _generator is None:
        from models.frame_generator import FrameGenerator
        device = os.getenv("DEVICE")
        _generator = FrameGenerator(device=device)
    return _generator


# ─────────────────────────────────────────────────────────────
# 생성 파이프라인
# ─────────────────────────────────────────────────────────────
def run_generation_sync(
    job_id: str,
    image_bytes: bytes,
    num_frames: int,
    motion_strength: int,
    fps: int,
    use_rembg: bool,
) -> None:
    """
    이미지 → 프레임 생성 → 스프라이트 시트 저장 파이프라인 (동기).

    ThreadPoolExecutor에서 실행되며 job_store를 통해 진행 상태를 업데이트합니다.

    Args:
        job_id:          대상 Job ID
        image_bytes:     입력 이미지 바이트
        num_frames:      출력 프레임 수
        motion_strength: SVD motion_bucket_id (1~255)
        fps:             초당 프레임 수
        use_rembg:       AI 배경 제거 사용 여부
    """
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def progress_cb(p: int, msg: str) -> None:
        job_store.update_progress(job_id, p, msg)
        print(f"[{job_id[:8]}] {p:3d}% — {msg}")

    try:
        job_store.set_running(job_id)
        progress_cb(5, "이미지 로딩 중...")

        # 1. 이미지 로드 및 전처리
        image = Image.open(io.BytesIO(image_bytes))
        if use_rembg:
            progress_cb(10, "배경 제거 중 (rembg)...")
            from models.preprocessor import remove_background
            image = remove_background(image)
        else:
            image = image.convert("RGBA")

        # 2. SVD 프레임 생성
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

        # 3. 스프라이트 시트 조립
        progress_cb(95, "스프라이트 시트 조립 중...")
        from models.sprite_sheet_builder import build_sprite_sheet, create_preview_gif

        sheet, metadata = build_sprite_sheet(frames, cols=4, frame_size=512)
        metadata.update({"fps": fps, "motion_strength": motion_strength, "use_rembg": use_rembg})

        # 4. 파일 저장
        _save_outputs(job_dir, sheet, metadata, frames, fps)

        job_store.set_done(
            job_id,
            result={
                "sprite_sheet_url": f"/outputs/{job_id}/sprite_sheet.png",
                "metadata_url": f"/outputs/{job_id}/metadata.json",
                "preview_gif_url": f"/outputs/{job_id}/preview.gif",
                "num_frames": num_frames,
                "sheet_size": f"{sheet.width}×{sheet.height}",
            },
        )
        progress_cb(100, "완료!")

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[{job_id[:8]}] 오류 발생:\n{error_detail}")
        job_store.set_error(job_id, str(e), f"오류: {e}")


# ── 내부 유틸 ──────────────────────────────────────────────────
def _save_outputs(job_dir: Path, sheet, metadata: dict, frames: list, fps: int) -> None:
    """생성된 결과물을 파일로 저장합니다."""
    from models.sprite_sheet_builder import create_preview_gif

    (job_dir / "sprite_sheet.png").parent.mkdir(parents=True, exist_ok=True)
    sheet.save(str(job_dir / "sprite_sheet.png"), "PNG", optimize=False)
    (job_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    gif_bytes = create_preview_gif(frames, fps=fps, frame_size=256)
    (job_dir / "preview.gif").write_bytes(gif_bytes)
