import ErrorBoundary from './components/ErrorBoundary'
import HTMLEditor from './components/HTMLEditor'
import './App.css'

function App() {
  return (
    <ErrorBoundary>
      <div className="app">
        <HTMLEditor />
      </div>
    </ErrorBoundary>
  )
}

export default App
