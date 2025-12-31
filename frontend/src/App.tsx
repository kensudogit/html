import React from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import ScreenComparison from './components/ScreenComparison'
import './App.css'

function App() {
  return (
    <ErrorBoundary>
      <div className="app">
        <ScreenComparison />
      </div>
    </ErrorBoundary>
  )
}

export default App
