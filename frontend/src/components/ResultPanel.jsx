import { useState } from 'react'
import styles from './ResultPanel.module.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function DownloadButton({ href, label, icon, id }) {
  const [downloading, setDownloading] = useState(false)

  const handleClick = async () => {
    setDownloading(true)
    try {
      const res = await fetch(href)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = href.split('/').pop()
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('다운로드 실패:', e)
    } finally {
      setTimeout(() => setDownloading(false), 800)
    }
  }

  return (
    <button
      id={id}
      className={styles.downloadBtn}
      onClick={handleClick}
      disabled={downloading}
    >
      <span className={styles.downloadIcon}>{downloading ? '⏳' : icon}</span>
      <div className={styles.downloadLabel}>
        <span className={styles.downloadTitle}>{label}</span>
        <span className={styles.downloadSub}>{downloading ? '다운로드 중...' : '클릭하여 저장'}</span>
      </div>
      <svg className={styles.downloadArrow} width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 3v8M4 9l4 4 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </button>
  )
}

export default function ResultPanel({ result, onReset }) {
  if (!result) return null

  const sheetUrl  = `${API_BASE}${result.sprite_sheet_url}`
  const metaUrl   = `${API_BASE}${result.metadata_url}`
  const gifUrl    = `${API_BASE}${result.preview_gif_url}`

  return (
    <div className={`${styles.wrapper} animate-fade-up`}>
      {/* ── 헤더 ── */}
      <div className={styles.header}>
        <div className={styles.successBadge}>
          <span>✦</span> 생성 완료
        </div>
        <div className={styles.meta}>
          <span>{result.num_frames}프레임</span>
          <span>·</span>
          <span>{result.sheet_size}</span>
        </div>
      </div>

      {/* ── GIF 미리보기 ── */}
      <div className={styles.previewSection}>
        <p className="label">애니메이션 미리보기</p>
        <div className={styles.gifWrapper}>
          <img
            src={gifUrl}
            alt="생성된 폭발 애니메이션 미리보기 GIF"
            className={styles.gif}
          />
          <div className={styles.gifBadge}>GIF</div>
        </div>
      </div>

      {/* ── 스프라이트 시트 썸네일 ── */}
      <div className={styles.sheetSection}>
        <p className="label">스프라이트 시트</p>
        <div className={styles.sheetWrapper}>
          <img
            src={sheetUrl}
            alt="Unity용 스프라이트 시트"
            className={styles.sheetThumb}
          />
          <div className={styles.sheetOverlay}>
            <span>512 × 512 per cell</span>
          </div>
        </div>
      </div>

      {/* ── 다운로드 ── */}
      <div className={styles.downloads}>
        <p className="label">파일 다운로드</p>
        <DownloadButton
          id="download-sprite-sheet"
          href={sheetUrl}
          label="sprite_sheet.png"
          icon="🖼️"
        />
        <DownloadButton
          id="download-metadata"
          href={metaUrl}
          label="metadata.json"
          icon="📄"
        />
      </div>

      {/* ── Unity 사용 가이드 ── */}
      <details className={styles.guide}>
        <summary className={styles.guideSummary}>
          <span>🎮</span> Unity에서 사용하는 방법
        </summary>
        <ol className={styles.guideList}>
          <li><code>sprite_sheet.png</code>를 Unity <code>Assets/</code> 폴더에 드래그</li>
          <li>Inspector에서 <strong>Texture Type</strong> → <code>Sprite (2D and UI)</code></li>
          <li><strong>Sprite Mode</strong> → <code>Multiple</code></li>
          <li><strong>Sprite Editor</strong> 클릭 → <strong>Slice</strong> → <code>Grid By Cell Size</code></li>
          <li>Cell Size: <code>512 × 512</code> 입력 후 Slice 실행</li>
          <li>Sprites를 선택 후 Animator에 드래그 → Animation Clip 자동 생성</li>
        </ol>
      </details>

      {/* ── 다시 생성 ── */}
      <button id="reset-btn" className="btn-ghost" onClick={onReset} style={{ marginTop: 4 }}>
        ↩ 새 이미지로 다시 생성
      </button>
    </div>
  )
}
