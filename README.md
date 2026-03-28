# 💥 AnimGen — AI 게임 이펙트 애니메이션 생성기

> 2D 폭발 이펙트 이미지 **한 장**을 입력하면, **Unity 스프라이트 시트**를 자동으로 생성합니다.  
> AI 모델: **Stable Video Diffusion (SVD) img2vid-xt**  
> 백엔드: **FastAPI + PyTorch**  |  프론트엔드: **React + Vite**

---

## 🗂️ 프로젝트 구조

```
animation-generator/
├── backend/
│   ├── models/
│   │   ├── frame_generator.py      # SVD 파이프라인
│   │   ├── sprite_sheet_builder.py # 스프라이트 시트 조립
│   │   └── preprocessor.py         # 배경 제거, 리사이즈
│   ├── server.py                   # FastAPI REST API
│   ├── main.py                     # 서버 진입점
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/             # React 컴포넌트
│   │   ├── App.jsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
└── README.md
```

---

## 🚀 서버에서 실행하기 (Ubuntu + GPU)

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/animation-generator.git
cd animation-generator
```

### 2. 환경 변수 설정

```bash
cp backend/.env.example backend/.env
# .env 파일을 열어 HF_TOKEN 입력
nano backend/.env
```

> HuggingFace 토큰 발급: https://huggingface.co/settings/tokens  
> SVD 모델 접근 권한 수락: https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt

### 3-A. Docker Compose로 실행 (권장)

```bash
# GPU가 있는 서버에서
docker compose up --build

# 백그라운드 실행
docker compose up -d --build
```

- 프론트엔드: http://서버IP:5173
- API 문서: http://서버IP:8000/docs

### 3-B. 직접 실행

```bash
# ── 백엔드 ──
cd backend

# PyTorch CUDA 버전 설치 (CUDA 12.1 기준)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 나머지 의존성
pip install -r requirements.txt

# 서버 실행
python main.py
```

```bash
# ── 프론트엔드 ── (별도 터미널)
cd frontend
npm install
npm run dev
```

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
| `GET` | `/api/health` | 서버/GPU 상태 확인 |
| `POST` | `/api/generate` | 이미지 업로드 → 생성 시작 |
| `GET` | `/api/status/{job_id}` | 작업 진행 상태 조회 |
| `DELETE` | `/api/jobs/{job_id}` | 작업 및 파일 삭제 |
| `GET` | `/docs` | Swagger UI API 문서 |

---

## 🖥️ GPU 요구사항

| VRAM | 설정 | 속도 |
|------|------|------|
| 8 GB | CPU offload 자동 활성화 | 느림 |
| 12 GB | decode_chunk_size=4 | 보통 |
| 16 GB+ | 기본 설정 | 빠름 |

---

## 🛠️ 환경 변수 (.env)

```env
HF_TOKEN=hf_your_token_here
SVD_MODEL=stabilityai/stable-video-diffusion-img2vid-xt
HF_HOME=./hf_cache
OUTPUT_DIR=./outputs
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173
```

---

## 📦 기술 스택

| 영역 | 기술 |
|------|------|
| AI 모델 | Stable Video Diffusion (SVD) img2vid-xt |
| 배경 제거 | rembg (u2net) |
| 딥러닝 | PyTorch 2.x + CUDA + diffusers |
| 백엔드 | FastAPI + uvicorn |
| 프론트엔드 | React 18 + Vite |
| 컨테이너 | Docker + NVIDIA CUDA |
