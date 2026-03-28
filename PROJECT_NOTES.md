# AnimGen 프로젝트 정리 문서

> 작성일: 2026-03-28  
> 프로젝트: 2D 이펙트 이미지 → Unity 스프라이트 시트 애니메이션 자동 생성기

---

## 1. 프로젝트 개요

### 목표

게임 에디터(Unity)에서 사용할 수 있는 **AI 기반 애니메이션 생성기**를 만드는 것.  
1단계로 **2D 폭발 이펙트 이미지 한 장**을 입력받아, Unity에서 바로 사용 가능한 **스프라이트 시트 PNG**와 **메타데이터 JSON**을 자동으로 생성하는 파이프라인을 구현.

### 핵심 플로우

```
폭발 이펙트 이미지 (PNG 1장)
        ↓
  [배경 제거 · rembg]
        ↓
  [SVD img2vid 추론]
  (Stable Video Diffusion)
        ↓
  [프레임 샘플링 · 후처리]
  8 / 12 / 16 프레임 RGBA
        ↓
  [스프라이트 시트 조립]
  4×N 그리드 PNG
        ↓
Unity: Sprite Editor → Grid by Cell Size (512, 512)
       → Animation Clip 자동 생성
```

---

## 2. 기획 과정에서 결정한 사항들

### Q&A 의사결정 로그

| 질문 | 결정 | 이유 |
|------|------|------|
| 실행 환경 | **로컬 GPU 서버 (Ubuntu)** | 클라우드 API 비용 없이 자체 서버 운영 |
| 1단계 출력 형식 | **스프라이트 시트 PNG만** | `.anim` 파일 생성은 2단계로 미룸 |
| 우선 이펙트 | **폭발 (Explosion)** | 가장 일반적인 게임 이펙트 |
| 프레임 해상도 | **512 × 512 px** | 게임 이펙트 표준급 해상도 |
| 프레임 수 | **8 ~ 16장** | 선택 가능 (8 / 12 / 16) |
| 프론트엔드 | **React + Vite** | 사용자 요청 |
| GitHub 설정 | **포함** | `.gitignore`, `.gitattributes`, 초기 커밋 |

### AI 모델 선택 근거

후보 3가지를 검토:

| 모델 | 특징 | 채택 여부 |
|------|------|-----------|
| Stable Video Diffusion (SVD) | 이미지 1장 → 영상 직접 생성 | ✅ **채택** |
| AnimateDiff + ControlNet | 프롬프트+이미지 기반, 제어 유연 | 보류 |
| img2img 반복 | 가벼움, 프레임 일관성 부족 | 보류 |

**SVD를 선택한 결정적 이유**:  
"이미지 1장 → 애니메이션" 요구사항에 가장 직접적으로 대응하는 구조이며,  
`motion_bucket_id` 파라미터로 폭발의 모션 강도를 직접 제어할 수 있음.

---

## 3. 최종 기술 스택

| 레이어 | 기술 | 버전/비고 |
|--------|------|-----------|
| **AI 모델** | Stable Video Diffusion img2vid-xt | stabilityai/stable-video-diffusion-img2vid-xt |
| **모델 라이브러리** | 🤗 diffusers | 0.27.2 |
| **딥러닝** | PyTorch + CUDA | 2.x, CUDA 12.1 |
| **가속** | accelerate, xFormers | VRAM 효율 최적화 |
| **배경 제거** | rembg (u2net) | 2.0.56 |
| **이미지 처리** | Pillow, OpenCV, imageio | - |
| **백엔드 API** | FastAPI + uvicorn | 0.109.2 |
| **프론트엔드** | React 18 + Vite 6 | CSS Modules |
| **컨테이너** | Docker + docker-compose | NVIDIA GPU 지원 |

---

## 4. 프로젝트 구조

```
animation-generator/
│
├── backend/
│   ├── models/
│   │   ├── preprocessor.py          # 전처리: 배경 제거, 리사이즈
│   │   ├── frame_generator.py       # SVD 파이프라인 (핵심 AI)
│   │   └── sprite_sheet_builder.py  # 스프라이트 시트 조립 + GIF 생성
│   │
│   ├── server.py                    # FastAPI 서버 (API + 작업 큐)
│   ├── main.py                      # uvicorn 진입점
│   ├── requirements.txt             # Python 의존성
│   ├── .env.example                 # 환경 변수 템플릿
│   └── Dockerfile                   # CUDA 기반 컨테이너
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # 메인 앱 (상태 관리, 레이아웃)
│   │   ├── App.module.css
│   │   ├── index.css                # 글로벌 디자인 시스템
│   │   ├── main.jsx                 # React 진입점
│   │   └── components/
│   │       ├── UploadZone.jsx       # 드래그&드롭 업로드
│   │       ├── UploadZone.module.css
│   │       ├── OptionsPanel.jsx     # 옵션 설정 UI
│   │       ├── OptionsPanel.module.css
│   │       ├── ProgressBar.jsx      # 5단계 진행률 표시
│   │       ├── ProgressBar.module.css
│   │       ├── ResultPanel.jsx      # 결과 + 다운로드 + Unity 가이드
│   │       └── ResultPanel.module.css
│   │
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
│
├── docker-compose.yml               # GPU 서버 통합 실행
├── .gitignore
├── .gitattributes                   # LF 줄바꿈 통일 (Ubuntu 서버 대응)
└── README.md
```

---

## 5. 각 모듈 상세 설명

### 5-1. `preprocessor.py`

| 함수 | 역할 |
|------|------|
| `remove_background(image)` | rembg AI로 배경 제거 → RGBA 반환 |
| `extract_alpha_by_luminance(image, threshold=15)` | 밝기 기반 알파 생성 (검은 배경 이펙트용) |
| `prepare_for_svd(image, 1024, 576)` | SVD 입력 규격에 맞게 center-pad + RGB 변환 |
| `center_crop_and_resize(image, 512)` | 생성된 프레임을 512×512로 center-crop |
| `validate_input_image(image)` | 크기 유효성 검사 |

**설계 포인트**: SVD 모델은 `1024×576` 입력을 요구하므로, 512×512 이펙트 이미지를 center-pad로 배치 후 출력 프레임을 다시 center-crop하는 방식으로 원본 비율을 보존.

---

### 5-2. `frame_generator.py`

**FrameGenerator 클래스**의 핵심 동작:

```
1. 최초 generate() 호출 시 SVD 모델 lazy load (HuggingFace)
2. VRAM 자동 감지:
   - 16GB+: 기본 설정
   - 12GB:  decode_chunk_size=4
   - 8GB:   CPU offload 활성화
3. xFormers 메모리 효율 어텐션 자동 활성화
4. SVD 추론: model_max_frames (14 or 25) 생성
5. np.linspace로 N개 균등 샘플링
6. 각 프레임: center_crop → luminance alpha 적용
```

**주요 파라미터**:

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `num_frames` | 8 | 출력 프레임 수 |
| `motion_bucket_id` | 127 | 모션 강도 (폭발: 127~200 권장) |
| `fps` | 12 | 메타데이터에 반영되는 FPS |
| `noise_aug_strength` | 0.02 | 낮을수록 원본에 충실 |
| `seed` | 42 | 재현성 시드 |

---

### 5-3. `sprite_sheet_builder.py`

| 함수 | 역할 |
|------|------|
| `build_sprite_sheet(frames, cols=4)` | 4×N 그리드 PNG + 메타데이터 JSON 생성 |
| `create_preview_gif(frames, fps=12)` | 미리보기용 GIF 생성 (256×256) |
| `create_preview_apng(frames, fps=12)` | 알파 보존 APNG (실패 시 GIF로 대체) |

**Unity 메타데이터 JSON 구조**:
```json
{
  "frame_width": 512,
  "frame_height": 512,
  "num_frames": 8,
  "cols": 4,
  "rows": 2,
  "sheet_width": 2048,
  "sheet_height": 1024,
  "fps": 12,
  "unity": {
    "import_settings": {
      "sprite_mode": "Multiple",
      "slice_type": "GridByCellSize",
      "cell_width": 512,
      "cell_height": 512
    }
  },
  "frames": [
    { "index": 0, "x": 0, "y": 0, "w": 512, "h": 512, "pivot_x": 0.5, "pivot_y": 0.5 }
  ]
}
```

---

### 5-4. `server.py` (FastAPI)

**작업 처리 방식**: 비동기 Job 큐

```
POST /api/generate
    └─ FormData 수신 → job_id 생성 → ThreadPoolExecutor 백그라운드 실행
                                              ↓
GET /api/status/{job_id}  ←──── 클라이언트 2초 폴링
                                              ↓
                                         상태 업데이트 (progress %)
                                              ↓
                                    status: "done" → result 반환
```

**보안/안정성**:
- max_workers=1 (GPU 동시 사용 방지)
- 파일 크기 20MB 제한
- CORS 허용 출처 환경 변수로 제어

**전체 엔드포인트**:

| Method | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/health` | GPU 정보 + 서버 상태 |
| `POST` | `/api/generate` | 이미지 업로드 → 생성 시작 |
| `GET` | `/api/status/{job_id}` | 진행률 폴링 |
| `DELETE` | `/api/jobs/{job_id}` | 작업 + 파일 삭제 |
| `GET` | `/api/jobs` | 전체 작업 목록 |
| `GET` | `/docs` | Swagger UI 자동 문서 |
| `GET` | `/outputs/**` | 생성 파일 정적 서빙 |

---

### 5-5. React 프론트엔드

**앱 상태 흐름**:
```
idle → generating → done
              ↘ error
```

**컴포넌트 트리**:
```
App (상태 관리, 폴링 로직)
├── Header    (로고, GPU 뱃지)
├── LeftPanel (glass-card)
│   ├── UploadZone   (drag&drop, 미리보기)
│   ├── OptionsPanel (segmented 버튼, 슬라이더, 토글)
│   └── GenerateButton
└── RightPanel (glass-card)
    ├── [idle]      IdleState (안내 + 힌트)
    ├── [generating] ProgressBar (5단계 스텝)
    ├── [done]      ResultPanel (GIF + 시트 + 다운로드)
    └── [error]     ErrorState
```

**디자인 시스템** (`index.css`):

| 토큰 | 값 | 용도 |
|------|----|------|
| `--bg-deep` | `#06060e` | 최하단 배경 |
| `--orange` | `#ff6b35` | 주 강조색 |
| `--red` | `#e11d48` | 그라디언트 중간 |
| `--purple` | `#7c3aed` | 보조 강조색 |
| `--grad-main` | orange→red→purple | 버튼, 바 그라디언트 |
| `--font-head` | Space Grotesk | 제목 폰트 |
| `--font-sans` | Inter | 본문 폰트 |

---

## 6. 스프라이트 시트 출력 규격

| 프레임 수 | 그리드 | 시트 해상도 | 파일 크기 예상 |
|-----------|--------|-------------|----------------|
| 8 frames  | 4 × 2  | 2048 × 1024 | ~5~15 MB |
| 12 frames | 4 × 3  | 2048 × 1536 | ~8~22 MB |
| 16 frames | 4 × 4  | 2048 × 2048 | ~10~30 MB |

모든 시트는 **알파채널 포함 RGBA PNG**.

---

## 7. GPU VRAM별 실행 설정

| VRAM | 자동 적용 설정 | 추론 속도 |
|------|---------------|-----------|
| 8 GB | CPU offload ON, decode_chunk_size=2 | 느림 (~5~10분) |
| 12 GB | decode_chunk_size=4 | 보통 (~2~4분) |
| 16 GB | decode_chunk_size=6 | 빠름 (~1~2분) |
| 24 GB+ | decode_chunk_size=8 | 매우 빠름 (<1분) |

---

## 8. 실행 방법 요약

### A. Docker Compose (권장)

```bash
# 1. 레포 클론
git clone https://github.com/your-username/animation-generator.git
cd animation-generator

# 2. 환경 변수 설정
cp backend/.env.example backend/.env
# HF_TOKEN 입력 필수

# 3. 실행
docker compose up --build -d

# 접속
# 프론트엔드: http://서버IP:5173
# API 문서:  http://서버IP:8000/docs
```

### B. 직접 실행

```bash
# ── 백엔드 ──
cd backend
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
cp .env.example .env  # HF_TOKEN 설정
python main.py

# ── 프론트엔드 (별도 터미널) ──
cd frontend
npm install
npm run dev
```

---

## 9. HuggingFace 설정 체크리스트

- [ ] https://huggingface.co 계정 생성
- [ ] https://huggingface.co/settings/tokens 에서 **Read 권한** 토큰 발급
- [ ] https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt 에서 **이용약관 동의**
- [ ] `backend/.env`에 `HF_TOKEN=hf_xxx...` 입력

---

## 10. Unity 임포트 방법

1. `sprite_sheet.png` → Unity `Assets/` 폴더에 드래그
2. Inspector → **Texture Type**: `Sprite (2D and UI)`
3. **Sprite Mode**: `Multiple`
4. **Sprite Editor** 클릭 → **Slice** → `Grid By Cell Size`
5. Cell Size: `512 × 512` 입력 → **Slice** 실행
6. **Apply** 클릭
7. 생성된 Sprite들을 선택 → **Animator**에 드래그 → Animation Clip 자동 생성

---

## 11. 로드맵 (향후 개발)

### Phase 2 (Unity 플러그인)
- Unity Editor C# 확장 (`AnimationGeneratorImporter.cs`)
- 에디터 내에서 직접 API 호출 → 결과물 `Assets/`에 자동 저장
- `.anim` 파일 자동 생성

### Phase 3 (품질 향상)
- 폭발 이외 이펙트 추가: 불꽃, 마법, 물, 연기, 번개
- 루프 애니메이션 개선 (첫/마지막 프레임 블렌딩)
- 게임 이펙트 특화 LoRA 파인튜닝
- 배치 생성 (여러 이미지 동시 처리)
- RMBG-2.0 도입 (배경 제거 품질 향상)

---

## 12. 주요 파일 링크

| 파일 | 역할 |
|------|------|
| [frame_generator.py](backend/models/frame_generator.py) | SVD 추론 핵심 |
| [sprite_sheet_builder.py](backend/models/sprite_sheet_builder.py) | 시트 조립 |
| [preprocessor.py](backend/models/preprocessor.py) | 이미지 전처리 |
| [server.py](backend/server.py) | FastAPI 서버 |
| [App.jsx](frontend/src/App.jsx) | React 메인 |
| [index.css](frontend/src/index.css) | 디자인 시스템 |
| [docker-compose.yml](docker-compose.yml) | 배포 설정 |
| [README.md](README.md) | 사용자 가이드 |

---

## 13. 커밋 이력

| 커밋 | 메시지 |
|------|--------|
| `4fe721a` | feat: initial commit - AnimGen 2D effect to Unity sprite sheet generator |

---

*AnimGen · 2D Effect Animation Generator for Unity · Powered by Stable Video Diffusion*
