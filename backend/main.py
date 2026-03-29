"""
main.py

서버 진입점 — 이 파일을 직접 실행하거나 uvicorn으로 실행합니다.

사용법:
  cd backend
  python main.py

또는 uvicorn 직접 실행:
  uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload

환경 변수:
  HOST    서버 바인드 주소 (기본값: 0.0.0.0)
  PORT    서버 포트 (기본값: 8000)
  DEVICE  디바이스 강제 지정: cuda | mps | cpu (기본값: 자동 감지)
"""

import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    device = os.getenv("DEVICE", "자동 감지")

    print(f"🚀 Animation Generator API 시작: http://{host}:{port}")
    print(f"📖 API 문서: http://{host}:{port}/docs")
    print(f"🖥️  디바이스: {device}")

    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
