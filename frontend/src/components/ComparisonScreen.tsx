import React, { useState, useEffect, useRef } from 'react'
import type { ComparisonFile } from '../types'
import './ComparisonScreen.css'

interface ComparisonScreenProps {
  file: ComparisonFile
  content: string
  isLoading: boolean
  error?: string
  comparisonMode: boolean
  htmlDiffs?: number
  cssDiffs?: number
}

const ComparisonScreen: React.FC<ComparisonScreenProps> = ({
  file,
  content,
  isLoading,
  error,
  comparisonMode,
  htmlDiffs,
  cssDiffs,
}) => {
  const [selected, setSelected] = useState<boolean>(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    if (content && iframeRef.current) {
      const blob = new Blob([content], { type: 'text/html' })
      const url = URL.createObjectURL(blob)
      iframeRef.current.src = url

      return () => {
        URL.revokeObjectURL(url)
      }
    }
  }, [content])

  const handleEdit = () => {
    // 新しいタブでエディタを開く
    window.open(`/?file=${encodeURIComponent(file.path)}`, '_blank')
  }

  const handleDownload = () => {
    if (!content) return

    const blob = new Blob([content], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleAnalyze = () => {
    // 分析機能（実装予定）
    alert(`${file.name}の分析機能は実装中です`)
  }

  return (
    <div
      className={`comparison-screen ${selected ? 'selected' : ''} ${comparisonMode ? 'comparison-mode' : ''}`}
      onClick={() => setSelected(!selected)}
    >
      <div className="comparison-screen-header">
        <div className="screen-title-group">
          <span className="screen-title">{file.name}</span>
          <span className={`screen-type-badge screen-type-${file.type}`}>
            {file.type === 'html' ? 'HTML' : file.type === 'css' ? 'CSS' : 'OTHER'}
          </span>
        </div>
        <div className="screen-actions" onClick={(e) => e.stopPropagation()}>
          <button
            className="screen-action-btn"
            onClick={handleEdit}
            title="編集"
          >
            ✏️
          </button>
          <button
            className="screen-action-btn"
            onClick={handleDownload}
            title="ダウンロード"
            disabled={!content}
          >
            ⬇️
          </button>
          <button
            className="screen-action-btn"
            onClick={handleAnalyze}
            title="分析"
          >
            📊
          </button>
        </div>
      </div>
      <div className="comparison-screen-preview">
        {isLoading ? (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <p>読み込み中...</p>
          </div>
        ) : error ? (
          <div className="error-preview">
            <p className="error-text">⚠️ {error}</p>
          </div>
        ) : content ? (
          file.type === 'css' ? (
            <div className="css-preview">
              <pre className="css-content">{content}</pre>
            </div>
          ) : (
            <iframe
              ref={iframeRef}
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
              className="comparison-iframe"
              title={`${file.name}のプレビュー`}
            />
          )
        ) : (
          <div className="empty-preview">
            <p>プレビューを読み込めませんでした</p>
          </div>
        )}
      </div>
      <div className="comparison-screen-info">
        <div className="file-info-left">
          <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
          {file.relatedFiles && file.relatedFiles.length > 0 && (
            <span className="related-files-count">
              {file.relatedFiles.length}個の関連ファイル
            </span>
          )}
        </div>
        <div className="diff-badges">
          {(htmlDiffs !== undefined && htmlDiffs > 0) && (
            <span className="diff-badge html-diff" title={`HTML差分: ${htmlDiffs}箇所`}>
              HTML: {htmlDiffs}
            </span>
          )}
          {(cssDiffs !== undefined && cssDiffs > 0) && (
            <span className="diff-badge css-diff" title={`CSS差分: ${cssDiffs}箇所`}>
              CSS: {cssDiffs}
            </span>
          )}
          <span className={`diff-badge ${error ? 'error' : content ? 'loaded' : 'loading'}`}>
            {error ? 'エラー' : content ? '読み込み済み' : '読み込み中...'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default ComparisonScreen
