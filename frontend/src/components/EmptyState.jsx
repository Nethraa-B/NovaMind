import { Inbox } from 'lucide-react'

export default function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  compact = false,
}) {
  return (
    <div className={`empty-state${compact ? ' empty-state-compact' : ''}`}>
      <div className="empty-state-icon"><Icon size={21} strokeWidth={1.8} /></div>
      <div className="empty-state-copy">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {action}
    </div>
  )
}