"""
cpu_backend.py

CPU Fallback 백엔드.
GPU를 사용할 수 없는 환경에서 동작합니다.

⚠️ 주의: SVD 모델의 CPU 추론은 매우 느립니다.
    테스트/개발 목적으로만 사용을 권장합니다.
"""

from __future__ import annotations

import platform
from typing import Optional

import torch

from models.devices.base import DeviceBackend, DeviceInfo


class CPUBackend(DeviceBackend):
    """CPU Fallback 백엔드 (항상 사용 가능)."""

    def is_available(self) -> bool:
        return True  # CPU는 항상 사용 가능

    def get_info(self) -> DeviceInfo:
        cpu_name = platform.processor() or "Unknown CPU"
        memory_gb = self._get_system_ram_gb()
        return DeviceInfo(
            device_type="cpu",
            device_name=cpu_name,
            memory_gb=memory_gb,
            platform_os=platform.system(),
        )

    def get_torch_dtype(self) -> torch.dtype:
        return torch.float32

    def get_decode_chunk_size(self) -> int:
        # CPU는 최소 청크로 OOM 방지
        return 1

    def optimize_pipeline(self, pipe) -> object:
        pipe = pipe.to("cpu")
        print("[CPUBackend] 파이프라인을 CPU로 이동 (⚠️ 매우 느림)")
        try:
            pipe.enable_attention_slicing(1)
        except Exception:
            pass
        return pipe

    def get_generator(self, seed: Optional[int]) -> Optional[torch.Generator]:
        if seed is None:
            return None
        return torch.Generator(device="cpu").manual_seed(seed)

    # ── 내부 유틸 ──────────────────────────────────────────────
    @staticmethod
    def _get_system_ram_gb() -> float:
        try:
            import psutil
            return round(psutil.virtual_memory().total / (1024 ** 3), 1)
        except ImportError:
            return 0.0
