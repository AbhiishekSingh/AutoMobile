import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/style.css'
import api from './lib/api'
import { installFieldErrors } from './lib/fieldErrors'
installFieldErrors(api)

// A screen error must never leave a blank white page: show what happened and a way back.
class ErrorBoundary extends React.Component {
  state = { err: null }
  static getDerivedStateFromError(err) { return { err } }
  render() {
    if (!this.state.err) return this.props.children
    return (
      <div style={{ maxWidth: 560, margin: '80px auto', padding: 24, fontFamily: 'sans-serif' }}>
        <h2>Something went wrong on this screen</h2>
        <p style={{ color: '#a52a2a' }}>{String(this.state.err?.message || this.state.err)}</p>
        <p>Your data is safe. Please go back and try again; if it keeps happening, send this message to the developer.</p>
        <button onClick={() => { window.location.href = '/' }}>Back to home</button>
      </div>)
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary><App /></ErrorBoundary>
  </React.StrictMode>
)
