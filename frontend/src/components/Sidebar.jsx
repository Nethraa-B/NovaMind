import { NavLink } from 'react-router-dom'
import {
  BookOpen,
  ChartNoAxesColumnIncreasing,
  ClipboardCheck,
  LayoutDashboard,
  MessageSquareText,
  X,
} from 'lucide-react'

const navigation = [
  { label: 'Overview', to: '/', icon: LayoutDashboard, end: true },
  { label: 'Materials', to: '/materials', icon: BookOpen },
  { label: 'Learning assistant', to: '/assistant', icon: MessageSquareText },
  { label: 'Practice', to: '/assessment', icon: ClipboardCheck },
  { label: 'Progress', to: '/progress', icon: ChartNoAxesColumnIncreasing },
]

export default function Sidebar({ open, onClose }) {
  return (
    <>
      {open && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={onClose} />}
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark" aria-hidden="true">N</div>
          <div>
            <div className="brand-name">NovaMind</div>
            <div className="brand-caption">Learning workspace</div>
          </div>
          <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="sidebar-section-label">Workspace</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {navigation.map(({ label, to, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) => `nav-link${isActive ? ' nav-link-active' : ''}`}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-course-label">Study focus</div>
          <div className="sidebar-course">
            <div className="course-symbol">DB</div>
            <div>
              <div className="course-title">Database systems</div>
              <div className="course-subtitle">Source-grounded study</div>
            </div>
          </div>
          <div className="sidebar-footer">NovaMind · Personal learning</div>
        </div>
      </aside>
    </>
  )
}