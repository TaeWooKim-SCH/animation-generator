"""
frame_generator.py
Stable Video Diffusion(SVD) img2vid를 사용하여 단일 이미지로부터
애니메이션 프레임 시퀀스를 생성합니다.
"""
import os
import math
import torch
import numpy as np
from PIL import Image
from typing import Callable, Optional
from pathlib import Path

from models.preprocessor import prepare_for_svd, center_crop_and_resize, extract_alpha_by_luminance


# ─────────────────────────────────────────────────────────────
# VRAM 자동 감지 및 설정
# ─────────────────────────────────────────────────────────────
def get_optimal_decode_chunk_size() -> int:
    """사용 가능한 VRAM에 따라 decode_chunk_size 자동 결정"""
    if not torch.cuda.is_available():
        return 1
    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    if vram_gb >= 24:
        return 8
    elif vram_gb >= 16:
        return 6
    elif vram_gb >= 12:
        return 4
    else:
        return 2


def get_device_info() -> dict:
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        return {
            "device": "cuda",
            "name": props.name,
            "vram_gb": round(props.total_memory / (1024 ** 3), 1),
        }
    return {"device": "cpu", "name": "CPU", "vram_gb": 0}


# ─────────────────────────────────────────────────────────────
# FrameGenerator 클래스
# ─────────────────────────────────────────────────────────────
class FrameGenerator:
    """
    SVD img2vid 파이프라인을 래핑하는 프레임 생성기.
    모델은 처음 generate() 호출 시 lazy load됩니다.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        hf_token: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        self.model_id = model_id or os.getenv(
            "SVD_MODEL", "stabilityai/stable-video-diffusion-img2vid-xt"
        )
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.cache_dir = cache_dir or os.getenv("HF_HOME", "./hf_cache")
        self.pipe = None
        self._device_info = get_device_info()
        print(f"[FrameGenerator] 디바이스: {self._device_info}")

    # ── 모델 로드 ──────────────────────────────────────────────
    def load_model(self, progress_cb: Optional[Callable] = None):
        """SVD 모델을 HuggingFace에서 로드합니다 (최초 1회)."""
        if self.pipe is not None:
            return

        from diffusers import StableVideoDiffusionPipeline

        print(f"[FrameGenerator] 모델 로딩: {self.model_id}")
        if progress_cb:
            progress_cb(5, "모델 로딩 중...")

        kwargs = {
            "torch_dtype": torch.float16,
            "variant": "fp16",
            "cache_dir": self.cache_dir,
        }
        if self.hf_token:
            kwargs["token"] = self.hf_token

        self.pipe = StableVideoDiffusionPipeline.from_pretrained(self.model_id, **kwargs)

        # VRAM 절약: CPU offload
        vram_gb = self._device_info.get("vram_gb", 0)
        if vram_gb < 16 and torch.cuda.is_available():
            print(f"[FrameGenerator] VRAM {vram_gb}GB 감지 → CPU offload 활성화")
            self.pipe.enable_model_cpu_offload()
        elif torch.cuda.is_available():
            self.pipe = self.pipe.to("cuda")

        # xFormers 메모리 효율 어텐션 (사용 가능한 경우)
        try:
            self.pipe.enable_xformers_memory_efficient_attention()
            print("[FrameGenerator] xFormers 활성화")
        except Exception:
            pass

        print("[FrameGenerator] 모델 로드 완료")
        if progress_cb:
            progress_cb(15, "모델 로드 완료")

    # ── 프레임 생성 ────────────────────────────────────────────
    def generate(
        self,
        image: Image.Image,
        num_frames: int = 8,
        motion_bucket_id: int = 127,
        fps: int = 12,
        noise_aug_strength: float = 0.02,
        seed: Optional[int] = None,
        use_luminance_alpha: bool = True,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> list[Image.Image]:
        """
        단일 이미지에서 N개의 애니메이션 프레임을 생성합니다.

        Args:
            image: 입력 PIL 이미지 (어떤 크기든 OK)
            num_frames: 출력 프레임 수 (8, 12, 16)
            motion_bucket_id: 모션 강도 (1~255, 클수록 강한 움직임 / 폭발: 127~200 추천)
            fps: 생성 FPS (최종 스프라이트 시트 메타데이터에 반영)
            noise_aug_strength: 노이즈 강도 (낮을수록 원본에 충실)
            seed: 재현성을 위한 랜덤 시드 (None=랜덤)
            use_luminance_alpha: 밝기 기반 알파 추출 사용 여부
            progress_cb: (progress: int, message: str) 콜백

        Returns:
            512×512 RGBA PIL 이미지 리스트 (num_frames개)
        """
        # 모델 로드 (필요시)
        self.load_model(progress_cb)

        if progress_cb:
            progress_cb(20, "이미지 전처리 중...")

        # SVD 입력 크기에 맞게 전처리
        svd_input = prepare_for_svd(image, target_w=1024, target_h=576)

        # SVD 모델 내부 프레임 수 확인
        # img2vid: 14프레임, img2vid-xt: 25프레임
        model_max_frames = 25 if "xt" in self.model_id else 14
        decode_chunk_size = get_optimal_decode_chunk_size()

        if progress_cb:
            progress_cb(25, f"SVD 추론 중... (chunk={decode_chunk_size})")

        generator = None
        if seed is not None:
            generator = torch.manual_seed(seed)

        # SVD 실행
        with torch.inference_mode():
            output = self.pipe(
                svd_input,
                num_frames=model_max_frames,
                motion_bucket_id=motion_bucket_id,
                fps=fps,
                noise_aug_strength=noise_aug_strength,
                decode_chunk_size=decode_chunk_size,
                generator=generator,
                output_type="pil",
            )

        raw_frames: list[Image.Image] = output.frames[0]

        if progress_cb:
            progress_cb(75, f"{len(raw_frames)}개 프레임 생성 완료, 후처리 중...")

        # 균등 샘플링으로 원하는 프레임 수 선택
        selected = self._sample_frames(raw_frames, num_frames)

        # 각 프레임 후처리: 크롭 → 리사이즈 → 알파 적용
        result_frames = []
        for i, frame in enumerate(selected):
            # 512×512 center-crop
            frame_512 = center_crop_and_resize(frame, size=512)

            # 알파 채널 생성
            if use_luminance_alpha:
                frame_rgba = extract_alpha_by_luminance(frame_512, threshold=15)
            else:
                frame_rgba = frame_512.convert("RGBA")

            result_frames.append(frame_rgba)

            if progress_cb:
                p = 75 + int((i + 1) / num_frames * 20)
                progress_cb(p, f"프레임 후처리 중... ({i+1}/{num_frames})")

        if progress_cb:
            progress_cb(95, "프레임 생성 완료")

        return result_frames

    # ── 내부 유틸 ──────────────────────────────────────────────
    @staticmethod
    def _sample_frames(frames: list, n: int) -> list:
        """N개의 프레임을 균등 간격으로 샘플링합니다."""
        total = len(frames)
        if n >= total:
            return frames
        indices = np.linspace(0, total - 1, n, dtype=int)
        return [frames[i] for i in indices]

    @property
    def device_info(self) -> dict:
        return self._device_info

    def unload(self):
        """메모리 해제"""
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("[FrameGenerator] 모델 언로드 완료")
