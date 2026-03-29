"""
test_generate.py

서버 없이 모델 파이프라인만 단독으로 테스트합니다.
이미지 한 장을 입력하면 스프라이트 시트와 GIF 미리보기를 출력합니다.

사용법:
  cd backend
  python test_generate.py --image /path/to/effect.png

옵션:
  --image     입력 이미지 경로 (필수)
  --frames    출력 프레임 수 (기본값: 8)
  --motion    모션 강도 1~255 (기본값: 127)
  --fps       초당 프레임 수 (기본값: 12)
  --no-rembg  배경 제거 건너뜀
  --device    디바이스 강제 지정: cuda | mps | cpu (기본값: 자동)
  --output    결과 저장 폴더 (기본값: ./test_output)
  --seed      재현을 위한 시드 (기본값: 42)

예시:
  # 기본 실행
  python test_generate.py --image explosion.png

  # Apple Silicon Mac에서 실행
  python test_generate.py --image explosion.png --device mps

  # 빠른 테스트 (배경 제거 생략, 적은 프레임)
  python test_generate.py --image explosion.png --frames 4 --no-rembg
"""

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────
# CLI 인자 파싱
# ─────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AnimGen 단독 테스트 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--image", required=True, metavar="PATH",
        help="입력 이미지 경로 (PNG/JPG)",
    )
    parser.add_argument(
        "--frames", type=int, default=8, choices=[4, 8, 12, 16],
        help="출력 프레임 수 (기본값: 8)",
    )
    parser.add_argument(
        "--motion", type=int, default=127, metavar="1-255",
        help="모션 강도 (기본값: 127, 폭발은 150~200 권장)",
    )
    parser.add_argument(
        "--fps", type=int, default=12,
        help="초당 프레임 수 (기본값: 12)",
    )
    parser.add_argument(
        "--no-rembg", action="store_true",
        help="배경 제거(rembg) 생략",
    )
    parser.add_argument(
        "--device", choices=["cuda", "mps", "cpu"], default=None,
        help="디바이스 강제 지정 (기본값: 자동 감지)",
    )
    parser.add_argument(
        "--output", default="./test_output", metavar="DIR",
        help="결과 저장 폴더 (기본값: ./test_output)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="재현성을 위한 랜덤 시드 (기본값: 42)",
    )
    return parser.parse_args()


# ─────────────────────────────────────────────────────────────
# 진행 상태 출력
# ─────────────────────────────────────────────────────────────
def make_progress_cb(start_time: float):
    """진행률을 터미널에 출력하는 콜백을 생성합니다."""
    def cb(progress: int, message: str) -> None:
        elapsed = time.time() - start_time
        bar_len = 30
        filled = int(bar_len * progress / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {progress:3d}%  {message:<35} ({elapsed:.1f}s)", end="", flush=True)
        if progress >= 100:
            print()  # 완료 시 줄바꿈
    return cb


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()

    # ── 입력 이미지 확인 ──────────────────────────────────────
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"❌ 이미지 파일을 찾을 수 없습니다: {image_path}")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("  🎆 AnimGen — 단독 테스트 스크립트")
    print("=" * 60)
    print(f"  입력 이미지  : {image_path}")
    print(f"  프레임 수    : {args.frames}")
    print(f"  모션 강도    : {args.motion}")
    print(f"  FPS          : {args.fps}")
    print(f"  배경 제거    : {'건너뜀' if args.no_rembg else '사용 (rembg)'}")
    print(f"  디바이스     : {args.device or '자동 감지'}")
    print(f"  출력 폴더    : {output_dir.resolve()}")
    print("=" * 60 + "\n")

    from PIL import Image

    # ── 이미지 로드 ───────────────────────────────────────────
    print("📂 이미지 로딩...")
    image = Image.open(image_path)
    print(f"  원본 크기: {image.size[0]}×{image.size[1]}  모드: {image.mode}")

    # ── 배경 제거 ─────────────────────────────────────────────
    if not args.no_rembg:
        print("\n🔍 배경 제거 중 (rembg)...")
        t0 = time.time()
        try:
            from models.preprocessor import remove_background
            image = remove_background(image)
            print(f"  ✅ 완료 ({time.time() - t0:.1f}s)")
        except Exception as e:
            print(f"  ⚠️  rembg 실패, 건너뜀: {e}")
            image = image.convert("RGBA")
    else:
        image = image.convert("RGBA")

    # ── 모델 로드 & 프레임 생성 ──────────────────────────────
    print("\n🤖 모델 초기화...")
    from models.frame_generator import FrameGenerator
    generator = FrameGenerator(device=args.device)
    print(f"  디바이스: {generator.device_info}")

    print("\n🎬 프레임 생성 중...\n")
    start = time.time()
    progress_cb = make_progress_cb(start)

    frames = generator.generate(
        image=image,
        num_frames=args.frames,
        motion_bucket_id=args.motion,
        fps=args.fps,
        seed=args.seed,
        use_luminance_alpha=True,
        progress_cb=progress_cb,
    )
    elapsed = time.time() - start
    print(f"\n  ✅ {len(frames)}개 프레임 생성 완료 (총 {elapsed:.1f}s)\n")

    # ── 스프라이트 시트 조립 ──────────────────────────────────
    print("🗂️  스프라이트 시트 조립 중...")
    from models.sprite_sheet_builder import build_sprite_sheet, create_preview_gif

    sheet, metadata = build_sprite_sheet(frames, cols=4, frame_size=512)
    metadata.update({
        "fps": args.fps,
        "motion_strength": args.motion,
        "source_image": str(image_path.resolve()),
        "elapsed_sec": round(elapsed, 1),
        "device": str(generator.device_info),
    })

    # ── 파일 저장 ─────────────────────────────────────────────
    sheet_path  = output_dir / "sprite_sheet.png"
    meta_path   = output_dir / "metadata.json"
    gif_path    = output_dir / "preview.gif"

    sheet.save(str(sheet_path), "PNG")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    gif_bytes = create_preview_gif(frames, fps=args.fps, frame_size=256)
    gif_path.write_bytes(gif_bytes)

    # ── 결과 출력 ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ✅ 완료!")
    print("=" * 60)
    print(f"  스프라이트 시트 : {sheet_path}")
    print(f"    해상도         : {sheet.width}×{sheet.height} px")
    print(f"    파일 크기      : {sheet_path.stat().st_size / 1024:.1f} KB")
    print(f"  GIF 미리보기    : {gif_path}")
    print(f"    파일 크기      : {gif_path.stat().st_size / 1024:.1f} KB")
    print(f"  메타데이터      : {meta_path}")
    print(f"  총 소요 시간    : {elapsed:.1f}초")
    print("=" * 60 + "\n")

    print("💡 Unity 적용 방법:")
    print(f"  1. {sheet_path.name} 를 Unity Assets/ 에 드래그")
    print("  2. Texture Type → Sprite (2D and UI)")
    print("  3. Sprite Mode → Multiple")
    print("  4. Sprite Editor → Slice → Grid By Cell Size (512, 512)")
    print()


if __name__ == "__main__":
    main()
