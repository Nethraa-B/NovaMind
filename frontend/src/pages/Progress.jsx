import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowRight, ChartNoAxesColumnIncreasing, Lightbulb, RotateCw } from 'lucide-react'
import EmptyState from '../components/EmptyState.jsx'
import { api, getApiError } from '../services/api.js'

function formatDate(value) {
  if (!value) return 'Update time unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Update time unavailable' : `Updated ${new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)}`
}

function RecommendationRows({ recommendations }) {
  if (!recommendations.length) return <EmptyState compact icon={Lightbulb} title="No recommendations yet" description="Complete an assessment to get topic-based revision suggestions." />
  return (
    <div className="recommendation-list">
      {recommendations.map((item, index) => (
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

export default function Progress() {
  const [mastery, setMastery] = useState([])
  const [weakTopics, setWeakTopics] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadProgress() {
    setLoading(true)
    setError('')
    try {
      const [masteryResponse, weakResponse, recommendationResponse] = await Promise.all([
        api.getMastery(), api.getWeakTopics(), api.getRecommendations(),
      ])
      setMastery(masteryResponse.mastery || [])
      setWeakTopics(weakResponse.weak_topics || [])
      setRecommendations(recommendationResponse.recommendations || [])
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadProgress() }, [])
  const weakNames = new Set(weakTopics.map((item) => item.topic))

  return (
    <div className="page-stack">
      {error && <div className="error-banner"><AlertCircle size={16} /><span>{error}</span><button className="button button-link" onClick={loadProgress}><RotateCw size={14} /> Retry</button></div>}
      <div className="progress-page-grid">
        <section>
          <div className="section-heading"><div><h2>Mastery by topic</h2><p>Scores reflect the backend learner model.</p></div><button className="button button-secondary" onClick={loadProgress} disabled={loading}><RotateCw size={14} className={loading ? 'spinner' : ''} /> Refresh</button></div>
          <div className="panel panel-pad">
            {loading ? <div className="loading-line"><span className="spinner">◌</span> Loading topic progress…</div> : mastery.length ? mastery.map((item) => (
              <div className="progress-item" key={item.topic}>
                <div className="mastery-row-head"><span className="mastery-topic">{item.topic}</span><span className="mastery-score">{Math.round(item.mastery_score)}%</span></div>
                <div className="progress-track"><div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, item.mastery_score))}%` }} /></div>
                <div className="progress-item-foot"><span>{weakNames.has(item.topic) ? 'Among current weak topics' : 'Recorded mastery'}</span><span>{formatDate(item.last_updated)}</span></div>
              </div>
            )) : <EmptyState icon={ChartNoAxesColumnIncreasing} title="No topic scores yet" description="Submit an assessment answer to start recording mastery." action={<Link className="button button-secondary" to="/assessment">Go to practice <ArrowRight size={14} /></Link>} />}
          </div>
        </section>

        <section>
          <div className="section-heading"><div><h2>Revision plan</h2><p>Recommendations returned by NovaMind.</p></div></div>
          <div className="panel panel-pad"><RecommendationRows recommendations={recommendations} /></div>
          <div className="notice-inline" style={{ marginTop: 12 }}><Lightbulb size={14} /> Weak-topic ordering is supplied by the learner API; recommendations are linked to course sources when available.</div>
        </section>
      </div>
    </div>
  )
}