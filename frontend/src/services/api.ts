// API通信サービス

import axios, { AxiosError } from 'axios'
import { API_BASE_URL } from '../config/env'
import type {
  ComparisonFile,
  LoadFilesResponse,
  LoadFileContentResponse,
  CompareScreensResponse,
} from '../types'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30秒
  headers: {
    'Content-Type': 'application/json',
  },
})

// レスポンスインターセプター
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      // サーバーからのエラーレスポンス
      const message = (error.response.data as { error?: string })?.error || error.message
      return Promise.reject(new Error(message))
    } else if (error.request) {
      // リクエストは送信されたが、レスポンスが受信されなかった
      return Promise.reject(new Error('サーバーに接続できませんでした'))
    } else {
      // リクエストの設定中にエラーが発生
      return Promise.reject(new Error(error.message || 'リクエストの送信に失敗しました'))
    }
  }
)

export const apiService = {
  /**
   * 比較用ファイルリストを読み込む（HTMLとCSSを含む）
   */
  async loadComparisonFiles(directory: string): Promise<ComparisonFile[]> {
    if (!directory.trim()) {
      throw new Error('ディレクトリパスを入力してください')
    }

    try {
      const response = await apiClient.post<LoadFilesResponse>('/api/load-comparison-files', {
        directory: directory.trim(),
      })

      if (response.data.success && response.data.files) {
        // HTMLファイルを優先し、最大27ファイル
        const htmlFiles = response.data.files.filter(f => f.type === 'html')
        const cssFiles = response.data.files.filter(f => f.type === 'css')
        
        // HTMLファイルを最大27個まで、関連するCSSも含める
        const result: ComparisonFile[] = []
        const addedCss = new Set<string>()
        
        for (const htmlFile of htmlFiles.slice(0, 27)) {
          result.push(htmlFile)
          // 関連するCSSファイルも追加
          if (htmlFile.relatedFiles) {
            for (const cssPath of htmlFile.relatedFiles) {
              if (!addedCss.has(cssPath)) {
                const cssFile = cssFiles.find(f => f.path === cssPath)
                if (cssFile) {
                  result.push(cssFile)
                  addedCss.add(cssPath)
                }
              }
            }
          }
        }
        
        return result
      } else {
        throw new Error(response.data.error || 'ファイルの読み込みに失敗しました')
      }
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('ファイルの読み込み中にエラーが発生しました')
    }
  },

  /**
   * ファイルの内容を読み込む
   */
  async loadFileContent(filePath: string): Promise<string> {
    try {
      const response = await apiClient.get<LoadFileContentResponse>('/api/load-file-content', {
        params: { path: filePath },
      })

      if (response.data.success && response.data.content) {
        return response.data.content
      } else {
        throw new Error(response.data.error || 'ファイル内容の読み込みに失敗しました')
      }
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('ファイル内容の読み込み中にエラーが発生しました')
    }
  },

  /**
   * 複数の画面を比較
   */
  async compareScreens(filePaths: string[]): Promise<CompareScreensResponse> {
    if (filePaths.length < 2) {
      throw new Error('2つ以上のファイルを指定してください')
    }

    try {
      const response = await apiClient.post<CompareScreensResponse>('/api/compare-screens', {
        files: filePaths,
      })

      if (response.data.success) {
        return response.data
      } else {
        throw new Error(response.data.error || '画面の比較に失敗しました')
      }
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('画面の比較中にエラーが発生しました')
    }
  },

  /**
   * 比較レポートをエクスポート
   */
  async exportComparisonReport(files: Array<{ name: string; path: string }>): Promise<string> {
    if (files.length < 2) {
      throw new Error('2つ以上のファイルを指定してください')
    }

    try {
      const response = await apiClient.post<{ success: boolean; report?: string; error?: string }>(
        '/api/export-comparison-report',
        { files }
      )

      if (response.data.success && response.data.report) {
        return response.data.report
      } else {
        throw new Error(response.data.error || 'レポートの生成に失敗しました')
      }
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('レポートのエクスポート中にエラーが発生しました')
    }
  },
}
