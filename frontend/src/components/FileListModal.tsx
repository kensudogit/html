import React, { useEffect, useState } from 'react'
import { editorApi } from '../services/editorApi'
import './Modal.css'

interface FileListModalProps {
  isOpen: boolean
  onClose: () => void
  onSelectFile: (filename: string) => void
}

const FileListModal: React.FC<FileListModalProps> = ({ isOpen, onClose, onSelectFile }) => {
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [files, setFiles] = useState<Array<{ name: string; size: number }>>([])

  useEffect(() => {
    if (isOpen) {
      loadFiles()
    }
  }, [isOpen])

  const loadFiles = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await editorApi.getFiles()
      if (response.success && response.files) {
        setFiles(response.files)
      } else {
        setError(response.error || 'ファイル一覧の取得に失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ファイル一覧の取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  const handleFileClick = (filename: string) => {
    onSelectFile(filename)
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📁 ファイル一覧</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {loading && <div className="loading">読み込み中...</div>}
          {error && <div className="error-message">{error}</div>}
          {files.length === 0 && !loading && !error && (
            <div className="empty-message">ファイルが見つかりませんでした</div>
          )}
          {files.length > 0 && (
            <div className="file-list">
              <table className="file-table">
                <thead>
                  <tr>
                    <th>ファイル名</th>
                    <th>サイズ</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file, index) => (
                    <tr key={index}>
                      <td>{file.name}</td>
                      <td>{formatFileSize(file.size)}</td>
                      <td>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleFileClick(file.name)}
                        >
                          開く
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            閉じる
          </button>
        </div>
      </div>
    </div>
  )
}

export default FileListModal
