import React, { useState, useEffect, useCallback } from 'react'
import ComparisonScreen from './ComparisonScreen'
import { apiService } from '../services/api'
import type { ComparisonFile, LayoutMode } from '../types'
import './ComparisonGrid.css'

interface ComparisonGridProps {
  files: ComparisonFile[]
  layout: LayoutMode
  comparisonMode: boolean
}

const ComparisonGrid: React.FC<ComparisonGridProps> = ({
  files,
  layout,
  comparisonMode,
}) => {
  const [fileContents, setFileContents] = useState<Map<string, string>>(new Map())
  const [loading, setLoading] = useState<Set<string>>(new Set())
  const [errors, setErrors] = useState<Map<string, string>>(new Map())

  const loadFileContent = useCallback(async (file: ComparisonFile) => {
    // 既に読み込み済みまたは読み込み中の場合はスキップ
    if (fileContents.has(file.path) || loading.has(file.path)) {
      return
    }

    setLoading((prev) => new Set(prev).add(file.path))
    setErrors((prev) => {
      const newMap = new Map(prev)
      newMap.delete(file.path)
      return newMap
    })

    try {
      const content = await apiService.loadFileContent(file.path)
      setFileContents((prev) => {
        const newMap = new Map(prev)
        newMap.set(file.path, content)
        return newMap
      })
      
      // HTMLファイルの場合は、関連するCSSファイルも自動的に読み込む
      if (file.type === 'html' && file.relatedFiles && file.relatedFiles.length > 0) {
        // 関連CSSファイルの読み込みは非同期で実行（エラーは無視）
        file.relatedFiles.forEach(async (cssPath) => {
          try {
            if (!fileContents.has(cssPath) && !loading.has(cssPath)) {
              const cssContent = await apiService.loadFileContent(cssPath)
              setFileContents((prev) => {
                const newMap = new Map(prev)
                newMap.set(cssPath, cssContent)
                return newMap
              })
            }
          } catch (err) {
            // CSSファイルの読み込みエラーは無視（オプショナル）
            console.warn(`Failed to load related CSS file: ${cssPath}`, err)
          }
        })
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'ファイルの読み込みに失敗しました'
      setErrors((prev) => {
        const newMap = new Map(prev)
        newMap.set(file.path, errorMessage)
        return newMap
      })
      console.error(`Error loading file content for ${file.name}:`, error)
    } finally {
      setLoading((prev) => {
        const newSet = new Set(prev)
        newSet.delete(file.path)
        return newSet
      })
    }
  }, [fileContents, loading])

  useEffect(() => {
    // 各ファイルの内容を読み込む（HTMLとCSSの両方）
    files.forEach((file) => {
      loadFileContent(file)
    })
  }, [files, loadFileContent])

  if (files.length === 0) {
    return (
      <div className="comparison-grid-empty">
        <p>表示するファイルを選択してください</p>
      </div>
    )
  }

  return (
    <div className={`comparison-grid comparison-grid-${layout} ${comparisonMode ? 'comparison-mode' : ''}`}>
      {files.map((file) => (
        <ComparisonScreen
          key={file.path}
          file={file}
          content={fileContents.get(file.path) || ''}
          isLoading={loading.has(file.path)}
          error={errors.get(file.path)}
          comparisonMode={comparisonMode}
        />
      ))}
    </div>
  )
}

export default ComparisonGrid
