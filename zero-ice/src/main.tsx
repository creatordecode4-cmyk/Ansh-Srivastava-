import React from 'react'
import ReactDOM from 'react-dom/client'
import '@fontsource/barlow-condensed/600.css'
import '@fontsource/barlow-condensed/700.css'
import '@fontsource/barlow-condensed/800.css'
import '@fontsource/barlow-condensed/800-italic.css'
import '@fontsource/barlow-condensed/900-italic.css'
import '@fontsource-variable/inter'
import './index.css'
import App from './App'

// tiny path switch: /showcase is the standalone ZERO BOOK scene, everything else is the site
const Showcase = React.lazy(() => import('./showcase/Showcase'))
const isShowcase = window.location.pathname.replace(/\/+$/, '') === '/showcase'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isShowcase ? (
      <React.Suspense fallback={null}>
        <Showcase />
      </React.Suspense>
    ) : (
      <App />
    )}
  </React.StrictMode>,
)
