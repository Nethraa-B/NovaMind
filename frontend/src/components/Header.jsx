import { Menu } from 'lucide-react'

export default function Header({ title, description, onMenu }) {
  return (
    <header className="topbar">
      <button className="icon-button menu-button" aria-label="Open navigation" onClick={onMenu}>
        <Menu size={20} />
      </button>
      <div className="topbar-heading">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="topbar-tools">
        <div className="api-indicator"><span className="api-dot" /> Local workspace</div>
        <div className="user-avatar" aria-label="NovaMind learner">NM</div>
      </div>
    </header>
  )
}