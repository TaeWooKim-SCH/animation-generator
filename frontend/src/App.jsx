import { useState, useEffect, useRef, useCallback } from 'react'
import UploadZone from './components/UploadZone'
import OptionsPanel from './components/OptionsPanel'
import ProgressBar from './components/ProgressBar'
import ResultPanel from './components/ResultPanel'
import styles from './App.module.css'

const API_BASE = import.meta.env.VITE_API_URL || ''
const POLL_INTERVAL_MS = 2000

const DEFAULT_OPTIONS = {
  numFrames: 8,
  motionStrength: 150,
  fps: 12,
  useRembg: true,
}

// ── 상태 정의 ──
// idle → uploading → generating → done | error

export default function App() {
  const [imageFile, setImageFile]     = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [options, setOptions]         = useState(DEFAULT_OPTIONS)
  const [appState, setAppState]       = useState('idle')   // idle|generating|done|error
  const [jobId, setJobId]             = useState(null)
  const [progress, setProgress]       = useState(0)
  const [message, setMessage]         = useState('')
  const [result, setResult]           = useState(null)
  const [errorMsg, setErrorMsg]       = useState('')
  const [gpuInfo, setGpuInfo]         = useState(null)

  const pollRef = useRef(null)

  // ── 서버 상태 확인 ──
  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then(r => r.json())
      .then(d => setGpuInfo(d.gpu))
      .catch(() => setGpuInfo(null))
  }, [])

  // ── 폴링 정리 ──
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => () => stopPolling(), [stopPolling])

  // ── 이미지 선택 ──
  const handleImageSelected = useCallback((file, previewUrl) => {
    setImageFile(file)
    setImagePreview(previewUrl)
    setAppState('idle')
    setResult(null)
    setErrorMsg('')
    setProgress(0)
  }, [])

  // ── 생성 시작 ──
  const handleGenerate = useCallback(async () => {
    if (!imageFile) return

    setAppState('generating')
    setProgress(0)
    setMessage('서버에 요청 중...')
    setErrorMsg('')
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('image', imageFile)
      formData.append('num_frames', options.numFrames)
      formData.append('motion_strength', options.motionStrength)
      formData.append('fps', options.fps)
      formData.append('use_rembg', options.useRembg)

      const res = await fetch(`${API_BASE}/api/generate`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '알 수 없는 오류' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const { job_id } = await res.json()
      setJobId(job_id)

      // 폴링 시작
      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_BASE}/api/status/${job_id}`)
          const data = await statusRes.json()

          setProgress(data.progress)
          setMessage(data.message)

          if (data.status === 'done') {
            stopPolling()
            setResult(data.result)
            setAppState('done')
          } else if (data.status === 'error') {
            stopPolling()
            setErrorMsg(data.error || '생성 중 오류 발생')
            setAppState('error')
          }
        } catch (e) {
          stopPolling()
          setErrorMsg(`상태 확인 실패: ${e.message}`)
          setAppState('error')
        }
      }, POLL_INTERVAL_MS)

    } catch (e) {
      setErrorMsg(e.message)
      setAppState('error')
    }
  }, [imageFile, options, stopPolling])

  // ── 리셋 ──
  const handleReset = useCallback(() => {
    stopPolling()
    setAppState('idle')
    setImageFile(null)
    setImagePreview(null)
    setResult(null)
    setJobId(null)
    setProgress(0)
    setMessage('')
    setErrorMsg('')
  }, [stopPolling])

  const isGenerating = appState === 'generating'
  const isDone       = appState === 'done'
  const isError      = appState === 'error'
  const canGenerate  = !!imageFile && !isGenerating

  return (
    <div className={styles.app}>
      {/* ════ 헤더 ════ */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.logo}>
            <span className={styles.logoEmoji}>💥</span>
            <span className={`${styles.logoText} gradient-text`}>AnimGen</span>
          </div>
          <div className={styles.headerRight}>
            {gpuInfo && typeof gpuInfo === 'object' ? (
              <div className={`badge badge-orange`} id="gpu-badge">
                <span>🖥️</span>
                {gpuInfo.name} · {gpuInfo.vram_gb}GB
              </div>
            ) : (
              <div className="badge badge-orange" id="gpu-badge">🎮 AI 서버</div>
            )}
          </div>
        </div>
        <p className={styles.tagline}>
          폭발 이펙트 이미지 한 장 → &nbsp;
          <strong>Unity 스프라이트 시트</strong> 자동 생성
        </p>
      </header>

      {/* ════ 메인 콘텐츠 ════ */}
      <main className={styles.main}>
        <div className={styles.grid}>
          {/* ── 왼쪽: 업로드 + 옵션 ── */}
          <section className={`glass-card ${styles.leftPanel}`}>
            <UploadZone
              onImageSelected={handleImageSelected}
              imagePreview={imagePreview}
              disabled={isGenerating}
            />

            <hr className="divider" />

            <OptionsPanel
              options={options}
              onChange={setOptions}
              disabled={isGenerating}
            />

            <button
              id="generate-btn"
              className={`btn-primary ${styles.generateBtn}`}
              onClick={handleGenerate}
              disabled={!canGenerate}
            >
              {isGenerating ? (
                <>
                  <div className="spinner" />
                  생성 중...
                </>
              ) : (
                <>
                  <span>✦</span>
                  애니메이션 생성
                </>
              )}
            </button>
          </section>

          {/* ── 오른쪽: 결과/진행 ── */}
          <section className={`glass-card ${styles.rightPanel}`}>
            {/* 대기 상태 */}
            {appState === 'idle' && !isDone && (
              <div className={styles.idleState}>
                <div className={styles.idleIcon}>
                  <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                    <circle cx="32" cy="32" r="31" stroke="url(#ig1)" strokeWidth="1" strokeDasharray="5 4" opacity="0.4"/>
                    <circle cx="32" cy="32" r="20" stroke="url(#ig2)" strokeWidth="1" strokeDasharray="3 3" opacity="0.3"/>
                    <text x="32" y="38" textAnchor="middle" fontSize="24">💥</text>
                    <defs>
                      <linearGradient id="ig1" x1="1" y1="1" x2="63" y2="63"><stop stopColor="#ff6b35"/><stop offset="1" stopColor="#7c3aed"/></linearGradient>
                      <linearGradient id="ig2" x1="12" y1="12" x2="52" y2="52"><stop stopColor="#e11d48"/><stop offset="1" stopColor="#7c3aed"/></linearGradient>
                    </defs>
                  </svg>
                </div>
                <h2 className={styles.idleTitle}>생성 준비 완료</h2>
                <p className={styles.idleDesc}>
                  폭발 이펙트 이미지를 업로드하고<br/>
                  옵션을 설정한 뒤 생성 버튼을 누르세요
                </p>
                <div className={styles.idleHints}>
                  {[
                    ['512×512 PNG', '최적 해상도'],
                    ['투명/검정 배경', '알파 자동 처리'],
                    ['무한 루프 지원', 'Unity Animator'],
                  ].map(([title, sub]) => (
                    <div key={title} className={styles.idleHint}>
                      <span className={styles.idleHintTitle}>{title}</span>
                      <span className={styles.idleHintSub}>{sub}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 생성 중 */}
            {isGenerating && (
              <div className={`${styles.generatingState} animate-fade-in`}>
                <h2 className={styles.sectionTitle}>
                  <span className={styles.pulse}>●</span> 생성 중
                </h2>
                <ProgressBar
                  progress={progress}
                  message={message}
                  status="running"
                />
              </div>
            )}

            {/* 오류 */}
            {isError && (
              <div className={`${styles.errorState} animate-fade-up`}>
                <div className={styles.errorIcon}>⚠️</div>
                <h2 className={styles.errorTitle}>생성 실패</h2>
                <p className={styles.errorMsg}>{errorMsg}</p>
                <button id="retry-btn" className="btn-ghost" onClick={handleReset}>
                  ↩ 처음으로
                </button>
              </div>
            )}

            {/* 완료 */}
            {isDone && (
              <ResultPanel result={result} onReset={handleReset} />
            )}
          </section>
        </div>
      </main>

      {/* ════ 푸터 ════ */}
      <footer className={styles.footer}>
        <p>AnimGen · 2D Effect Animation Generator for Unity · SVD img2vid powered</p>
      </footer>
    </div>
  )
}
