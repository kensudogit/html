import React, { useState } from 'react'
import { editorApi } from '../services/editorApi'
import './Modal.css'

interface SearchModalProps {
  isOpen: boolean
  onClose: () => void
  content: string
  onReplace: (searchText: string, replaceText: string) => void
  onSearch?: (searchText: string) => void
  filename?: string | null
}

const SearchModal: React.FC<SearchModalProps> = ({ isOpen, onClose, content, onReplace, onSearch, filename }) => {
  const [searchText, setSearchText] = useState<string>('')
  const [replaceText, setReplaceText] = useState<string>('')
  const [matchCount, setMatchCount] = useState<number>(0)
  const [currentMatchIndex, setCurrentMatchIndex] = useState<number>(-1)
  const [matches, setMatches] = useState<number[]>([])
  const [searchType, setSearchType] = useState<'html' | 'excel'>('html')
  const [folderPath, setFolderPath] = useState<string>('')
  const [excelResults, setExcelResults] = useState<any[]>([])
  const [loading, setLoading] = useState<boolean>(false)

  React.useEffect(() => {
    if (isOpen && searchText && searchType === 'html') {
      const allMatches = []
      let match
      const regexGlobal = new RegExp(searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
      while ((match = regexGlobal.exec(content)) !== null) {
        allMatches.push(match.index)
      }
      setMatches(allMatches)
      setMatchCount(allMatches.length)
      setCurrentMatchIndex(-1)
    } else {
      setMatchCount(0)
      setMatches([])
      setCurrentMatchIndex(-1)
    }
  }, [searchText, content, isOpen, searchType])

  const handleSearch = async (e?: React.MouseEvent) => {
    e?.preventDefault()
    e?.stopPropagation()
    
    console.log('検索ボタンがクリックされました', { searchText, searchType, folderPath })
    
    if (!searchText.trim()) {
      alert('検索文字列を入力してください')
      return
    }

    if (searchType === 'excel') {
      // Excelファイル検索
      setLoading(true)
      setExcelResults([])
      try {
        const response = await editorApi.searchExcelFiles(searchText, folderPath || undefined)
        if (response.success && response.results) {
          setExcelResults(response.results)
          setMatchCount(response.results.length)
        } else {
          alert(response.error || 'Excelファイルの検索に失敗しました')
          setExcelResults([])
          setMatchCount(0)
        }
      } catch (err) {
        alert(err instanceof Error ? err.message : 'Excelファイルの検索に失敗しました')
        setExcelResults([])
        setMatchCount(0)
      } finally {
        setLoading(false)
      }
    } else {
      // HTML検索
      // マッチを再計算
      const allMatches: number[] = []
      if (content) {
        let match: RegExpExecArray | null
        const regexGlobal = new RegExp(searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
        while ((match = regexGlobal.exec(content)) !== null) {
          allMatches.push(match.index)
        }
      }
      setMatches(allMatches)
      setMatchCount(allMatches.length)
      
      if (allMatches.length > 0) {
        setCurrentMatchIndex(0)
        // マッチを設定した後、少し遅延してハイライト（状態更新を待つ）
        setTimeout(() => {
          highlightMatch(0, allMatches, searchText)
        }, 0)
      } else {
        alert('検索結果が見つかりませんでした')
      }
      
      if (onSearch) {
        onSearch(searchText)
      }
    }
  }

  const highlightMatch = (index: number, matchesArray?: number[], searchQuery?: string) => {
    const matchesToUse = matchesArray || matches
    const queryToUse = searchQuery || searchText
    
    if (matchesToUse.length === 0 || index < 0 || index >= matchesToUse.length) return
    if (!queryToUse.trim()) return
    
    const matchIndex = matchesToUse[index]
    // エディタ内のテキストエリアで検索結果をハイライト
    const textarea = document.querySelector('.editor-textarea') as HTMLTextAreaElement
    if (textarea) {
      textarea.focus()
      const startPos = matchIndex
      const endPos = matchIndex + queryToUse.length
      textarea.setSelectionRange(startPos, endPos)
      // テキストエリアをスクロールして選択範囲を表示
      const lineHeight = parseInt(window.getComputedStyle(textarea).lineHeight) || 20
      const linesBefore = textarea.value.substring(0, startPos).split('\n').length - 1
      textarea.scrollTop = linesBefore * lineHeight - textarea.clientHeight / 2
    }
  }

  const handleNextMatch = () => {
    if (matches.length === 0) return
    const nextIndex = (currentMatchIndex + 1) % matches.length
    setCurrentMatchIndex(nextIndex)
    setTimeout(() => {
      highlightMatch(nextIndex)
    }, 0)
  }

  const handlePrevMatch = () => {
    if (matches.length === 0) return
    const prevIndex = currentMatchIndex <= 0 ? matches.length - 1 : currentMatchIndex - 1
    setCurrentMatchIndex(prevIndex)
    setTimeout(() => {
      highlightMatch(prevIndex)
    }, 0)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.shiftKey) {
      handlePrevMatch()
    } else if (e.key === 'Enter') {
      handleSearch()
    }
  }

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
              <label>検索タイプ:</label>
              <select
                value={searchType}
                onChange={(e) => {
                  setSearchType(e.target.value as 'html' | 'excel')
                  setExcelResults([])
                  setMatchCount(0)
                }}
                className="form-input"
              >
                <option value="html">HTML要素検索</option>
                <option value="excel">Excelファイル検索</option>
              </select>
            </div>

            {searchType === 'excel' && (
              <div className="form-group">
                <label>フォルダパス（空欄の場合は選択中のExcelファイルまたはアップロードフォルダ内の全Excelファイル）:</label>
                <input
                  type="text"
                  value={folderPath}
                  onChange={(e) => setFolderPath(e.target.value)}
                  placeholder="例: C:\excel_files（空欄可）"
                  className="form-input"
                />
                {filename && (filename.toLowerCase().endsWith('.xlsx') || filename.toLowerCase().endsWith('.xls')) && (
                  <small style={{ color: '#666', fontSize: '0.875rem', display: 'block', marginTop: '0.25rem' }}>
                    現在選択中のファイル: {filename}
                  </small>
                )}
              </div>
            )}

            <div className="form-group">
              <label>検索:</label>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input
                  type="text"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={searchType === 'excel' ? '検索キーワードを入力' : '検索文字列を入力'}
                  className="form-input"
                  style={{ flex: 1 }}
                />
                <button 
                  type="button"
                  className="btn btn-info btn-sm" 
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    handleSearch(e)
                  }} 
                  disabled={loading}
                >
                  {loading ? '検索中...' : '検索'}
                </button>
              </div>
              {matchCount > 0 && searchType === 'html' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
                  <span className="match-count">{matchCount}件見つかりました</span>
                  {currentMatchIndex >= 0 && (
                    <span style={{ fontSize: '0.875rem', color: '#666' }}>
                      ({currentMatchIndex + 1}/{matchCount})
                    </span>
                  )}
                  <div style={{ display: 'flex', gap: '0.25rem', marginLeft: 'auto' }}>
                    <button
                      className="btn btn-info btn-sm"
                      onClick={handlePrevMatch}
                      disabled={matches.length === 0}
                      title="前の検索結果へ"
                    >
                      ▲ 前へ
                    </button>
                    <button
                      className="btn btn-info btn-sm"
                      onClick={handleNextMatch}
                      disabled={matches.length === 0}
                      title="次の検索結果へ"
                    >
                      次へ ▼
                    </button>
                  </div>
                </div>
              )}
              {searchType === 'excel' && excelResults.length > 0 && (
                <div style={{ marginTop: '1rem' }}>
                  <div style={{ fontSize: '0.875rem', color: '#666', marginBottom: '0.5rem' }}>
                    {excelResults.length}件の一致が見つかりました
                  </div>
                  <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '0.5rem' }}>
                    {excelResults.map((result, index) => (
                      <div key={index} style={{ padding: '0.5rem', borderBottom: '1px solid #e2e8f0', fontSize: '0.875rem' }}>
                        {result.error ? (
                          <div style={{ color: '#c53030' }}>{result.file}: {result.error}</div>
                        ) : (
                          <div>
                            <strong>{result.file}</strong> - シート: {result.sheet}, 行: {result.row}, 列: {result.column}
                            <div style={{ color: '#666', marginTop: '0.25rem' }}>{result.value}</div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {searchType === 'html' && (
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
            )}
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
