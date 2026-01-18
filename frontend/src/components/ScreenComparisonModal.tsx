import React from 'react'
import ScreenComparison from './ScreenComparison'
import './Modal.css'

interface ScreenComparisonModalProps {
  isOpen: boolean
  onClose: () => void
}

const ScreenComparisonModal: React.FC<ScreenComparisonModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content screen-comparison-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🖼️ 画面比較</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body" style={{ padding: 0, overflow: 'auto', maxHeight: '90vh' }}>
          <ScreenComparison />
        </div>
      </div>
    </div>
  )
}

export default ScreenComparisonModal
