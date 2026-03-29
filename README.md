# 💥 AnimGen — AI 게임 이펙트 애니메이션 생성기

> 2D 폭발 이펙트 이미지 **한 장**을 입력하면, **Unity 스프라이트 시트**를 자동으로 생성합니다.  
> AI 모델: **Stable Video Diffusion (SVD) img2vid-xt**  
> 백엔드: **FastAPI + PyTorch** | 프론트엔드: **React + Vite**  
> 지원 플랫폼: **Ubuntu + NVIDIA GPU** / **macOS Apple Silicon (Mac Mini M-series)**

---

## 🗂️ 프로젝트 구조

```
animation-generator/
├── backend/
│   ├── main.py                        ← 서버 진입점 (uvicorn 실행)
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   │
│   ├── api/                           ← HTTP 계층
│   │   ├── app.py                     ← FastAPI 앱 + 미들웨어 + 라우터 등록
│   │   ├── schemas.py                 ← Pydantic 요청/응답 스키마
│   │   └── routes/
│   │       ├── health.py              ← GET  /api/health
│   │       ├── generate.py            ← POST /api/generate
│   │       └── jobs.py                ← Job CRUD 엔드포인트
│   │
│   ├── services/                      ← 비즈니스 로직 계층
│   │   ├── job_service.py             ← JobStore (In-memory 상태 관리)
│   │   └── generation_service.py     ← run_generation_sync + FrameGenerator 싱글턴
│   │
│   └── models/                        ← ML 모델 & 이미지 처리 계층
│       ├── frame_generator.py         ← SVD 파이프라인 래퍼
│       ├── preprocessor.py            ← 이미지 전처리 유틸
│       ├── sprite_sheet_builder.py    ← 스프라이트 시트 조립
│       └── devices/                   ← 디바이스 추상화 서브패키지
│           ├── base.py                ← DeviceInfo + DeviceBackend (ABC)
│           ├── cuda_backend.py        ← CUDABackend (Ubuntu + NVIDIA)
│           ├── mps_backend.py         ← MPSBackend (macOS Apple Silicon)
│           ├── cpu_backend.py         ← CPUBackend (Fallback)
│           └── factory.py             ← BackendFactory (자동 감지)
│
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── App.jsx
    │   └── index.css
    ├── package.json
    └── vite.config.js
```

---

## 🖥️ 지원 플랫폼 및 디바이스

| 환경 | 칩/GPU | 백엔드 | dtype | 속도 |
|------|--------|--------|-------|------|
| Ubuntu AI 서버 | NVIDIA RTX (8~24GB+) | `CUDABackend` | fp16 | ⚡ 빠름 |
| Mac Mini M2 Pro/M4 | Apple Silicon | `MPSBackend` | fp32 | 🐢 보통 |
| 기타 (개발/테스트) | CPU | `CPUBackend` | fp32 | 🐌 느림 |

**디바이스는 자동 감지**됩니다 (CUDA → MPS → CPU 우선순위).  
`.env` 파일의 `DEVICE` 변수로 강제 지정할 수 있습니다.

---

## 🚀 실행하기

### 공통: 환경 변수 설정

```bash
cp backend/.env.example backend/.env
# .env 파일을 열어 HF_TOKEN 입력
```

> HuggingFace 토큰 발급: https://huggingface.co/settings/tokens  
> SVD 모델 접근 권한 수락: https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt

---

### 🐧 Ubuntu + NVIDIA GPU (서버)

#### Docker Compose 실행 (권장)

```bash
docker compose up --build
```

#### 직접 실행

```bash
cd backend

# PyTorch CUDA 버전 설치 (CUDA 12.1 기준)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 나머지 의존성
pip install -r requirements.txt

# 서버 실행
python main.py
```

---

### 🍎 macOS Apple Silicon (Mac Mini M-series)

Docker는 macOS에서 NVIDIA GPU를 지원하지 않으므로 직접 실행합니다.

```bash
cd backend

# PyTorch MPS 버전 (기본 PyTorch에 MPS 포함)
pip install torch torchvision

# 나머지 의존성
pip install -r requirements.txt

# 서버 실행 (MPS 자동 감지)
python main.py

# 또는 명시적으로 디바이스 지정
DEVICE=mps python main.py
```

#### 프론트엔드 (별도 터미널)

```bash
cd frontend
npm install
npm run dev
```

- 프론트엔드: http://localhost:5173
- API 문서: http://localhost:8000/docs

---

## 🎮 생성 결과물 → Unity에서 사용하기

1. `sprite_sheet.png`를 Unity **Assets/** 폴더에 드래그
2. Inspector → **Texture Type**: `Sprite (2D and UI)`
3. **Sprite Mode**: `Multiple` 설정
4. **Sprite Editor** 클릭 → **Slice** → `Grid By Cell Size`
5. Cell Size: `512 × 512` 입력 후 Slice 실행
6. 생성된 Sprites를 Animator에 드래그 → Animation Clip 자동 생성

---

## 🖼️ 스프라이트 시트 규격

| 프레임 수 | 그리드 | 시트 해상도 |
|-----------|--------|-------------|
| 8 frames  | 4 × 2  | 2048 × 1024 |
| 12 frames | 4 × 3  | 2048 × 1536 |
| 16 frames | 4 × 4  | 2048 × 2048 |

---

## ⚙️ API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/health` | 서버/디바이스 상태 확인 (CUDA·MPS·CPU 공통) |
| `POST` | `/api/generate` | 이미지 업로드 → 생성 시작 |
| `GET` | `/api/status/{job_id}` | 작업 진행 상태 조회 |
| `DELETE` | `/api/jobs/{job_id}` | 작업 및 파일 삭제 |
| `GET` | `/api/jobs` | 전체 작업 목록 조회 |
| `GET` | `/docs` | Swagger UI API 문서 |

---

## 🛠️ 환경 변수 (.env)

```env
# HuggingFace 토큰 (필수)
HF_TOKEN=hf_your_token_here

# SVD 모델 선택
SVD_MODEL=stabilityai/stable-video-diffusion-img2vid-xt

# 디바이스 강제 지정 (비워두면 자동 감지: CUDA → MPS → CPU)
# DEVICE=cuda   # Ubuntu + NVIDIA
# DEVICE=mps    # macOS Apple Silicon
# DEVICE=cpu    # CPU 전용 (테스트용)

# 모델 캐시 디렉토리
HF_HOME=./hf_cache

# 서버 설정
HOST=0.0.0.0
PORT=8000

# 출력 디렉토리
OUTPUT_DIR=./outputs

# CORS (프론트엔드 주소)
CORS_ORIGINS=http://localhost:5173
```

---

## 📦 기술 스택

| 영역 | 기술 |
|------|------|
| AI 모델 | Stable Video Diffusion (SVD) img2vid-xt |
| 배경 제거 | rembg (u2net) |
| 딥러닝 | PyTorch 2.x + CUDA / MPS + diffusers |
| 백엔드 | FastAPI + uvicorn |
| 프론트엔드 | React 18 + Vite |
| 컨테이너 | Docker + NVIDIA CUDA (Ubuntu 전용) |

---

## 🏗️ 아키텍처 설계

3계층 구조로 관심사를 분리합니다:

```
api/          ← HTTP 계층: 요청 파싱, 응답 직렬화
services/     ← 비즈니스 계층: Job 관리, 생성 파이프라인
models/       ← ML/이미지 계층: SVD 추론, 전처리, 스프라이트 조립
  └─ devices/ ← 디바이스 추상화: CUDA·MPS·CPU 차이 캡슐화
```

새로운 GPU 플랫폼 추가 시 `models/devices/`에 새 백엔드 클래스만 추가하면 됩니다.
