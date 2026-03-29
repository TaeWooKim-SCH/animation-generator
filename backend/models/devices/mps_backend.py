"""
mps_backend.py

Apple Metal Performance Shaders(MPS) 백엔드.
Mac Mini M1/M2/M3/M4 등 Apple Silicon 환경에 최적화됩니다.

설계 주의사항:
  - MPS는 fp16 일부 연산 미지원 → float32 사용
  - xFormers 미지원 → attention_slicing으로 메모리 절약
  - 유니파이드 메모리(CPU+GPU 공유) → 시스템 RAM을 기준으로 판단
  - torch.Generator는 MPS device에서 불안정 → cpu device로 생성
"""

from __future__ import annotations

import platform
from typing import Optional

import torch

from models.devices.base import DeviceBackend, DeviceInfo


class MPSBackend(DeviceBackend):
    """Apple Silicon MPS 백엔드."""

    def is_available(self) -> bool:
        return (
            platform.system() == "Darwin"
            and hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        )

    def get_info(self) -> DeviceInfo:
        if not self.is_available():
            raise RuntimeError("MPS를 사용할 수 없습니다.")

        chip = self._get_chip_name()
        memory_gb = self._get_system_ram_gb()

        return DeviceInfo(
            device_type="mps",
            device_name=chip,
            memory_gb=memory_gb,
            platform_os="Darwin",
            extra={"unified_memory": True},
        )

    def get_torch_dtype(self) -> torch.dtype:
        # MPS는 fp16 일부 ops 미지원 → float32 안전
        return torch.float32

    def get_decode_chunk_size(self) -> int:
        """유니파이드 메모리(RAM) 용량 기준으로 결정합니다."""
        ram_gb = self._get_system_ram_gb()
        if ram_gb >= 32:
            return 4
        elif ram_gb >= 16:
            return 2
        else:
            return 1

    def optimize_pipeline(self, pipe) -> object:
        # MPS 디바이스로 이동 (float32 강제)
        pipe = pipe.to(torch.device("mps"), torch.float32)
        print("[MPSBackend] 파이프라인을 MPS(float32)로 이동")

        # MPS는 attention_slicing으로 메모리 절약
        try:
            pipe.enable_attention_slicing()
            print("[MPSBackend] Attention slicing 활성화")
        except Exception:
            pass

        return pipe

    def get_generator(self, seed: Optional[int]) -> Optional[torch.Generator]:
        if seed is None:
            return None
        # MPS Generator 불안정 → cpu device로 생성
        return torch.Generator(device="cpu").manual_seed(seed)

    def empty_cache(self) -> None:
        if hasattr(torch.mps, "empty_cache"):
            torch.mps.empty_cache()
            print("[MPSBackend] MPS 캐시 비움")

    # ── 내부 유틸 ──────────────────────────────────────────────
    @staticmethod
    def _get_chip_name() -> str:
        """Apple Silicon 칩 이름을 반환합니다."""
        import subprocess
        try:
            return subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            return "Apple Silicon"

    @staticmethod
    def _get_system_ram_gb() -> float:
        """시스템 RAM(유니파이드 메모리) 크기를 GB로 반환합니다."""
        try:
            import psutil
            return round(psutil.virtual_memory().total / (1024 ** 3), 1)
        except ImportError:
            return 8.0  # 보수적 기본값
