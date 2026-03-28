import styles from './ProgressBar.module.css'

const STEPS = [
  { min: 0,  max: 15,  label: '모델 로딩', icon: '🧠' },
  { min: 15, max: 25,  label: '이미지 전처리', icon: '🖼️' },
  { min: 25, max: 75,  label: 'AI 프레임 생성 (SVD)', icon: '✨' },
  { min: 75, max: 95,  label: '후처리', icon: '🎨' },
  { min: 95, max: 100, label: '스프라이트 시트 조립', icon: '📦' },
]

export default function ProgressBar({ progress, message, status }) {
  const currentStep = STEPS.findIndex(s => progress >= s.min && progress < s.max)
  const activeStep = currentStep === -1 ? STEPS.length - 1 : currentStep

  return (
    <div className={styles.wrapper} role="status" aria-live="polite">
      {/* 프로그레스 바 */}
      <div className={styles.barContainer}>
        <div
          className={`${styles.bar} ${status === 'done' ? styles.done : ''}`}
          style={{ width: `${Math.max(progress, 2)}%` }}
        />
        <div className={styles.barGlow} style={{ left: `${Math.max(progress, 2)}%` }} />
      </div>

      {/* 퍼센트 & 메시지 */}
      <div className={styles.info}>
        <span className={styles.percent}>{progress}%</span>
        <span className={styles.message}>{message}</span>
      </div>

      {/* 스텝 인디케이터 */}
      <div className={styles.steps}>
        {STEPS.map((step, i) => {
          const isDone    = progress >= step.max
          const isActive  = i === activeStep
          const isPending = progress < step.min
          return (
            <div
              key={i}
              className={`${styles.step} ${isDone ? styles.stepDone : ''} ${isActive ? styles.stepActive : ''} ${isPending ? styles.stepPending : ''}`}
            >
              <div className={styles.stepIcon}>{step.icon}</div>
              <span className={styles.stepLabel}>{step.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
