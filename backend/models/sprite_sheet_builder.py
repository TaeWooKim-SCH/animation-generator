"""
sprite_sheet_builder.py
프레임 시퀀스로부터 Unity 스프라이트 시트 PNG와 메타데이터 JSON을 생성합니다.
"""
import io
import math
import numpy as np
from PIL import Image
from typing import Callable


def build_sprite_sheet(
    frames: list[Image.Image],
    cols: int = 4,
    frame_size: int = 512,
) -> tuple[Image.Image, dict]:
    """
    프레임 리스트를 그리드로 배치하여 스프라이트 시트를 생성합니다.

    Args:
        frames: RGBA PIL 이미지 리스트 (각 512×512)
        cols: 열 수 (기본값 4)
        frame_size: 각 프레임 크기 (px)

    Returns:
        (sprite_sheet_image, metadata_dict)
    """
    num_frames = len(frames)
    rows = math.ceil(num_frames / cols)

    sheet_w = cols * frame_size
    sheet_h = rows * frame_size

    # 투명 배경으로 스프라이트 시트 생성
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    frame_metadata = []
    for i, frame in enumerate(frames):
        col = i % cols
        row = i // cols
        x = col * frame_size
        y = row * frame_size

        # 프레임을 정확한 크기로 리사이즈
        if frame.size != (frame_size, frame_size):
            frame = frame.resize((frame_size, frame_size), Image.LANCZOS)

        # RGBA 확인
        if frame.mode != "RGBA":
            frame = frame.convert("RGBA")

        sheet.paste(frame, (x, y), frame)

        frame_metadata.append({
            "index": i,
            "x": x,
            "y": y,
            "w": frame_size,
            "h": frame_size,
            "pivot_x": 0.5,
            "pivot_y": 0.5,
        })

    metadata = {
        "version": "1.0",
        "frame_width": frame_size,
        "frame_height": frame_size,
        "num_frames": num_frames,
        "cols": cols,
        "rows": rows,
        "sheet_width": sheet_w,
        "sheet_height": sheet_h,
        "unity": {
            "import_settings": {
                "sprite_mode": "Multiple",
                "pixels_per_unit": 100,
                "slice_type": "GridByCellSize",
                "cell_width": frame_size,
                "cell_height": frame_size,
            },
            "animation_hint": f"Slice by Grid Cell Size ({frame_size}, {frame_size}), then create Animation Clip"
        },
        "frames": frame_metadata,
    }

    return sheet, metadata


def create_preview_gif(
    frames: list[Image.Image],
    fps: int = 12,
    frame_size: int = 256,
) -> bytes:
    """
    애니메이션 미리보기용 GIF를 생성합니다.

    Args:
        frames: RGBA PIL 이미지 리스트
        fps: 초당 프레임 수
        frame_size: GIF 크기 (파일 크기 절약을 위해 원본보다 작게)

    Returns:
        GIF 바이트
    """
    duration_ms = int(1000 / fps)

    # GIF는 알파 투명도를 완전히 지원하지 않으므로 검은 배경에 합성
    gif_frames = []
    for frame in frames:
        bg = Image.new("RGBA", frame.size, (15, 15, 25, 255))
        if frame.mode == "RGBA":
            bg.paste(frame, mask=frame.split()[3])
        else:
            bg.paste(frame.convert("RGBA"))

        # 리사이즈
        resized = bg.resize((frame_size, frame_size), Image.LANCZOS).convert("P", palette=Image.ADAPTIVE, colors=256)
        gif_frames.append(resized)

    buf = io.BytesIO()
    gif_frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=duration_ms,
        loop=0,  # 무한 루프
        optimize=True,
    )
    buf.seek(0)
    return buf.read()


def create_preview_apng(
    frames: list[Image.Image],
    fps: int = 12,
    frame_size: int = 256,
) -> bytes:
    """
    알파 투명도가 보존되는 APNG 미리보기를 생성합니다.
    (GIF보다 품질이 좋지만 파일이 큼)
    """
    try:
        import imageio.v3 as iio
        duration_s = 1.0 / fps

        resized_frames = []
        for frame in frames:
            if frame.mode != "RGBA":
                frame = frame.convert("RGBA")
            resized = frame.resize((frame_size, frame_size), Image.LANCZOS)
            resized_frames.append(np.array(resized))

        buf = io.BytesIO()
        iio.imwrite(
            buf,
            resized_frames,
            format="PNG",
            extension=".apng",
            fps=fps,
            loop=0,
        )
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[sprite_sheet_builder] APNG 생성 실패, GIF로 대체: {e}")
        return create_preview_gif(frames, fps, frame_size)
