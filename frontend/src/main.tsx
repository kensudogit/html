import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// ブラウザ拡張機能関連のエラーを抑制
window.addEventListener('unhandledrejection', (event) => {
  const errorMessage = event.reason?.message || event.reason?.toString() || '';
  const errorSource = event.reason?.source || '';
  
  // ブラウザ拡張機能関連のエラーを抑制
  if (
    errorMessage.includes('message port closed') ||
    errorMessage.includes('message channel closed') ||
    errorMessage.includes('Extension context invalidated') ||
    errorMessage.includes('Receiving end does not exist') ||
    errorMessage.includes('asynchronous response') ||
    errorSource.includes('content.js') ||
    errorSource.includes('extension') ||
    errorSource.includes('chrome-extension') ||
    errorSource.includes('moz-extension')
  ) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    return false;
  }
}, true); // capture phaseで早期にキャッチ

window.addEventListener('error', (event) => {
  const errorMessage = event.message || '';
  const errorSource = event.filename || '';
  
  // ブラウザ拡張機能関連のエラーを抑制
  if (
    errorMessage.includes('message port closed') ||
    errorMessage.includes('message channel closed') ||
    errorMessage.includes('Extension context invalidated') ||
    errorMessage.includes('Receiving end does not exist') ||
    errorMessage.includes('asynchronous response') ||
    errorSource.includes('content.js') ||
    errorSource.includes('extension') ||
    errorSource.includes('chrome-extension') ||
    errorSource.includes('moz-extension') ||
    errorMessage.includes('SVG attribute') ||
    errorMessage.includes('Expected length') ||
    // jQuery関連のエラーを抑制（HTMLコンテンツ内でjQueryが使用されている場合）
    errorMessage.includes('$ is not defined') ||
    errorMessage.includes('jQuery is not defined') ||
    errorSource.includes('about:srcdoc')
  ) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    return false;
  }
}, true); // capture phaseで早期にキャッチ

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
