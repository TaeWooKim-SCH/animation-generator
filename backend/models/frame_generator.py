"""
frame_generator.py

SVD(Stable Video Diffusion) img2vid 파이프라인 래퍼.
DeviceBackend를 주입받아 플랫폼(CUDA / MPS / CPU)에 무관하게 동작합니다.

의존성:
  models.device_backend  — 플랫폼 추상화 (DeviceBackend, BackendFactory)
  models.preprocessor    — 이미지 전처리 유틸리티
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import numpy as np
import torch
from PIL import Image

from models.devices import BackendFactory, DeviceBackend, DeviceInfo
from models.preprocessor import (
    center_crop_and_resize,
    extract_alpha_by_luminance,
    prepare_for_svd,
)


class FrameGenerator:
    """
    SVD img2vid 파이프라인을 래핑하는 프레임 생성기.

    - 플랫폼 감지 및 최적화는 DeviceBackend에 위임합니다.
    - 모델은 처음 generate() 호출 시 Lazy Load됩니다.
    - BackendFactory를 통해 CUDA / MPS / CPU를 자동 선택합니다.

    Examples:
        # 환경 자동 감지 (권장)
        gen = FrameGenerator()
        frames = gen.generate(image)

        # 특정 백엔드 강제 지정
        gen = FrameGenerator(device="mps")

        # 직접 백엔드 주입 (테스트 용도)
        backend = MPSBackend()
        gen = FrameGenerator(backend=backend)
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        hf_token: Optional[str] = None,
        cache_dir: Optional[str] = None,
        device: Optional[str] = None,
        backend: Optional[DeviceBackend] = None,
    ):
        """
        Args:
            model_id:  HuggingFace 모델 ID (기본값: SVD_MODEL 환경변수 또는 img2vid-xt)
            hf_token:  HuggingFace 액세스 토큰 (기본값: HF_TOKEN 환경변수)
            cache_dir: 모델 캐시 디렉토리 (기본값: HF_HOME 또는 ./hf_cache)
            device:    "cuda" | "mps" | "cpu" | None(자동 감지)
            backend:   직접 DeviceBackend 인스턴스 주입 (테스트/확장 용도)
        """
        self.model_id = model_id or os.getenv(
            "SVD_MODEL", "stabilityai/stable-video-diffusion-img2vid-xt"
        )
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.cache_dir = cache_dir or os.getenv("HF_HOME", "./hf_cache")

        # DeviceBackend: 외부 주입 → 직접 지정 → 자동 감지 순서
        self._backend: DeviceBackend = backend or BackendFactory.create(device)
        self._info: DeviceInfo = self._backend.get_info()

        self._pipe = None  # Lazy load
        print(f"[FrameGenerator] 초기화 완료 — {self._info}")

    # ── 프로퍼티 ──────────────────────────────────────────────
    @property
    def backend(self) -> DeviceBackend:
        """현재 사용 중인 DeviceBackend를 반환합니다."""
        return self._backend

    @property
    def device_info(self) -> DeviceInfo:
        """디바이스 정보를 반환합니다."""
        return self._info

    @property
    def is_loaded(self) -> bool:
        """모델이 로드되어 있는지 확인합니다."""
        return self._pipe is not None

    # ── 모델 로드 ──────────────────────────────────────────────
    def load_model(self, progress_cb: Optional[Callable[[int, str], None]] = None) -> None:
        """
        SVD 모델을 HuggingFace에서 로드합니다 (최초 1회).
        이미 로드된 경우 즉시 반환합니다.
        """
        if self._pipe is not None:
            return

        from diffusers import StableVideoDiffusionPipeline

        print(f"[FrameGenerator] 모델 로딩 시작: {self.model_id}")
        if progress_cb:
            progress_cb(5, "모델 로딩 중...")

        dtype = self._backend.get_torch_dtype()
        kwargs: dict = {
            "torch_dtype": dtype,
            "cache_dir": self.cache_dir,
        }
        # fp16 variant는 CUDA에서만 사용 가능
        if dtype == torch.float16:
            kwargs["variant"] = "fp16"
        if self.hf_token:
            kwargs["token"] = self.hf_token

        print(f"[FrameGenerator] dtype={dtype}, device={self._info.device_type}")
        self._pipe = StableVideoDiffusionPipeline.from_pretrained(
            self.model_id, **kwargs
        )

        # 백엔드에 최적화 위임 (디바이스 이동, offload, 어텐션 최적화 등)
        self._pipe = self._backend.optimize_pipeline(self._pipe)

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
            image:               입력 PIL 이미지
            num_frames:          출력 프레임 수 (8, 12, 16)
            motion_bucket_id:    모션 강도 (1~255, 폭발: 127~200 권장)
            fps:                 생성 FPS
            noise_aug_strength:  노이즈 강도 (낮을수록 원본에 충실)
            seed:                재현성을 위한 랜덤 시드 (None=랜덤)
            use_luminance_alpha: 밝기 기반 알파 추출 사용 여부
            progress_cb:         (progress: int, message: str) 콜백

        Returns:
            512×512 RGBA PIL 이미지 리스트 (num_frames개)
        """
        # 1. 모델 로드 (필요 시)
        self.load_model(progress_cb)

        if progress_cb:
            progress_cb(20, "이미지 전처리 중...")

        # 2. SVD 입력 전처리
        svd_input = prepare_for_svd(image, target_w=1024, target_h=576)

        # 3. 모델 파라미터 결정
        model_max_frames = 25 if "xt" in self.model_id else 14
        decode_chunk_size = self._backend.get_decode_chunk_size()
        generator = self._backend.get_generator(seed)

        if progress_cb:
            progress_cb(
                25,
                f"SVD 추론 중... "
                f"({self._info.device_type.upper()}, chunk={decode_chunk_size})",
            )

        # 4. SVD 추론
        with torch.inference_mode():
            output = self._pipe(
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

        # 5. 프레임 후처리 (샘플링 → crop → 알파)
        result_frames = self._postprocess_frames(
            raw_frames, num_frames, use_luminance_alpha, progress_cb
        )

        if progress_cb:
            progress_cb(95, "프레임 생성 완료")

        return result_frames

    # ── 모델 해제 ──────────────────────────────────────────────
    def unload(self) -> None:
        """파이프라인 메모리를 해제하고 디바이스 캐시를 비웁니다."""
        if self._pipe is not None:
            del self._pipe
            self._pipe = None
            self._backend.empty_cache()
            print("[FrameGenerator] 모델 언로드 완료")

    # ── 내부 유틸 ──────────────────────────────────────────────
    def _postprocess_frames(
        self,
        raw_frames: list[Image.Image],
        num_frames: int,
        use_luminance_alpha: bool,
        progress_cb: Optional[Callable[[int, str], None]],
    ) -> list[Image.Image]:
        """프레임 샘플링 → center-crop → 알파 처리를 수행합니다."""
        selected = self._sample_frames(raw_frames, num_frames)
        result: list[Image.Image] = []

        for i, frame in enumerate(selected):
            frame_512 = center_crop_and_resize(frame, size=512)

            if use_luminance_alpha:
                frame_rgba = extract_alpha_by_luminance(frame_512, threshold=15)
            else:
                frame_rgba = frame_512.convert("RGBA")

            result.append(frame_rgba)

            if progress_cb:
                p = 75 + int((i + 1) / num_frames * 20)
                progress_cb(p, f"프레임 후처리 중... ({i + 1}/{num_frames})")

        return result

    @staticmethod
    def _sample_frames(frames: list, n: int) -> list:
        """N개의 프레임을 균등 간격으로 샘플링합니다."""
        total = len(frames)
        if n >= total:
            return frames
        indices = np.linspace(0, total - 1, n, dtype=int)
        return [frames[i] for i in indices]
