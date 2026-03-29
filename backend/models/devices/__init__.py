"""
models/devices/__init__.py

devices 서브패키지의 공개 API를 재노출합니다.
외부 코드는 이 패키지에서만 임포트합니다.

    from models.devices import BackendFactory, DeviceBackend, DeviceInfo
    from models.devices import CUDABackend, MPSBackend, CPUBackend
"""

from models.devices.base import DeviceBackend, DeviceInfo
from models.devices.cuda_backend import CUDABackend
from models.devices.mps_backend import MPSBackend
from models.devices.cpu_backend import CPUBackend
from models.devices.factory import BackendFactory

__all__ = [
    "DeviceBackend",
    "DeviceInfo",
    "CUDABackend",
    "MPSBackend",
    "CPUBackend",
    "BackendFactory",
]
