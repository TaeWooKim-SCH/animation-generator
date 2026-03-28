import styles from './OptionsPanel.module.css'

const FRAME_OPTIONS = [
  { value: 8,  label: '8', sub: '빠름' },
  { value: 12, label: '12', sub: '권장' },
  { value: 16, label: '16', sub: '고품질' },
]

const FPS_OPTIONS = [
  { value: 8,  label: '8 fps' },
  { value: 12, label: '12 fps' },
  { value: 24, label: '24 fps' },
]

export default function OptionsPanel({ options, onChange, disabled }) {
  const set = (key, value) => onChange({ ...options, [key]: value })

  return (
    <div className={styles.panel}>
      {/* ── 프레임 수 ── */}
      <div className={styles.group}>
        <label className="label">프레임 수</label>
        <div className={styles.segmented} role="group" aria-label="프레임 수 선택">
          {FRAME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              id={`frame-option-${opt.value}`}
              className={`${styles.segBtn} ${options.numFrames === opt.value ? styles.active : ''}`}
              onClick={() => set('numFrames', opt.value)}
              disabled={disabled}
              aria-pressed={options.numFrames === opt.value}
            >
              <span className={styles.segBtnMain}>{opt.label}</span>
              <span className={styles.segBtnSub}>{opt.sub}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── 모션 강도 ── */}
      <div className={styles.group}>
        <div className={styles.labelRow}>
          <label className="label" htmlFor="motion-slider">모션 강도</label>
          <span className={styles.value}>{options.motionStrength}</span>
        </div>
        <div className={styles.sliderWrapper}>
          <input
            id="motion-slider"
            type="range"
            min={50}
            max={255}
            step={1}
            value={options.motionStrength}
            onChange={(e) => set('motionStrength', Number(e.target.value))}
            disabled={disabled}
            className={styles.slider}
          />
          <div className={styles.sliderTicks}>
            <span>낮음</span>
            <span>폭발 추천 (127+)</span>
            <span>최대</span>
          </div>
        </div>
      </div>

      {/* ── FPS ── */}
      <div className={styles.group}>
        <label className="label">FPS</label>
        <div className={styles.segmented} role="group" aria-label="FPS 선택">
          {FPS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              id={`fps-option-${opt.value}`}
              className={`${styles.segBtn} ${options.fps === opt.value ? styles.active : ''}`}
              onClick={() => set('fps', opt.value)}
              disabled={disabled}
              aria-pressed={options.fps === opt.value}
            >
              <span className={styles.segBtnMain}>{opt.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── AI 배경 제거 ── */}
      <div className={styles.group}>
        <label className="label">배경 처리</label>
        <button
          id="rembg-toggle"
          className={`${styles.toggle} ${options.useRembg ? styles.toggleOn : ''}`}
          onClick={() => set('useRembg', !options.useRembg)}
          disabled={disabled}
          role="switch"
          aria-checked={options.useRembg}
        >
          <div className={styles.toggleTrack}>
            <div className={styles.toggleThumb} />
          </div>
          <div className={styles.toggleLabel}>
            <span className={styles.toggleTitle}>
              {options.useRembg ? 'AI 배경 제거 ON' : '원본 배경 유지'}
            </span>
            <span className={styles.toggleDesc}>
              {options.useRembg
                ? 'rembg로 배경 자동 제거 (권장)'
                : '검은 배경이면 밝기 기반 알파 처리'}
            </span>
          </div>
        </button>
      </div>

      {/* ── 스프라이트 시트 정보 ── */}
      <div className={styles.infoBox}>
        <div className={styles.infoRow}>
          <span className={styles.infoLabel}>예상 시트 크기</span>
          <span className={styles.infoVal}>
            {options.numFrames <= 8 ? '2048 × 1024' :
             options.numFrames <= 12 ? '2048 × 1536' : '2048 × 2048'}
          </span>
        </div>
        <div className={styles.infoRow}>
          <span className={styles.infoLabel}>Unity 슬라이싱</span>
          <span className={styles.infoVal}>Grid by Cell Size (512, 512)</span>
        </div>
        <div className={styles.infoRow}>
          <span className={styles.infoLabel}>셀 크기</span>
          <span className={styles.infoVal}>512 × 512 px</span>
        </div>
      </div>
    </div>
  )
}
