"""
base.py

디바이스 추상화의 기반 타입.
  - DeviceInfo  : 플랫폼 공통 디바이스 정보 (불변 데이터클래스)
  - DeviceBackend (ABC) : 새 플랫폼 지원 시 상속하여 구현할 추상 베이스 클래스
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional

import torch


@dataclass(frozen=True)
class DeviceInfo:
    """
    플랫폼에 관계없이 동일한 인터페이스로 디바이스 정보를 제공합니다.
    frozen=True 로 불변 객체를 보장합니다.
    """

    device_type: str        # "cuda" | "mps" | "cpu"
    device_name: str        # GPU/CPU 이름
    memory_gb: float        # 사용 가능한 메모리 (VRAM 또는 공유 RAM)
    platform_os: str        # "Linux" | "Darwin" | "Windows"
    extra: dict = field(default_factory=dict)  # 디바이스별 추가 정보

    @property
    def torch_device(self) -> torch.device:
        return torch.device(self.device_type)

    def __str__(self) -> str:
        return (
            f"[{self.device_type.upper()}] {self.device_name} "
            f"({self.memory_gb:.1f} GB) on {self.platform_os}"
        )


class DeviceBackend(abc.ABC):
    """
    플랫폼별 차이를 캡슐화하는 추상 디바이스 백엔드.

    새로운 플랫폼 지원 시 이 클래스를 상속하고
    아래 추상 메서드를 모두 구현합니다.

    책임:
      - 현재 환경에서 사용 가능 여부 판단
      - 디바이스 정보 제공
      - 파이프라인 최적화 (디바이스 이동, 어텐션, offload 등)
      - 적합한 torch dtype / chunk size / generator 제공
    """

    # ── 환경 확인 ──────────────────────────────────────────────
    @abc.abstractmethod
    def is_available(self) -> bool:
        """이 백엔드를 현재 환경에서 사용할 수 있는지 확인합니다."""

    # ── 정보 제공 ──────────────────────────────────────────────
    @abc.abstractmethod
    def get_info(self) -> DeviceInfo:
        """디바이스 정보를 반환합니다."""

    # ── 모델 최적화 파라미터 ───────────────────────────────────
    @abc.abstractmethod
    def get_torch_dtype(self) -> torch.dtype:
        """최적의 torch 데이터 타입을 반환합니다 (fp16 / fp32)."""

    @abc.abstractmethod
    def get_decode_chunk_size(self) -> int:
        """메모리에 따른 최적 decode_chunk_size를 반환합니다."""

    # ── 파이프라인 최적화 ──────────────────────────────────────
    @abc.abstractmethod
    def optimize_pipeline(self, pipe) -> object:
        """
        로드된 파이프라인을 이 디바이스에 맞게 최적화합니다.
        (device 이동, CPU offload, 어텐션 최적화 등)

        Returns:
            최적화된 파이프라인 (in-place 수정 또는 새 객체)
        """

    # ── 재현성 ─────────────────────────────────────────────────
    @abc.abstractmethod
    def get_generator(self, seed: Optional[int]) -> Optional[torch.Generator]:
        """재현성을 위한 torch.Generator를 생성합니다."""

    # ── 메모리 관리 (선택적 오버라이드) ───────────────────────
    def empty_cache(self) -> None:
        """디바이스 메모리 캐시를 비웁니다 (기본: no-op)."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.get_info()})"
