import React, { useState, useEffect, useRef } from 'react'
import { editorApi } from '../services/editorApi'
import './HTMLEditor.css'

const HTMLEditor: React.FC = () => {
  const [content, setContent] = useState<string>('')
  const [previewContent, setPreviewContent] = useState<string>('')
  const [filename, setFilename] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
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

  const loadFile = async (name: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await editorApi.loadFile(name)
      if (response.success && response.content) {
        setContent(response.content)
        setFilename(name)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ファイルの読み込みに失敗しました')
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

  return (
    <div className="html-editor">
      <header className="html-editor-header">
        <h1>HTMLエディタ</h1>
        <div className="html-editor-actions">
          <input
            type="file"
            accept=".html,.htm"
            onChange={handleFileSelect}
            id="file-input"
            style={{ display: 'none' }}
          />
          <label htmlFor="file-input" className="btn btn-primary">
            ファイルを選択
          </label>
          {filename && (
            <>
              <button onClick={handleSave} className="btn btn-success" disabled={loading}>
                {loading ? '保存中...' : '保存'}
              </button>
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
