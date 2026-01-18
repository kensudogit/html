import React, { useState, useEffect, useRef } from 'react'
import './RemoteControl.css'

interface RemoteControlProps {
  filename: string | null
  onUpload: () => void
  onSave: () => void
  onReload: () => void
  onClear: () => void
  onShowStructure: () => void
  onValidate: () => void
  onSearch: () => void
  onShowFileList: () => void
  onSearchElement: (query: string) => void
}

const RemoteControl: React.FC<RemoteControlProps> = ({
  filename,
  onUpload,
  onSave,
  onReload,
  onClear,
  onShowStructure,
  onValidate,
  onSearch,
  onShowFileList,
  onSearchElement,
}) => {
  const [collapsed, setCollapsed] = useState<boolean>(false)
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const remoteControlRef = useRef<HTMLDivElement>(null)
  const headerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // 保存された位置と状態を復元
    const savedPosition = localStorage.getItem('remoteControlPosition')
    const savedState = localStorage.getItem('remoteControlState')

    if (savedPosition) {
      const pos = JSON.parse(savedPosition)
      setPosition(pos)
    }

    if (savedState === 'collapsed') {
      setCollapsed(true)
    }
  }, [])

  useEffect(() => {
    // 状態を保存
    localStorage.setItem('remoteControlState', collapsed ? 'collapsed' : 'expanded')
  }, [collapsed])

  useEffect(() => {
    // 位置を保存
    if (position) {
      localStorage.setItem('remoteControlPosition', JSON.stringify(position))
    }
  }, [position])

  const handleHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.remote-control-toggle')) return

    setIsDragging(true)
    const rect = remoteControlRef.current?.getBoundingClientRect()
    if (rect) {
      setDragStart({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      })
    }
    e.preventDefault()
  }

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragStart || !remoteControlRef.current) return

      let newX = e.clientX - dragStart.x
      let newY = e.clientY - dragStart.y

      // 画面外に出ないように制限
      const maxX = window.innerWidth - remoteControlRef.current.offsetWidth
      const maxY = window.innerHeight - remoteControlRef.current.offsetHeight

      newX = Math.max(0, Math.min(newX, maxX))
      newY = Math.max(0, Math.min(newY, maxY))

      setPosition({ x: newX, y: newY })
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      setDragStart(null)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, dragStart])

  const handleToggle = () => {
    setCollapsed(!collapsed)
  }

  const handleSearchKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onSearchElement(searchQuery)
    }
  }

  const hasFile = !!filename

  const style: React.CSSProperties = position
    ? {
        left: `${position.x}px`,
        top: `${position.y}px`,
        right: 'auto',
        bottom: 'auto',
      }
    : {
        right: '20px',
        top: '20px',
      }

  return (
    <div
      ref={remoteControlRef}
      className={`remote-control ${collapsed ? 'collapsed' : ''} ${isDragging ? 'dragging' : ''}`}
      style={style}
    >
      <div
        ref={headerRef}
        className="remote-control-header"
        onMouseDown={handleHeaderMouseDown}
      >
        <div className="remote-control-title">🎮 リモコン盤</div>
        <button
          className="remote-control-toggle"
          onClick={handleToggle}
          title="開閉"
        >
          {collapsed ? '▲' : '▼'}
        </button>
      </div>
      {!collapsed && (
        <div className="remote-control-content">
          {/* ファイル操作セクション */}
          <div className="remote-control-section">
            <div className="remote-control-section-title">ファイル操作</div>
            <div className="remote-control-buttons">
              <button
                className="btn btn-primary"
                onClick={onUpload}
                style={{
                  fontWeight: 600,
                  background: '#667eea',
                  border: '2px solid #5568d3',
                  color: 'white',
                }}
              >
                📤 アップロード
              </button>
              <button
                className="btn btn-info"
                onClick={onShowFileList}
                style={{
                  fontWeight: 600,
                  background: '#3b82f6',
                  border: '2px solid #2563eb',
                  color: 'white',
                }}
              >
                📁 ファイル一覧
              </button>
            </div>
          </div>

          {/* 編集操作セクション */}
          <div className="remote-control-section">
            <div className="remote-control-section-title">編集操作</div>
            <div className="remote-control-buttons">
              <button
                className="btn btn-primary"
                onClick={onSave}
                disabled={!hasFile}
                style={{
                  fontWeight: 600,
                  background: '#667eea',
                  border: '2px solid #5568d3',
                  color: 'white',
                }}
              >
                💾 保存
              </button>
              <button
                className="btn btn-success"
                onClick={onReload}
                disabled={!hasFile}
                style={{
                  fontWeight: 600,
                  background: '#48bb78',
                  border: '2px solid #38a169',
                  color: 'white',
                }}
              >
                🔄 再読み込み
              </button>
              <button
                className="btn btn-danger"
                onClick={onClear}
                style={{
                  fontWeight: 600,
                  background: '#ef4444',
                  border: '2px solid #dc2626',
                  color: 'white',
                }}
              >
                🗑️ クリア
              </button>
              <button
                className="btn btn-warning"
                onClick={onShowStructure}
                disabled={!hasFile}
                style={{
                  fontWeight: 600,
                  background: '#f59e0b',
                  border: '2px solid #d97706',
                  color: 'white',
                }}
              >
                📊 構造情報
              </button>
              <button
                className="btn btn-danger"
                onClick={onValidate}
                disabled={!hasFile}
                style={{
                  fontWeight: 600,
                  background: '#ef4444',
                  border: '2px solid #dc2626',
                  color: 'white',
                }}
              >
                ⚠️ 構文チェック
              </button>
              <button
                className="btn btn-info"
                onClick={onSearch}
                disabled={!hasFile}
                style={{
                  fontWeight: 600,
                  background: '#3b82f6',
                  border: '2px solid #2563eb',
                  color: 'white',
                }}
              >
                🔍 検索・置換
              </button>
            </div>
          </div>

          {/* 要素検索セクション */}
          <div className="remote-control-section">
            <div className="remote-control-section-title">要素検索</div>
            <div className="remote-control-search">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={handleSearchKeyPress}
                placeholder="ID、クラス、タグ、テキストで検索..."
                disabled={!hasFile}
              />
              <button
                className="btn btn-info"
                onClick={() => onSearchElement(searchQuery)}
                disabled={!hasFile}
                style={{
                  fontWeight: 600,
                  background: '#3b82f6',
                  border: '2px solid #2563eb',
                  color: 'white',
                }}
              >
                検索
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RemoteControl
