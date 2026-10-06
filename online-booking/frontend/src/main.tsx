import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// Expose build ID to window so it survives tree-shaking
declare global {
  interface Window {
    __BUILD_ID__: string
  }
}
window.__BUILD_ID__ = __BUILD_ID__

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)