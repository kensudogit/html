import React, { useState } from 'react'
import { editorApi } from '../services/editorApi'
import './Modal.css'

interface DiffAnalysisModalProps {
  isOpen: boolean
  onClose: () => void
}

const DiffAnalysisModal: React.FC<DiffAnalysisModalProps> = ({ isOpen, onClose }) => {
  const [directory, setDirectory] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<any>(null)
  const [options, setOptions] = useState({
    structureDiff: true,
    attributeDiff: true,
    detailedDiff: false,
  })

  const handleAnalyze = async () => {
    if (!directory.trim()) {
      setError('ディレクトリパスを入力してください')
      return
    }

    setLoading(true)
    setError(null)
    setResults(null)

    try {
      const response = await editorApi.diffAnalysis(directory.trim(), options)
      if (response.success) {
        setResults(response)
      } else {
        setError(response.error || '差分検出に失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '差分検出中にエラーが発生しました')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateTemplate = async () => {
    if (!results || !results.files || results.files.length < 2) {
      setError('テンプレート生成には2つ以上のファイルが必要です')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const filePaths = results.files.map((filename: string) => {
        // ファイルパスを構築（簡略版）
        return directory.trim() + '/' + filename
      })
      const response = await editorApi.templateMerge(filePaths, options)
      if (response.success) {
        setResults((prev: any) => ({
          ...prev,
          template: response.template,
          templateStats: response.stats,
        }))
      } else {
        setError(response.error || 'テンプレート生成に失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'テンプレート生成中にエラーが発生しました')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadReport = () => {
    if (!results) return

    const report = JSON.stringify(results, null, 2)
    const blob = new Blob([report], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'diff_report.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadCSV = () => {
    if (!results) return

    let csv = 'ファイル名,差分タイプ,詳細\n'
    if (results.differences) {
      results.differences.forEach((diff: any) => {
        csv += `${diff.file || ''},${diff.type || ''},${diff.details || ''}\n`
      })
    }

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'diff_report.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🔍 差分検出とテンプレート生成</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label>27校のHTMLファイルが保存されているディレクトリパス:</label>
            <input
              type="text"
              className="form-input"
              value={directory}
              onChange={(e) => setDirectory(e.target.value)}
              placeholder="例: C:\universities"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>検出オプション:</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label>
                <input
                  type="checkbox"
                  checked={options.structureDiff}
                  onChange={(e) => setOptions({ ...options, structureDiff: e.target.checked })}
                  disabled={loading}
                />
                構造の差分
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={options.attributeDiff}
                  onChange={(e) => setOptions({ ...options, attributeDiff: e.target.checked })}
                  disabled={loading}
                />
                属性の差分
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={options.detailedDiff}
                  onChange={(e) => setOptions({ ...options, detailedDiff: e.target.checked })}
                  disabled={loading}
                />
                詳細な差分情報を表示
              </label>
            </div>
          </div>

          {error && (
            <div className="error-message">{error}</div>
          )}

          {results && (
            <div style={{ marginTop: '1rem' }}>
              <h3>検出結果</h3>
              <p>ファイル数: {results.fileCount || 0}</p>
              <p>差分数: {results.diffCount || 0}</p>
              {results.template && (
                <div style={{ marginTop: '1rem' }}>
                  <h4>テンプレート生成完了</h4>
                  {results.templateStats && (
                    <p>共通要素数: {results.templateStats.commonElements || 0}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {loading && (
            <div style={{ textAlign: 'center', padding: '1rem' }}>
              処理中...
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button
            className="btn btn-primary"
            onClick={handleAnalyze}
            disabled={loading || !directory.trim()}
          >
            🔍 差分検出実行
          </button>
          {results && !results.template && (
            <button
              className="btn btn-success"
              onClick={handleGenerateTemplate}
              disabled={loading}
            >
              🔀 最大公約数テンプレート生成
            </button>
          )}
          {results && (
            <>
              <button
                className="btn btn-info"
                onClick={handleDownloadReport}
                disabled={loading}
              >
                📥 差分レポートをダウンロード
              </button>
              <button
                className="btn btn-info"
                onClick={handleDownloadCSV}
                disabled={loading}
              >
                📊 CSVでエクスポート
              </button>
            </>
          )}
          <button className="btn btn-secondary" onClick={onClose} disabled={loading}>
            閉じる
          </button>
        </div>
      </div>
    </div>
  )
}

export default DiffAnalysisModal
