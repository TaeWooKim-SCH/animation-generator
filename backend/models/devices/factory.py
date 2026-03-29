"""
factory.py

BackendFactory: 실행 환경을 자동으로 감지하여 적절한 DeviceBackend를 생성합니다.

우선순위: CUDA → MPS → CPU

Examples:
    # 자동 감지 (권장)
    backend = BackendFactory.create()

    # 강제 지정
    backend = BackendFactory.create("mps")
    backend = BackendFactory.create("cuda")
    backend = BackendFactory.create("cpu")
"""

from __future__ import annotations

from typing import Optional

from models.devices.base import DeviceBackend
from models.devices.cuda_backend import CUDABackend
from models.devices.cpu_backend import CPUBackend
from models.devices.mps_backend import MPSBackend


class BackendFactory:
    """
    실행 환경에 맞는 DeviceBackend를 생성하는 팩토리 클래스.

    새 백엔드를 추가하려면 _REGISTRY에 등록하고
    우선순위 _AUTO_ORDER 리스트에 삽입합니다.
    """

    # 등록된 모든 백엔드
    _REGISTRY: dict[str, type[DeviceBackend]] = {
        "cuda": CUDABackend,
        "mps": MPSBackend,
        "cpu": CPUBackend,
    }

    # 자동 감지 우선순위 (앞 → 뒤 순서로 시도)
    _AUTO_ORDER: list[str] = ["cuda", "mps", "cpu"]

    @classmethod
    def create(cls, device: Optional[str] = None) -> DeviceBackend:
        """
        DeviceBackend 인스턴스를 생성합니다.

        Args:
            device: "cuda" | "mps" | "cpu" | None(자동 감지)

        Returns:
            사용 가능한 DeviceBackend 인스턴스

        Raises:
            ValueError: 지정한 디바이스를 사용할 수 없거나 알 수 없는 경우
        """
        if device is not None:
            return cls._create_explicit(device.lower())
        return cls._create_auto()

    @classmethod
    def list_available(cls) -> list[str]:
        """현재 환경에서 사용 가능한 모든 백엔드 이름을 반환합니다."""
        return [
            name
            for name in cls._AUTO_ORDER
            if cls._REGISTRY[name]().is_available()
        ]

    # ── 내부 메서드 ────────────────────────────────────────────
    @classmethod
    def _create_explicit(cls, device: str) -> DeviceBackend:
        """지정된 디바이스로 백엔드를 생성합니다."""
        if device not in cls._REGISTRY:
            raise ValueError(
                f"알 수 없는 디바이스: '{device}'. "
                f"지원 목록: {list(cls._REGISTRY.keys())}"
            )
        backend = cls._REGISTRY[device]()
        if not backend.is_available():
            raise ValueError(
                f"'{device}' 디바이스를 현재 환경에서 사용할 수 없습니다."
            )
        print(f"[BackendFactory] 강제 지정: {backend.get_info()}")
        return backend

    @classmethod
    def _create_auto(cls) -> DeviceBackend:
        """우선순위에 따라 자동으로 백엔드를 선택합니다."""
        for name in cls._AUTO_ORDER:
            backend = cls._REGISTRY[name]()
            if backend.is_available():
                print(f"[BackendFactory] 자동 감지: {backend.get_info()}")
                return backend
        # CPUBackend는 always True이므로 여기까지 오면 버그
        raise RuntimeError("사용 가능한 디바이스를 찾을 수 없습니다.")
