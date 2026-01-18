import React, { useState, useCallback, useEffect } from 'react'
import ComparisonFileList from './ComparisonFileList'
import ComparisonGrid from './ComparisonGrid'
import ErrorMessage from './ErrorMessage'
import LoadingSpinner from './LoadingSpinner'
import { apiService } from '../services/api'
import type { ComparisonFile, LayoutMode } from '../types'
import './ScreenComparison.css'

const ScreenComparison: React.FC = () => {
  const [directory, setDirectory] = useState<string>('')
  const [files, setFiles] = useState<ComparisonFile[]>([])
  const [selectedFiles, setSelectedFiles] = useState<Set<number>>(new Set())
  const [layout, setLayout] = useState<LayoutMode>('grid')
  const [comparisonMode, setComparisonMode] = useState<boolean>(false)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [comparisonResults, setComparisonResults] = useState<Map<string, { htmlDiffs: number; cssDiffs: number }>>(new Map())

  const loadFiles = useCallback(async () => {
    if (!directory.trim()) {
      setError('ディレクトリパスを入力してください')
      return
    }

    setLoading(true)
    setError(null)
    
    try {
      const loadedFiles = await apiService.loadComparisonFiles(directory.trim())
      setFiles(loadedFiles)
      setSelectedFiles(new Set(loadedFiles.map((_, index) => index)))
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ファイルの読み込み中にエラーが発生しました'
      setError(errorMessage)
      console.error('Error loading files:', err)
    } finally {
      setLoading(false)
    }
  }, [directory])

  const toggleFileSelection = (index: number) => {
    const newSelected = new Set(selectedFiles)
    if (newSelected.has(index)) {
      newSelected.delete(index)
    } else {
      newSelected.add(index)
    }
    setSelectedFiles(newSelected)
  }

  const selectAllFiles = (select: boolean) => {
    if (select) {
      setSelectedFiles(new Set(files.map((_, index) => index)))
    } else {
      setSelectedFiles(new Set())
    }
  }

  const removeFile = (index: number) => {
    const newFiles = files.filter((_, i) => i !== index)
    setFiles(newFiles)
    const newSelected = new Set<number>()
    selectedFiles.forEach(idx => {
      if (idx < index) {
        newSelected.add(idx)
      } else if (idx > index) {
        newSelected.add(idx - 1)
      }
    })
    setSelectedFiles(newSelected)
  }

  const activeFiles = files.filter((_, index) => selectedFiles.has(index))

  // 複数ファイルが選択されたときに自動的に比較を実行
  useEffect(() => {
    if (activeFiles.length >= 2 && comparisonMode) {
      const performComparison = async () => {
        try {
          const response = await apiService.exportComparisonReport(
            activeFiles.map(f => ({ name: f.name, path: f.path }))
          )
          
          // 比較結果を各ファイルにマッピング
          const results = new Map<string, { htmlDiffs: number; cssDiffs: number }>()
          activeFiles.forEach((file) => {
            results.set(file.path, {
              htmlDiffs: response.htmlDiffs || 0,
              cssDiffs: response.cssDiffs || 0,
            })
          })
          setComparisonResults(results)
        } catch (err) {
          console.error('Error performing comparison:', err)
        }
      }
      performComparison()
    } else {
      setComparisonResults(new Map())
    }
  }, [activeFiles, comparisonMode])

  const handleExportReport = useCallback(async () => {
    if (activeFiles.length < 2) {
      setError('比較するには2つ以上のファイルを選択してください')
      return
    }

    try {
      const response = await apiService.exportComparisonReport(
        activeFiles.map(f => ({ name: f.name, path: f.path }))
      )
      
      // CSVファイルをダウンロード
      const blob = new Blob([response.report], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'comparison_report.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'レポートのエクスポート中にエラーが発生しました'
      setError(errorMessage)
      console.error('Error exporting report:', err)
    }
  }, [activeFiles])

  return (
    <div className="screen-comparison">
      {error && (
        <ErrorMessage
          message={error}
          onClose={() => setError(null)}
        />
      )}
      
      <div className="screen-comparison-header">
        <h1>🖼️ 画面比較（最大27大学）</h1>
        <p className="header-description">
          HTMLファイルとCSSファイルを比較・編集できます
        </p>
      </div>

      <div className="screen-comparison-controls">
        <div className="control-group">
          <label className="control-label">比較対象ディレクトリ</label>
          <div className="directory-input-group">
            <input
              type="text"
              className="directory-input"
              placeholder="例: C:\\universities または /path/to/universities"
              value={directory}
              onChange={(e) => setDirectory(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && loadFiles()}
            />
            <button
              className="btn btn-primary"
              onClick={loadFiles}
              disabled={loading || !directory.trim()}
            >
              {loading ? '読み込み中...' : '📁 ファイル読み込み'}
            </button>
          </div>
        </div>

        <div className="control-group">
          <select
            className="layout-select"
            value={layout}
            onChange={(e) => setLayout(e.target.value as LayoutMode)}
          >
            <option value="grid">グリッド表示</option>
            <option value="horizontal">横並び</option>
            <option value="vertical">縦並び</option>
          </select>
          <button
            className={`btn ${comparisonMode ? 'btn-warning' : 'btn-primary'}`}
            onClick={() => setComparisonMode(!comparisonMode)}
          >
            {comparisonMode ? '編集モード' : '比較モード'}
          </button>
          <button
            className="btn btn-success"
            onClick={handleExportReport}
            disabled={activeFiles.length < 2}
          >
            📊 比較レポート出力
          </button>
        </div>
      </div>

      <ComparisonFileList
        files={files}
        selectedFiles={selectedFiles}
        onToggleFile={toggleFileSelection}
        onSelectAll={selectAllFiles}
        onRemoveFile={removeFile}
      />

      {loading && files.length === 0 ? (
        <LoadingSpinner message="ファイルを読み込み中..." size="large" />
      ) : (
        <ComparisonGrid
          files={activeFiles}
          layout={layout}
          comparisonMode={comparisonMode}
          comparisonResults={comparisonResults}
        />
      )}
    </div>
  )
}

export default ScreenComparison
