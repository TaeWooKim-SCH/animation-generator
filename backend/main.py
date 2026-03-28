"""
main.py
서버 진입점 - 이 파일을 직접 실행하거나 uvicorn으로 실행합니다.

사용법:
  cd backend
  python main.py

또는:
  uvicorn server:app --host 0.0.0.0 --port 8000 --reload
"""
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Animation Generator API 시작: http://{host}:{port}")
    print(f"📖 API 문서: http://{host}:{port}/docs")
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
