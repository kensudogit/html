// 環境変数の型安全な取得

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

export const getApiBaseUrl = (): string => {
  const apiUrl = import.meta.env.VITE_API_URL
  
  if (apiUrl) {
    return apiUrl
  }
  
  // 開発環境のデフォルト
  if (import.meta.env.DEV) {
    return 'http://localhost:5000'
  }
  
  // 本番環境では現在のオリジンを使用
  return window.location.origin
}

export const API_BASE_URL = getApiBaseUrl()
