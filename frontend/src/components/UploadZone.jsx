import { useRef, useState, useCallback } from 'react'
import styles from './UploadZone.module.css'

const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp']
const MAX_SIZE_MB = 20

export default function UploadZone({ onImageSelected, imagePreview, disabled }) {
  const inputRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState('')

  const validate = (file) => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setError('PNG, JPG, WEBP 파일만 지원합니다')
      return false
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`파일 크기는 ${MAX_SIZE_MB}MB 이하여야 합니다`)
      return false
    }
    setError('')
    return true
  }

  const handleFile = useCallback((file) => {
    if (!file || !validate(file)) return
    const url = URL.createObjectURL(file)
    onImageSelected(file, url)
  }, [onImageSelected])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    if (disabled) return
    const file = e.dataTransfer.files?.[0]
    handleFile(file)
  }, [handleFile, disabled])

  const onDragOver = (e) => { e.preventDefault(); if (!disabled) setIsDragging(true) }
  const onDragLeave = () => setIsDragging(false)
  const onInputChange = (e) => handleFile(e.target.files?.[0])
  const onClick = () => { if (!disabled) inputRef.current?.click() }

  return (
    <div className={styles.wrapper}>
      <p className="label">입력 이미지</p>

      <div
        id="upload-zone"
        className={`${styles.zone} ${isDragging ? styles.dragging : ''} ${imagePreview ? styles.hasImage : ''} ${disabled ? styles.disabled : ''}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={onClick}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => e.key === 'Enter' && onClick()}
        aria-label="이미지 업로드 영역"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".png,.jpg,.jpeg,.webp"
          onChange={onInputChange}
          style={{ display: 'none' }}
          id="file-input"
        />

        {imagePreview ? (
          <div className={styles.preview}>
            <img src={imagePreview} alt="업로드된 이펙트 이미지" className={styles.previewImg} />
            <div className={styles.previewOverlay}>
              <span className={styles.changeBtn}>🔄 이미지 변경</span>
            </div>
          </div>
        ) : (
          <div className={styles.placeholder}>
            <div className={styles.icon}>
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                <circle cx="24" cy="24" r="23" stroke="url(#g1)" strokeWidth="1.5" strokeDasharray="4 3" />
                <path d="M24 32V20M18 26l6-6 6 6" stroke="url(#g2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <defs>
                  <linearGradient id="g1" x1="1" y1="1" x2="47" y2="47">
                    <stop stopColor="#ff6b35"/><stop offset="1" stopColor="#7c3aed"/>
                  </linearGradient>
                  <linearGradient id="g2" x1="18" y1="20" x2="30" y2="32">
                    <stop stopColor="#ff6b35"/><stop offset="1" stopColor="#7c3aed"/>
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <p className={styles.mainText}>이미지를 드래그하거나 클릭해 업로드</p>
            <p className={styles.subText}>PNG · JPG · WEBP · 최대 {MAX_SIZE_MB}MB</p>
            <p className={styles.hint}>💡 투명 배경 PNG 또는 검은 배경의 폭발 이펙트 권장</p>
          </div>
        )}
      </div>

      {error && (
        <p className={styles.error} role="alert">⚠ {error}</p>
      )}
    </div>
  )
}
