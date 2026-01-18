import React, { useState, useEffect, useRef } from 'react'
import { editorApi } from '../services/editorApi'
import RemoteControl from './RemoteControl'
import UsageGuide from './UsageGuide'
import StructureModal from './StructureModal'
import ValidateModal from './ValidateModal'
import SearchModal from './SearchModal'
import FileListModal from './FileListModal'
import './HTMLEditor.css'

const HTMLEditor: React.FC = () => {
  const [content, setContent] = useState<string>('')
  const [previewContent, setPreviewContent] = useState<string>('')
  const [filename, setFilename] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showStructureModal, setShowStructureModal] = useState<boolean>(false)
  const [showValidateModal, setShowValidateModal] = useState<boolean>(false)
  const [showSearchModal, setShowSearchModal] = useState<boolean>(false)
  const [showFileListModal, setShowFileListModal] = useState<boolean>(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    // プレビューを更新
    setPreviewContent(content)
  }, [content])

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      await editorApi.uploadFile(file)
      setFilename(file.name)
      
      // Excelファイルの場合はコンテンツを取得しない
      const isExcel = file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls')
      if (!isExcel) {
        // HTMLファイルの場合のみコンテンツを取得
        const response = await editorApi.getContent()
        if (response.success && response.content) {
          setContent(response.content)
        }
      }
      setSuccess('ファイルをアップロードしました')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ファイルのアップロードに失敗しました')
    } finally {
      setLoading(false)
    }
  }


  const handleSave = async () => {
    if (!filename) {
      setError('ファイルが選択されていません')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      await editorApi.saveContent(content)
      setSuccess('ファイルを保存しました')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ファイルの保存に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value)
  }

  const handleUpload = () => {
    fileInputRef.current?.click()
  }

  const handleReload = async () => {
    if (!filename) return

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await editorApi.getContent()
      if (response.success && response.content) {
        setContent(response.content)
        setSuccess('ファイルを再読み込みしました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ファイルの再読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    if (window.confirm('エディタの内容をクリアしますか？')) {
      setContent('')
      setSuccess('エディタをクリアしました')
    }
  }

  const handleShowStructure = () => {
    setShowStructureModal(true)
  }

  const handleValidate = () => {
    setShowValidateModal(true)
  }

  const handleSearch = () => {
    setShowSearchModal(true)
  }

  const handleShowFileList = () => {
    setShowFileListModal(true)
  }

  const handleSearchElement = async (query: string) => {
    if (!query.trim()) {
      setError('検索文字列を入力してください')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await editorApi.searchElement(query)
      if (response.success && response.results) {
        if (response.results.length === 0) {
          setSuccess('検索結果が見つかりませんでした')
        } else {
          setSuccess(`${response.results.length}件の要素が見つかりました`)
          // TODO: 検索結果をハイライト表示
          console.log('検索結果:', response.results)
        }
      } else {
        setError(response.error || '要素の検索に失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '要素の検索に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleFileSelect = async (selectedFilename: string) => {
    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await editorApi.loadFile(selectedFilename)
      if (response.success && response.content) {
        setContent(response.content)
        setFilename(selectedFilename)
        setSuccess('ファイルを読み込みました')
      } else {
        setError(response.error || 'ファイルの読み込みに失敗しました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ファイルの読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleSearchReplace = (searchText: string, replaceText: string) => {
    if (!searchText.trim()) {
      setError('検索文字列を入力してください')
      return
    }

    const regex = new RegExp(searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
    const newContent = content.replace(regex, replaceText)
    
    if (newContent === content) {
      setError('置換対象が見つかりませんでした')
      return
    }

    setContent(newContent)
    setSuccess('置換が完了しました')
  }

  const handleSearchInModal = (_searchText: string) => {
    // 検索モーダル内での検索処理（ハイライト表示など）
    // 実際のハイライトはSearchModal内で処理される
  }

  return (
    <div className="html-editor">
      <RemoteControl
        filename={filename}
        onUpload={handleUpload}
        onSave={handleSave}
        onReload={handleReload}
        onClear={handleClear}
        onShowStructure={handleShowStructure}
        onValidate={handleValidate}
        onSearch={handleSearch}
        onShowFileList={handleShowFileList}
        onSearchElement={handleSearchElement}
      />
      <UsageGuide />
      <header className="html-editor-header">
        <div className="html-editor-logo-title">
          <img src="/logo.png" alt="ロゴ" className="html-editor-logo" />
          <h1>HTMLエディタ</h1>
        </div>
        <div className="html-editor-actions">
          <input
            ref={fileInputRef}
            type="file"
            accept=".html,.htm,.xlsx,.xls"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />
          {filename && (
            <>
              <span className="filename">{filename}</span>
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          {success}
        </div>
      )}

      {loading && (
        <div className="alert alert-info" style={{ background: '#dbeafe', color: '#1e40af', border: '1px solid #93c5fd' }}>
          処理中...
        </div>
      )}

      <div className="html-editor-content">
        <div className="editor-panel">
          <h2>エディタ</h2>
          <textarea
            value={content}
            onChange={handleContentChange}
            className="editor-textarea"
            placeholder="HTMLファイルを選択するか、直接HTMLコードを入力してください"
          />
        </div>
        <div className="preview-panel">
          <h2>プレビュー</h2>
          <iframe
            ref={iframeRef}
            srcDoc={previewContent}
            className="preview-iframe"
            title="HTML Preview"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
            onError={(e) => {
              // iframe内のエラーを抑制
              e.preventDefault()
              e.stopPropagation()
            }}
          />
        </div>
      </div>

      {/* モーダル */}
      <StructureModal
        isOpen={showStructureModal}
        onClose={() => setShowStructureModal(false)}
      />
      <ValidateModal
        isOpen={showValidateModal}
        onClose={() => setShowValidateModal(false)}
        content={content}
      />
      <SearchModal
        isOpen={showSearchModal}
        onClose={() => setShowSearchModal(false)}
        content={content}
        onReplace={handleSearchReplace}
        onSearch={handleSearchInModal}
        filename={filename}
      />
      <FileListModal
        isOpen={showFileListModal}
        onClose={() => setShowFileListModal(false)}
        onSelectFile={handleFileSelect}
      />
    </div>
  )
}

export default HTMLEditor
