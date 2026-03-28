"""
preprocessor.py
입력 이미지 전처리: 배경 제거, SVD용 리사이즈, 알파 복원 유틸리티
"""
import io
import numpy as np
from PIL import Image


def remove_background(image: Image.Image) -> Image.Image:
    """
    rembg (AI 배경 제거)를 사용하여 배경을 제거하고 RGBA 이미지를 반환합니다.
    rembg는 import 시점에 모델을 로드하므로 첫 실행이 느릴 수 있습니다.
    """
    try:
        from rembg import remove
        img_bytes = io.BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        result_bytes = remove(img_bytes.read())
        return Image.open(io.BytesIO(result_bytes)).convert("RGBA")
    except ImportError:
        print("[preprocessor] rembg not installed, skipping background removal")
        return image.convert("RGBA")


def extract_alpha_by_luminance(
    image: Image.Image, threshold: int = 15, smooth_edge: bool = True
) -> Image.Image:
    """
    밝기 기반으로 알파 채널을 생성합니다.
    폭발/불꽃처럼 어두운 배경에 밝은 이펙트가 있는 경우에 유용합니다.
    - 어두운 픽셀: 투명 (alpha=0)
    - 밝은 픽셀: 불투명 (alpha=255)
    """
    rgb = np.array(image.convert("RGB"), dtype=np.float32)
    # ITU-R BT.601 luminance
    luminance = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    # Linear ramp for soft edges
    alpha = np.clip((luminance - threshold) * (255.0 / (255.0 - threshold)), 0, 255)
    alpha = alpha.astype(np.uint8)
    rgba = np.dstack([rgb.astype(np.uint8), alpha])
    return Image.fromarray(rgba, "RGBA")


def prepare_for_svd(image: Image.Image, target_w: int = 1024, target_h: int = 576) -> Image.Image:
    """
    SVD 모델 입력 규격(1024×576)에 맞게 이미지를 변환합니다.
    - 원본 비율 유지 후 center-pad
    - RGB 출력 (SVD는 RGB만 지원)
    """
    image = image.convert("RGBA")
    orig_w, orig_h = image.size

    # 원본 비율 유지하며 목표 크기에 맞게 축소
    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    resized = image.resize((new_w, new_h), Image.LANCZOS)

    # 검은 캔버스 중앙에 배치 (SVD는 RGB이므로 검은 배경 사용)
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 255))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y), resized if resized.mode == "RGBA" else None)

    return canvas.convert("RGB")


def center_crop_and_resize(image: Image.Image, size: int = 512) -> Image.Image:
    """
    이미지를 정사각형으로 center-crop 후 target size로 리사이즈합니다.
    SVD 출력 프레임을 512×512로 변환하는 데 사용합니다.
    """
    w, h = image.size
    min_side = min(w, h)
    left = (w - min_side) // 2
    top = (h - min_side) // 2
    cropped = image.crop((left, top, left + min_side, top + min_side))
    return cropped.resize((size, size), Image.LANCZOS)


def validate_input_image(image: Image.Image) -> tuple[bool, str]:
    """
    입력 이미지의 유효성을 검사합니다.
    Returns: (is_valid, error_message)
    """
    min_size = 64
    max_size = 4096

    w, h = image.size
    if w < min_size or h < min_size:
        return False, f"이미지가 너무 작습니다. 최소 {min_size}×{min_size}px 필요"
    if w > max_size or h > max_size:
        return False, f"이미지가 너무 큽니다. 최대 {max_size}×{max_size}px"

    return True, ""
