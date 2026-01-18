// HTMLエディタ用API通信サービス

import axios, { AxiosError } from 'axios'
import { API_BASE_URL } from '../config/env'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// FormDataの場合はContent-Typeを自動設定
apiClient.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

// レスポンスインターセプター
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const message = (error.response.data as { error?: string })?.error || error.message
      return Promise.reject(new Error(message))
    } else if (error.request) {
      return Promise.reject(new Error('サーバーに接続できませんでした'))
    } else {
      return Promise.reject(new Error(error.message || 'リクエストの送信に失敗しました'))
    }
  }
)

export const editorApi = {
  /**
   * ファイルをアップロード
   */
  async uploadFile(file: File): Promise<{ success: boolean; filename?: string; error?: string }> {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await apiClient.post<{ success: boolean; filename?: string; error?: string }>(
        '/upload',
        formData
      )
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('ファイルのアップロードに失敗しました')
    }
  },

  /**
   * ファイルを読み込む
   */
  async loadFile(filename: string): Promise<{ success: boolean; content?: string; error?: string }> {
    try {
      const response = await apiClient.get<{ success: boolean; content?: string; error?: string }>(
        `/load/${encodeURIComponent(filename)}`
      )
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('ファイルの読み込みに失敗しました')
    }
  },

  /**
   * コンテンツを保存
   */
  async saveContent(content: string): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await apiClient.post<{ success: boolean; error?: string }>('/save', {
        content,
      })
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('ファイルの保存に失敗しました')
    }
  },

  /**
   * 現在のコンテンツを取得
   */
  async getContent(): Promise<{ success: boolean; content?: string; error?: string }> {
    try {
      const response = await apiClient.get<{ success: boolean; content?: string; error?: string }>('/content')
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('コンテンツの取得に失敗しました')
    }
  },

  /**
   * 構造情報を取得
   */
  async getStructure(): Promise<{ success: boolean; info?: any; error?: string }> {
    try {
      const response = await apiClient.get<{ success: boolean; info?: any; error?: string }>('/structure')
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('構造情報の取得に失敗しました')
    }
  },

  /**
   * HTMLを検証
   */
  async validateHTML(content: string): Promise<{ success: boolean; errors?: any[]; error?: string }> {
    try {
      const response = await apiClient.post<{ success: boolean; errors?: any[]; error?: string }>('/validate', {
        content,
      })
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('HTMLの検証に失敗しました')
    }
  },

  /**
   * 要素を検索（HTML）
   */
  async searchElement(query: string): Promise<{ success: boolean; results?: any[]; error?: string }> {
    try {
      const response = await apiClient.post<{ success: boolean; results?: any[]; error?: string }>('/search', {
        query,
        type: 'html',
      })
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('要素の検索に失敗しました')
    }
  },

  /**
   * Excelファイルを検索
   */
  async searchExcelFiles(query: string, folderPath?: string): Promise<{ success: boolean; results?: any[]; total_files?: number; matched_files?: number; error?: string }> {
    try {
      const response = await apiClient.post<{ success: boolean; results?: any[]; total_files?: number; matched_files?: number; error?: string }>('/search', {
        query,
        type: 'excel',
        folder_path: folderPath || '',
      })
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('Excelファイルの検索に失敗しました')
    }
  },

  /**
   * ファイル一覧を取得
   */
  async getFiles(): Promise<{ success: boolean; files?: Array<{ name: string; size: number }>; error?: string }> {
    try {
      const response = await apiClient.get<{ success: boolean; files?: Array<{ name: string; size: number }>; error?: string }>('/files')
      return response.data
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('ファイル一覧の取得に失敗しました')
    }
  },
}
