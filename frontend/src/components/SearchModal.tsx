import React, { useState } from 'react'
import './Modal.css'

interface SearchModalProps {
  isOpen: boolean
  onClose: () => void
  content: string
  onReplace: (searchText: string, replaceText: string) => void
}

const SearchModal: React.FC<SearchModalProps> = ({ isOpen, onClose, content, onReplace }) => {
  const [searchText, setSearchText] = useState<string>('')
  const [replaceText, setReplaceText] = useState<string>('')
  const [matchCount, setMatchCount] = useState<number>(0)

  React.useEffect(() => {
    if (isOpen && searchText) {
      const regex = new RegExp(searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
      const matches = content.match(regex)
      setMatchCount(matches ? matches.length : 0)
    } else {
      setMatchCount(0)
    }
  }, [searchText, content, isOpen])

  const handleReplace = () => {
    if (!searchText.trim()) {
      alert('検索文字列を入力してください')
      return
    }
    onReplace(searchText, replaceText)
    setSearchText('')
    setReplaceText('')
  }

  const handleReplaceAll = () => {
    if (!searchText.trim()) {
      alert('検索文字列を入力してください')
      return
    }
    onReplace(searchText, replaceText)
    setSearchText('')
    setReplaceText('')
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🔍 検索・置換</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="search-form">
            <div className="form-group">
              <label>検索:</label>
              <input
                type="text"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="検索文字列を入力"
                className="form-input"
              />
              {matchCount > 0 && (
                <span className="match-count">{matchCount}件見つかりました</span>
              )}
            </div>
            <div className="form-group">
              <label>置換:</label>
              <input
                type="text"
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
                placeholder="置換後の文字列を入力"
                className="form-input"
              />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-primary" onClick={handleReplace}>
            置換
          </button>
          <button className="btn btn-warning" onClick={handleReplaceAll}>
            すべて置換
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            閉じる
          </button>
        </div>
      </div>
    </div>
  )
}

export default SearchModal
