import React, { useState, useEffect, useRef } from 'react'
import { editorApi } from '../services/editorApi'
import RemoteControl from './RemoteControl'
import './HTMLEditor.css'

const HTMLEditor: React.FC = () => {
  const [content, setContent] = useState<string>('')
  const [previewContent, setPreviewContent] = useState<string>('')
  const [filename, setFilename] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    // プレビューを更新
    setPreviewContent(content)
  }, [content])

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      await editorApi.uploadFile(file)
      setFilename(file.name)
      // アップロード後、コンテンツを取得
      const response = await editorApi.getContent()
      if (response.success && response.content) {
        setContent(response.content)
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
    // TODO: 構造情報モーダルを表示
    alert('構造情報機能は実装中です')
  }

  const handleValidate = async () => {
    if (!filename) return

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      // TODO: バリデーションAPIを呼び出す
      alert('構文チェック機能は実装中です')
    } catch (err) {
      setError(err instanceof Error ? err.message : '構文チェックに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    // TODO: 検索・置換モーダルを表示
    alert('検索・置換機能は実装中です')
  }

  const handleShowFileList = () => {
    // TODO: ファイル一覧モーダルを表示
    alert('ファイル一覧機能は実装中です')
  }

  const handleSearchElement = (query: string) => {
    if (!query.trim()) return

    // TODO: 要素検索機能を実装
    alert(`要素検索: ${query}`)
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
      <header className="html-editor-header">
        <h1>HTMLエディタ</h1>
        <div className="html-editor-actions">
          <input
            ref={fileInputRef}
            type="file"
            accept=".html,.htm"
            onChange={handleFileSelect}
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
          />
        </div>
      </div>
    </div>
  )
}

export default HTMLEditor
