"""
cuda_backend.py

NVIDIA CUDA GPU 백엔드.
Ubuntu AI 서버(NVIDIA GPU) 환경에 최적화됩니다.

최적화 전략:
  - VRAM >= 16 GB : 전체 GPU 로드
  - VRAM < 16 GB  : CPU offload 활성화
  - xFormers 설치 시 메모리 효율 어텐션 활성화
"""

from __future__ import annotations

import platform
from typing import Optional

import torch

from models.devices.base import DeviceBackend, DeviceInfo


class CUDABackend(DeviceBackend):
    """NVIDIA CUDA GPU 백엔드."""

    def is_available(self) -> bool:
        return torch.cuda.is_available()

    def get_info(self) -> DeviceInfo:
        if not self.is_available():
            raise RuntimeError("CUDA를 사용할 수 없습니다.")
        props = torch.cuda.get_device_properties(0)
        return DeviceInfo(
            device_type="cuda",
            device_name=props.name,
            memory_gb=round(props.total_memory / (1024 ** 3), 1),
            platform_os=platform.system(),
            extra={
                "cuda_version": torch.version.cuda,
                "cudnn_version": torch.backends.cudnn.version(),
                "device_count": torch.cuda.device_count(),
            },
        )

    def get_torch_dtype(self) -> torch.dtype:
        # CUDA는 fp16 완전 지원 — 메모리 절약 효과
        return torch.float16

    def get_decode_chunk_size(self) -> int:
        """VRAM 용량에 따라 최적 청크 크기를 반환합니다."""
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if vram_gb >= 24:
            return 8
        elif vram_gb >= 16:
            return 6
        elif vram_gb >= 12:
            return 4
        else:
            return 2

    def optimize_pipeline(self, pipe) -> object:
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)

        if vram_gb < 16:
            # VRAM 부족 시 CPU offload로 VRAM 절약
            print(f"[CUDABackend] VRAM {vram_gb:.1f} GB → CPU offload 활성화")
            pipe.enable_model_cpu_offload()
        else:
            pipe = pipe.to("cuda")
            print(f"[CUDABackend] VRAM {vram_gb:.1f} GB → 전체 GPU 로드")

        # xFormers 메모리 효율 어텐션 (설치된 경우에만)
        try:
            pipe.enable_xformers_memory_efficient_attention()
            print("[CUDABackend] xFormers 메모리 효율 어텐션 활성화")
        except Exception:
            print("[CUDABackend] xFormers 미설치 — 기본 어텐션 사용")

        return pipe

    def get_generator(self, seed: Optional[int]) -> Optional[torch.Generator]:
        if seed is None:
            return None
        return torch.Generator(device="cuda").manual_seed(seed)

    def empty_cache(self) -> None:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("[CUDABackend] CUDA 캐시 비움")
