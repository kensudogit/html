import React from 'react'
import type { ComparisonFile } from '../types'
import './ComparisonFileList.css'

interface ComparisonFileListProps {
  files: ComparisonFile[]
  selectedFiles: Set<number>
  onToggleFile: (index: number) => void
  onSelectAll: (select: boolean) => void
  onRemoveFile: (index: number) => void
}

const ComparisonFileList: React.FC<ComparisonFileListProps> = ({
  files,
  selectedFiles,
  onToggleFile,
  onSelectAll,
  onRemoveFile,
}) => {
  if (files.length === 0) {
    return (
      <div className="comparison-file-list">
        <p className="empty-message">ディレクトリを指定してファイルを読み込んでください</p>
      </div>
    )
  }

  return (
    <div className="comparison-file-list">
      <div className="file-list-header">
        <strong>読み込み済みファイル ({files.length}/27)</strong>
        <div className="file-list-actions">
          <button
            className="btn-select-all"
            onClick={() => onSelectAll(true)}
          >
            すべて選択
          </button>
          <button
            className="btn-deselect-all"
            onClick={() => onSelectAll(false)}
          >
            すべて解除
          </button>
        </div>
      </div>
      <div className="file-list-content">
        {files.map((file, index) => (
          <div key={index} className="file-list-item">
            <input
              type="checkbox"
              id={`file_${index}`}
              checked={selectedFiles.has(index)}
              onChange={() => onToggleFile(index)}
              className="file-checkbox"
            />
            <label htmlFor={`file_${index}`} className="file-label">
              <span className="file-name">{file.name}</span>
              <span className={`file-type-badge file-type-${file.type}`}>
                {file.type === 'html' ? 'HTML' : file.type === 'css' ? 'CSS' : 'OTHER'}
              </span>
            </label>
            <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
            <button
              className="btn-remove"
              onClick={() => onRemoveFile(index)}
              title="削除"
            >
              削除
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ComparisonFileList
