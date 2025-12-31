// 型定義ファイル

export type FileType = 'html' | 'css' | 'other'

export interface ComparisonFile {
  name: string
  path: string
  size: number
  type: FileType
  relatedFiles?: string[] // 関連ファイル（HTMLの場合はCSS、CSSの場合はHTML）
}

export type LayoutMode = 'grid' | 'horizontal' | 'vertical'

export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  error?: string
  files?: ComparisonFile[]
  content?: string
  count?: number
}

export interface LoadFilesResponse extends ApiResponse {
  files: ComparisonFile[]
  count: number
}

export interface LoadFileContentResponse extends ApiResponse {
  content: string
  filename: string
}

export interface ComparisonResult {
  differences: number
  htmlDifferences?: number
  cssDifferences?: number
  details: Array<{
    type: 'missing' | 'extra' | 'different'
    path: string
    element?: string
    element1?: unknown
    element2?: unknown
    fileType?: 'html' | 'css'
  }>
}

export interface CSSRule {
  selector: string
  properties: Record<string, string>
  media?: string
}

export interface CSSComparison {
  rules: CSSRule[]
  differences: Array<{
    selector: string
    type: 'missing' | 'extra' | 'different'
    properties?: Record<string, { old?: string; new?: string }>
  }>
}

export interface CompareScreensResponse extends ApiResponse {
  comparison: Record<string, ComparisonResult>
  base_file: string
}
