import React, { useEffect, useState } from 'react'
import { editorApi } from '../services/editorApi'
import './Modal.css'

interface StructureModalProps {
  isOpen: boolean
  onClose: () => void
}

const StructureModal: React.FC<StructureModalProps> = ({ isOpen, onClose }) => {
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<any>(null)

  useEffect(() => {
    if (isOpen) {
      loadStructure()
    }
  }, [isOpen])

  const loadStructure = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await editorApi.getStructure()
      if (response.success && response.info) {
        setInfo(response.info)
      } else {
        setError(response.error || '構造情報の取得に失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '構造情報の取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📊 構造情報</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {loading && <div className="loading">読み込み中...</div>}
          {error && <div className="error-message">{error}</div>}
          {info && (
            <div className="structure-info">
              <p><strong>タイトル:</strong> {info.title || '(なし)'}</p>
              <p><strong>リンク数:</strong> {info.links_count || 0}</p>
              <p><strong>画像数:</strong> {info.images_count || 0}</p>
              <p><strong>スクリプト数:</strong> {info.scripts_count || 0}</p>
              <p><strong>スタイルシート数:</strong> {info.stylesheets_count || 0}</p>
              <p><strong>フォーム数:</strong> {info.forms_count || 0}</p>
              {info.meta_tags && Object.keys(info.meta_tags).length > 0 && (
                <div>
                  <p><strong>メタタグ:</strong></p>
                  <ul>
                    {Object.entries(info.meta_tags).map(([name, content]) => (
                      <li key={name}>
                        {name}: {String(content).substring(0, 50)}
                        {String(content).length > 50 ? '...' : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StructureModal
