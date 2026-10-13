import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarClock,
  ChartNoAxesColumnIncreasing,
  CircleAlert,
  FileText,
  Lightbulb,
  MessageSquareText,
  RotateCw,
} from 'lucide-react'
import EmptyState from '../components/EmptyState.jsx'
import { api, getApiError } from '../services/api.js'

function StatCard({ icon: Icon, label, value, note }) {
  return (
    <div className="stat-card">
      <div className="stat-top"><span>{label}</span><span className="stat-icon"><Icon size={16} /></span></div>
      <div className="stat-value">{value}</div>
      <div className="stat-note">{note}</div>
    </div>
  )
}

function RecommendationList({ recommendations }) {
  if (!recommendations.length) {
    return <EmptyState compact icon={Lightbulb} title="No recommendations yet" description="Recommendations appear after the backend has mastery results for your topics." />
  }
  return (
    <div className="recommendation-list">
      {recommendations.slice(0, 3).map((item, index) => (
        <div className="recommendation-row" key={`${item.topic}-${index}`}>
          <div className="recommendation-mark"><Lightbulb size={15} /></div>
          <div>
            <div className="recommendation-title">{item.title}</div>
            <div className="recommendation-detail">{item.detail}</div>
            {(item.source_name || item.location) && <div className="recommendation-source">{[item.source_name, item.location].filter(Boolean).join(' · ')}</div>}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [materials, setMaterials] = useState([])
  const [mastery, setMastery] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadDashboard() {
    setLoading(true)
    setError('')
    try {
      const [materialRows, masteryResponse, recommendationResponse] = await Promise.all([
        api.getMaterials(), api.getMastery(), api.getRecommendations(),
      ])
      setMaterials(materialRows)
      setMastery(masteryResponse.mastery || [])
      setRecommendations(recommendationResponse.recommendations || [])
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadDashboard() }, [])

  const averageMastery = mastery.length
    ? Math.round(mastery.reduce((sum, item) => sum + Number(item.mastery_score || 0), 0) / mastery.length)
    : null

  return (
    <div className="page-stack">
      {error && <div className="error-banner"><CircleAlert size={16} /><span>{error}</span><button className="button button-link" onClick={loadDashboard}><RotateCw size={14} /> Retry</button></div>}

      <section className="welcome-band">
        <div className="welcome-copy">
          <div className="eyebrow">Your study space</div>
          <h2>Learn from your course material, not guesswork.</h2>
          <p>Bring your technical course sources together, ask grounded questions, and use focused practice to find what to study next.</p>
          <Link className="button button-primary" to="/assistant">Continue learning <ArrowRight size={15} /></Link>
        </div>
        <div className="welcome-art" aria-hidden="true"><BookOpen size={54} strokeWidth={1.25} /></div>
      </section>

      <section className="stat-grid" aria-label="Learning summary">
        <StatCard icon={FileText} label="Course materials" value={loading ? '—' : materials.length} note="Uploaded source files" />
        <StatCard icon={ChartNoAxesColumnIncreasing} label="Topics tracked" value={loading ? '—' : mastery.length} note="Topics with mastery results" />
        <StatCard icon={ArrowUpRight} label="Average mastery" value={loading ? '—' : averageMastery === null ? '—' : `${averageMastery}%`} note={averageMastery === null ? 'No assessment results yet' : 'Across topics with recorded mastery'} />
      </section>

      <div className="dashboard-grid">
        <div className="dashboard-main-col">
          <section>
            <div className="section-heading"><div><h2>Topic mastery</h2><p>Recent levels recorded by your assessment submissions.</p></div><Link className="button button-link" to="/progress">View progress <ArrowRight size={14} /></Link></div>
            <div className="panel panel-pad">
              {loading ? <div className="loading-line"><span className="spinner">◌</span> Loading mastery…</div> : mastery.length ? (
                <div className="mastery-list">
                  {mastery.slice(0, 4).map((item) => (
                    <div className="mastery-row" key={item.topic}>
                      <div className="mastery-row-head"><span className="mastery-topic">{item.topic}</span><span className="mastery-score">{Math.round(item.mastery_score)}%</span></div>
                      <div className="progress-track"><div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, item.mastery_score))}%` }} /></div>
                    </div>
                  ))}
                </div>
              ) : <EmptyState compact icon={ChartNoAxesColumnIncreasing} title="No mastery recorded" description="Complete an assessment to see your topic-level progress here." action={<Link className="button button-secondary" to="/assessment">Practice <ArrowRight size={14} /></Link>} />}
            </div>
          </section>

          <section>
            <div className="section-heading"><div><h2>Recent assessment activity</h2><p>Submission history for your study sessions.</p></div></div>
            <div className="panel activity-note"><div className="activity-note-icon"><CalendarClock size={16} /></div><p>Assessment history is not available from the current backend API. Topic mastery and recommendations reflect persisted assessment results.</p></div>
          </section>
        </div>

        <div className="dashboard-side-col">
          <section>
            <div className="section-heading"><div><h2>Recommended next</h2><p>Based on your recorded topic mastery.</p></div></div>
            <div className="panel panel-pad">
              {loading ? <div className="loading-line">Loading recommendations…</div> : <RecommendationList recommendations={recommendations} />}
              <Link to="/progress" className="button button-link" style={{ marginTop: 8 }}>See all progress <ArrowRight size={14} /></Link>
            </div>
          </section>

          <section>
            <div className="section-heading"><div><h2>Quick actions</h2><p>Pick up where your study needs you.</p></div></div>
            <div className="panel panel-pad" style={{ display: 'grid', gap: 9 }}>
              <Link className="button button-secondary button-full" to="/materials"><BookOpen size={15} /> Add course material <ArrowUpRight size={14} /></Link>
              <Link className="button button-secondary button-full" to="/assistant"><MessageSquareText size={15} /> Ask about a concept <ArrowUpRight size={14} /></Link>
              <Link className="button button-secondary button-full" to="/assessment"><ChartNoAxesColumnIncreasing size={15} /> Start a practice check <ArrowUpRight size={14} /></Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}