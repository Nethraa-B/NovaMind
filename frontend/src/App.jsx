import { useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Header from './components/Header.jsx'
import Sidebar from './components/Sidebar.jsx'
import Assistant from './pages/Assistant.jsx'
import Assessment from './pages/Assessment.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Materials from './pages/Materials.jsx'
import Progress from './pages/Progress.jsx'

const pageDetails = {
  '/': ['Overview', 'Your course library and learning activity, in one place.'],
  '/materials': ['Course materials', 'Manage the sources NovaMind uses to ground your learning.'],
  '/assistant': ['Learning assistant', 'Ask questions grounded in your uploaded course material.'],
  '/assessment': ['Practice assessment', 'Check your understanding with questions drawn from course sources.'],
  '/progress': ['Learning progress', 'Review mastery by topic and choose what to revisit next.'],
}

export default function App() {
  const [navigationOpen, setNavigationOpen] = useState(false)
  const location = useLocation()
  const [title, description] = pageDetails[location.pathname] || pageDetails['/']

  return (
    <div className="app-shell">
      <Sidebar open={navigationOpen} onClose={() => setNavigationOpen(false)} />
      <div className="app-main">
        <Header title={title} description={description} onMenu={() => setNavigationOpen(true)} />
        <main className="page-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/materials" element={<Materials />} />
            <Route path="/assistant" element={<Assistant />} />
            <Route path="/assessment" element={<Assessment />} />
            <Route path="/progress" element={<Progress />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}