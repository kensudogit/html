import React from 'react'
import './ErrorMessage.css'

interface ErrorMessageProps {
  message: string
  onClose?: () => void
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onClose }) => {
  return (
    <div className="error-message" role="alert">
      <div className="error-message-content">
        <span className="error-icon">⚠️</span>
        <span className="error-text">{message}</span>
        {onClose && (
          <button
            className="error-close"
            onClick={onClose}
            aria-label="エラーメッセージを閉じる"
          >
            ×
          </button>
        )}
      </div>
    </div>
  )
}

export default ErrorMessage
