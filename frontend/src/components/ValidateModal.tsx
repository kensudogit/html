import React, { useState } from 'react'
import { editorApi } from '../services/editorApi'
import './Modal.css'

interface ValidateModalProps {
  isOpen: boolean
  onClose: () => void
  content: string
}

const ValidateModal: React.FC<ValidateModalProps> = ({ isOpen, onClose, content }) => {
  const [loading, setLoading] = useState<boolean>(false)
  const [errors, setErrors] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)

  const handleValidate = async () => {
    if (!content.trim()) {
      setError('コンテンツが空です')
      return
    }

    setLoading(true)
    setError(null)
    setErrors([])

    try {
      const response = await editorApi.validateHTML(content)
      if (response.success) {
        setErrors(response.errors || [])
        if (response.errors && response.errors.length === 0) {
          setError(null)
        }
      } else {
        setError(response.error || '検証に失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '検証に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => {
    if (isOpen && content) {
      handleValidate()
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>⚠️ 構文チェック</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {loading && <div className="loading">検証中...</div>}
          {error && <div className="error-message">{error}</div>}
          {errors.length === 0 && !loading && !error && (
            <div className="success-message">✅ エラーは見つかりませんでした</div>
          )}
          {errors.length > 0 && (
            <div className="errors-list">
              <h3>エラー・警告 ({errors.length}件)</h3>
              <ul>
                {errors.map((err, index) => (
                  <li key={index} className="error-item">
                    <strong>{err.type || 'エラー'}:</strong> {err.message || err.description || JSON.stringify(err)}
                    {err.line && <span className="error-line"> (行: {err.line})</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-primary" onClick={handleValidate} disabled={loading}>
            再検証
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            閉じる
          </button>
        </div>
      </div>
    </div>
  )
}

export default ValidateModal
