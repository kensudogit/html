import React, { useState, useEffect } from 'react'
import { editorApi } from '../services/editorApi'
import './Modal.css'

interface UniversityDataManagementModalProps {
  isOpen: boolean
  onClose: () => void
}

const UniversityDataManagementModal: React.FC<UniversityDataManagementModalProps> = ({ isOpen, onClose }) => {
  const [universities, setUniversities] = useState<any[]>([])
  const [selectedUniversity, setSelectedUniversity] = useState<number | null>(null)
  const [pageTitles, setPageTitles] = useState<any[]>([])
  const [selectedPageTitle, setSelectedPageTitle] = useState<number | null>(null)
  const [pageContent, setPageContent] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [yamlTargetUniversities, setYamlTargetUniversities] = useState<string>('')
  const [yamlOutputDir, setYamlOutputDir] = useState<string>('')
  const [yamlGenerationResult, setYamlGenerationResult] = useState<any>(null)

  useEffect(() => {
    if (isOpen) {
      loadUniversities()
      loadPageTitles()
    }
  }, [isOpen])

  const loadUniversities = async () => {
    try {
      const response = await editorApi.getUniversities()
      if (response.success && response.universities) {
        setUniversities(response.universities)
      }
    } catch (err) {
      console.error('Error loading universities:', err)
    }
  }

  const loadPageTitles = async () => {
    try {
      const response = await editorApi.getPageTitles()
      if (response.success && response.pageTitles) {
        setPageTitles(response.pageTitles)
      }
    } catch (err) {
      console.error('Error loading page titles:', err)
    }
  }

  const loadPageContent = async () => {
    if (!selectedUniversity || !selectedPageTitle) return

    setLoading(true)
    setError(null)
    try {
      const response = await editorApi.getUniversityPageDetail(selectedUniversity, selectedPageTitle)
      if (response.success) {
        setPageContent(response.content || '')
      } else {
        setError(response.error || 'ページデータの読み込みに失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ページデータの読み込み中にエラーが発生しました')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (selectedUniversity && selectedPageTitle) {
      loadPageContent()
    }
  }, [selectedUniversity, selectedPageTitle])

  const handleSavePage = async () => {
    if (!selectedUniversity || !selectedPageTitle) {
      setError('大学とページタイトルを選択してください')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await editorApi.saveUniversityPageDetail(selectedUniversity, selectedPageTitle, pageContent)
      if (response.success) {
        setSuccess('ページデータを保存しました')
      } else {
        setError(response.error || 'ページデータの保存に失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ページデータの保存中にエラーが発生しました')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateFromYAML = async () => {
    setLoading(true)
    setError(null)
    setSuccess(null)
    setYamlGenerationResult(null)

    try {
      const response = await editorApi.generatePagesFromYAML(
        yamlTargetUniversities,
        yamlOutputDir
      )
      if (response.success) {
        setYamlGenerationResult(response)
        setSuccess('ページの一括生成が完了しました')
      } else {
        setError(response.error || 'ページの一括生成に失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ページの一括生成中にエラーが発生しました')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadGeneratedPages = async () => {
    if (!yamlGenerationResult) return

    try {
      const blob = await editorApi.downloadGeneratedPages()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'university_pages.zip'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ダウンロードに失敗しました')
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🏫 大学データ管理</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* 基本機能セクション */}
            <div>
              <h3>基本機能</h3>
              <div className="form-group">
                <label>大学を選択:</label>
                <select
                  className="form-input"
                  value={selectedUniversity || ''}
                  onChange={(e) => setSelectedUniversity(Number(e.target.value) || null)}
                >
                  <option value="">選択してください</option>
                  {universities.map((uni) => (
                    <option key={uni.id} value={uni.id}>
                      {uni.code} - {uni.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>ページタイトルを選択:</label>
                <select
                  className="form-input"
                  value={selectedPageTitle || ''}
                  onChange={(e) => setSelectedPageTitle(Number(e.target.value) || null)}
                >
                  <option value="">選択してください</option>
                  {pageTitles.map((title) => (
                    <option key={title.id} value={title.id}>
                      {title.title}
                    </option>
                  ))}
                </select>
              </div>

              {selectedUniversity && selectedPageTitle && (
                <div className="form-group">
                  <label>ページデータ:</label>
                  <textarea
                    className="form-input"
                    value={pageContent}
                    onChange={(e) => setPageContent(e.target.value)}
                    rows={10}
                    style={{ fontFamily: 'monospace' }}
                  />
                  <button
                    className="btn btn-primary"
                    onClick={handleSavePage}
                    disabled={loading}
                    style={{ marginTop: '0.5rem' }}
                  >
                    💾 保存
                  </button>
                </div>
              )}
            </div>

            {/* YAML設定ファイルから一括生成セクション */}
            <div style={{ borderTop: '1px solid #eee', paddingTop: '1rem' }}>
              <h3>📄 YAML設定ファイルから一括生成</h3>
              <div className="form-group">
                <label>対象大学（大学コードをカンマ区切り、空欄で全大学）:</label>
                <input
                  type="text"
                  className="form-input"
                  value={yamlTargetUniversities}
                  onChange={(e) => setYamlTargetUniversities(e.target.value)}
                  placeholder="例: UNIV001,UNIV002"
                />
              </div>
              <div className="form-group">
                <label>出力ディレクトリ（空欄でデフォルト）:</label>
                <input
                  type="text"
                  className="form-input"
                  value={yamlOutputDir}
                  onChange={(e) => setYamlOutputDir(e.target.value)}
                  placeholder="例: C:\output"
                />
              </div>
              <button
                className="btn btn-success"
                onClick={handleGenerateFromYAML}
                disabled={loading}
              >
                🚀 ページ一括生成
              </button>

              {yamlGenerationResult && (
                <div style={{ marginTop: '1rem', padding: '1rem', background: '#f0f9ff', borderRadius: '4px' }}>
                  <h4>生成結果</h4>
                  <p>対象大学数: {yamlGenerationResult.targetCount || 0}</p>
                  <p>生成ページ数: {yamlGenerationResult.generatedCount || 0}</p>
                  <p>成功: {yamlGenerationResult.successCount || 0}</p>
                  <p>失敗: {yamlGenerationResult.failedCount || 0}</p>
                  <button
                    className="btn btn-info"
                    onClick={handleDownloadGeneratedPages}
                    style={{ marginTop: '0.5rem' }}
                  >
                    📦 生成済みページをダウンロード
                  </button>
                </div>
              )}
            </div>

            {error && <div className="error-message">{error}</div>}
            {success && <div className="success-message">{success}</div>}
            {loading && <div style={{ textAlign: 'center', padding: '1rem' }}>処理中...</div>}
          </div>
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

export default UniversityDataManagementModal
