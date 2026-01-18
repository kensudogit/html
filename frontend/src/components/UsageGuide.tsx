import React, { useState, useEffect, useRef } from 'react'
import './UsageGuide.css'

const UsageGuide: React.FC = () => {
  const [collapsed, setCollapsed] = useState<boolean>(false)
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const usageGuideRef = useRef<HTMLDivElement>(null)
  const headerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // 保存された位置と状態を復元
    const savedPosition = localStorage.getItem('usageGuidePosition')
    const savedState = localStorage.getItem('usageGuideState')

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
    localStorage.setItem('usageGuideState', collapsed ? 'collapsed' : 'expanded')
  }, [collapsed])

  useEffect(() => {
    // 位置を保存
    if (position) {
      localStorage.setItem('usageGuidePosition', JSON.stringify(position))
    }
  }, [position])

  const handleHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.usage-guide-toggle')) return

    setIsDragging(true)
    const rect = usageGuideRef.current?.getBoundingClientRect()
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
      if (!dragStart || !usageGuideRef.current) return

      let newX = e.clientX - dragStart.x
      let newY = e.clientY - dragStart.y

      // 画面外に出ないように制限
      const maxX = window.innerWidth - usageGuideRef.current.offsetWidth
      const maxY = window.innerHeight - usageGuideRef.current.offsetHeight

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

  const style: React.CSSProperties = position
    ? {
        left: `${position.x}px`,
        top: `${position.y}px`,
        bottom: 'auto',
        right: 'auto',
      }
    : {
        left: '20px',
        bottom: '20px',
      }

  return (
    <div
      ref={usageGuideRef}
      className={`usage-guide ${collapsed ? 'collapsed' : ''} ${isDragging ? 'dragging' : ''}`}
      style={style}
    >
      <div
        ref={headerRef}
        className="usage-guide-header"
        onMouseDown={handleHeaderMouseDown}
      >
        <div className="usage-guide-title">📖 利用手順</div>
        <button
          className="usage-guide-toggle"
          onClick={handleToggle}
          title="開閉"
        >
          {collapsed ? '▲' : '▼'}
        </button>
      </div>
      {!collapsed && (
        <div className="usage-guide-content">
          <div className="usage-guide-step">
            <div className="usage-guide-step-title">
              <span className="usage-guide-step-number">1</span>
              ファイルのアップロード・編集
            </div>
            <div className="usage-guide-step-content">
              <ul>
                <li>リモコン盤の「📤 アップロード」ボタンからHTMLファイルをアップロード</li>
                <li>アップロード後、サーバーのアップロードフォルダにファイルが保存されます（元のファイルは変更されません）</li>
                <li>左側のエディタでHTMLソースを編集可能</li>
                <li>右側のプレビューでリアルタイムに変更内容を確認</li>
                <li>「💾 保存」ボタンで編集内容を保存（Ctrl+Sでも保存可能）※アップロード先のファイルが更新されます</li>
              </ul>
            </div>
          </div>

          <div className="usage-guide-step">
            <div className="usage-guide-step-title">
              <span className="usage-guide-step-number">2</span>
              自由配置モード（🪟 自由配置モード）
            </div>
            <div className="usage-guide-step-content">
              <ul>
                <li>リモコン盤の「🪟 自由配置モード」ボタンをクリック</li>
                <li>HTMLソースとプレビューウィンドウを自由に移動・リサイズ可能</li>
                <li>ウィンドウのヘッダーをドラッグして移動</li>
                <li>ウィンドウの端や角をドラッグしてリサイズ</li>
                <li>配置は自動保存され、次回起動時にも復元されます</li>
                <li>「📐 通常モード」で元の分割表示に戻せます</li>
              </ul>
            </div>
          </div>

          <div className="usage-guide-step">
            <div className="usage-guide-step-title">
              <span className="usage-guide-step-number">3</span>
              画面比較機能（🖼️ 画面比較）
            </div>
            <div className="usage-guide-step-content">
              <ul>
                <li>リモコン盤の「🖼️ 画面比較」ボタンをクリック</li>
                <li>比較対象ディレクトリパスを入力（例: C:\universities）</li>
                <li>「📁 ファイル読み込み」でHTML/CSSファイルを自動検出（最大27ファイル）</li>
                <li>HTMLファイルとCSSファイルが自動的に関連付けられます</li>
                <li>ファイル一覧から比較したいファイルを選択（チェックボックス）</li>
                <li>レイアウト選択: グリッド表示 / 横並び / 縦並び</li>
                <li>各画面のアクション:
                  <ul>
                    <li>✏️ 編集: 新しいタブでエディタを開く</li>
                    <li>⬇️ ダウンロード: ファイルをダウンロード</li>
                    <li>📊 分析: 画面の詳細分析</li>
                  </ul>
                </li>
                <li>「📊 比較レポート出力」でCSV形式の比較レポートをダウンロード</li>
              </ul>
            </div>
          </div>

          <div className="usage-guide-step">
            <div className="usage-guide-step-title">
              <span className="usage-guide-step-number">4</span>
              HTML/CSS比較機能
            </div>
            <div className="usage-guide-step-content">
              <ul>
                <li>画面比較モードで複数ファイルを選択すると自動的に比較が実行されます</li>
                <li>HTML構造の比較: タグ、クラス、ID、属性の差分を検出</li>
                <li>CSS比較: セレクタ、プロパティ、値の差分を検出</li>
                <li>比較結果バッジに「HTML: X箇所, CSS: Y箇所」と表示</li>
                <li>CSSファイルはシンタックスハイライト付きで表示</li>
                <li>比較レポートにはHTML/CSSの両方の情報が含まれます</li>
              </ul>
            </div>
          </div>

          <div className="usage-guide-step">
            <div className="usage-guide-step-title">
              <span className="usage-guide-step-number">5</span>
              差分検出とテンプレート生成（27大学のホームページ）
            </div>
            <div className="usage-guide-step-content">
              <ul>
                <li>リモコン盤の「🔍 差分検出」ボタンをクリック</li>
                <li>27校のHTMLファイルが保存されているディレクトリパスを入力</li>
                <li>検出オプションを選択:
                  <ul>
                    <li>構造の差分: HTML構造の違いを検出</li>
                    <li>属性の差分: 属性値の違いを検出</li>
                    <li>詳細な差分情報を表示: より詳細な比較結果</li>
                  </ul>
                </li>
                <li>「🔍 差分検出実行」をクリックして処理開始</li>
                <li>差分検出完了後、「🔀 最大公約数テンプレート生成」をクリック</li>
                <li>共通部分と差分部分（変数化）を含むテンプレートが生成されます</li>
                <li>「📥 差分レポートをダウンロード」で詳細な差分情報を取得</li>
                <li>「📊 CSVでエクスポート」で比較結果をCSV形式で出力</li>
              </ul>
            </div>
          </div>

          <div className="usage-guide-step">
            <div className="usage-guide-step-title">
              <span className="usage-guide-step-number">6</span>
              27大学のホームページ生成
            </div>
            <div className="usage-guide-step-content">
              <ul>
                <li>テンプレート生成後、「🏫 27大学のホームページを生成」をクリック</li>
                <li>各大学の現行デザインを保持したホームページが自動生成されます</li>
                <li>生成されたファイルは「📦 ZIPファイルをダウンロード」で一括ダウンロード可能</li>
                <li>各大学の個別ファイルも個別にダウンロードできます</li>
              </ul>
            </div>
          </div>

          <div className="usage-guide-step">
            <div className="usage-guide-step-title">
              <span className="usage-guide-step-number">7</span>
              大学データ管理・YAML設定ファイルからページ一括生成（🏫 大学データ管理）
            </div>
            <div className="usage-guide-step-content">
              <ul>
                <li>リモコン盤の「🏫 大学データ管理」ボタンをクリック</li>
                <li><strong>基本機能:</strong>
                  <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                    <li>大学一覧から大学を選択、または新規大学を追加</li>
                    <li>ページタイトルを選択して、各大学のページデータを編集・保存</li>
                    <li>「⚙️ 表示位置設定」で各項目の表示位置・スタイルを設定</li>
                    <li>「🔀 ページ生成」で個別ページを生成</li>
                  </ul>
                </li>
                <li><strong>YAML設定ファイルから一括生成:</strong>
                  <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                    <li>モーダル下部の「📄 YAML設定ファイルから一括生成」セクションを確認</li>
                    <li><strong>対象大学:</strong> 大学コードをカンマ区切りで入力（例: UNIV001,UNIV002）<br />
                        空欄の場合は全大学が対象となります</li>
                    <li><strong>出力ディレクトリ:</strong> 生成ファイルの保存先を指定（空欄の場合はデフォルト）</li>
                    <li>「🚀 ページ一括生成」ボタンをクリック</li>
                    <li>university_pages_config.ymlの設定に基づいて、各大学の入学手続きWEBページ（全20ページ）が自動生成されます</li>
                    <li>生成されるページ: 入学手続TOP、個人情報同意、本人情報、健康状況、保護者情報、身元保証人情報、緊急連絡先情報、入学前セミナー受講調査、写真アップロード、書類アップロード、アンケート、学費負担者情報、外国語の履修に関する調査、父母等の連絡、誓約書、アドミッション・ポリシー、家族情報、通学住所情報、利用規約・個人情報取扱いに関する同意条項、言語選択申請</li>
                    <li>各ページには適切なフォームフィールド（テキスト、テキストエリア、日付、選択、チェックボックス、ラジオボタン、ファイルアップロードなど）が自動的に配置されます</li>
                    <li>生成完了後、生成結果が表示されます（対象大学数、生成ページ数、成功/失敗数など）</li>
                    <li>「📦 生成済みページをダウンロード」ボタンで、生成された全ページをZIPファイルとしてダウンロード可能</li>
                  </ul>
                </li>
                <li><strong>YAML設定ファイルのカスタマイズ:</strong>
                  <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                    <li>university_pages_config.ymlファイルを編集することで、ページタイトル、フォームフィールド、大学ごとのカスタマイズ設定を変更できます</li>
                    <li>各大学のレイアウトテーマ、カラースキーム、表示順序などを個別に設定可能</li>
                  </ul>
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default UsageGuide
