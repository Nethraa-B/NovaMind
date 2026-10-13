import { useState } from 'react'
import { AlertCircle, ArrowRight, CheckCircle2, CircleHelp, RotateCw, XCircle } from 'lucide-react'
import EmptyState from '../components/EmptyState.jsx'
import { api, getApiError } from '../services/api.js'

function SourceReference({ value }) {
  const [source, location] = (value || '').split('|').map((part) => part.trim())
  if (!source && !location) return <span className="source-reference">Source unavailable</span>
  return <span className="source-reference">Source: {[source, location].filter(Boolean).join(' · ')}</span>
}

export default function Assessment() {
  const [topic, setTopic] = useState('')
  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState({})
  const [results, setResults] = useState({})
  const [loading, setLoading] = useState(false)
  const [submittingId, setSubmittingId] = useState(null)
  const [error, setError] = useState('')

  async function generate(event) {
    event?.preventDefault()
    setLoading(true)
    setError('')
    setQuestions([])
    setAnswers({})
    setResults({})
    try {
      const response = await api.generateAssessment(topic.trim() || null, 5)
      setQuestions(response.questions || [])
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setLoading(false)
    }
  }

  async function submit(question) {
    const answer = (answers[question.id] || '').trim()
    if (!answer || results[question.id]) return
    setSubmittingId(question.id)
    setError('')
    try {
      const result = await api.submitAssessment(question.id, answer)
      setResults((current) => ({ ...current, [question.id]: result }))
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setSubmittingId(null)
    }
  }

  function setAnswer(questionId, value) {
    setAnswers((current) => ({ ...current, [questionId]: value }))
  }

  return (
    <div className="page-stack">
      {error && <div className="error-banner"><AlertCircle size={16} /><span>{error}</span></div>}
      <section className="panel panel-pad">
        <div className="section-heading"><div><h2>Build a practice set</h2><p>Questions are generated from topics and source chunks available in your course library.</p></div></div>
        <form className="assessment-toolbar" onSubmit={generate}>
          <div className="assessment-topic-field"><label className="field-label" htmlFor="assessment-topic">Topic <span className="muted" style={{ fontWeight: 400 }}>(optional)</span></label><input id="assessment-topic" className="text-input" maxLength="100" value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="e.g. Transactions and Concurrency" /></div>
          <button className="button button-primary" type="submit" disabled={loading}>{loading ? <><span className="spinner">◌</span> Generating…</> : <><RotateCw size={14} /> Generate questions</>}</button>
        </form>
      </section>

      {!questions.length && !loading && (
        <div className="panel">
          <EmptyState icon={CircleHelp} title="No practice questions loaded" description="Generate questions from uploaded material. If no matching source content exists, the backend may return an empty set." />
        </div>
      )}

      {questions.map((question, index) => {
        const result = results[question.id]
        const isChoice = question.question_type === 'mcq' && Array.isArray(question.options) && question.options.length > 0
        return (
          <article className="panel assessment-question" key={question.id ?? `${question.topic}-${index}`}>
            <div className="question-topline">
              <span className="question-tag">{question.topic}</span>
              <span className="question-tag question-tag-neutral">{question.concept}</span>
              <span className="question-tag question-tag-neutral">{question.difficulty}</span>
              <span className="question-tag question-tag-neutral">{question.question_type}</span>
            </div>
            <h2 className="question-text">{index + 1}. {question.question_text}</h2>
            {isChoice ? (
              <div className="question-options">
                {question.options.map((option) => (
                  <label className={`option-label${answers[question.id] === option ? ' option-label-selected' : ''}`} key={option}>
                    <input type="radio" name={`question-${question.id}`} value={option} checked={answers[question.id] === option} disabled={Boolean(result)} onChange={() => setAnswer(question.id, option)} />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            ) : (
              <div><label className="field-label" htmlFor={`answer-${question.id}`}>{question.question_type === 'numerical' ? 'Your numerical answer' : 'Your answer'}</label><textarea id={`answer-${question.id}`} className="text-area" value={answers[question.id] || ''} disabled={Boolean(result)} onChange={(event) => setAnswer(question.id, event.target.value)} placeholder="Write your response…" /></div>
            )}

            <div className="question-footer">
              <SourceReference value={question.source_reference} />
              {!result && <button className="button button-primary" disabled={!answers[question.id]?.trim() || submittingId === question.id} onClick={() => submit(question)}>{submittingId === question.id ? <><span className="spinner">◌</span> Checking…</> : <>Submit answer <ArrowRight size={14} /></>}</button>}
            </div>

            {result && (
              <div className={`result-panel ${result.correctness ? 'result-correct' : 'result-incorrect'}`}>
                <div className="result-heading">{result.correctness ? <CheckCircle2 size={16} /> : <XCircle size={16} />}{result.correctness ? 'Correct' : 'Review this answer'} · {Math.round(result.score * 100)}%</div>
                <p className="result-copy">{result.explanation}</p>
                {!result.correctness && result.correct_answer && <p className="result-copy"><span className="result-answer">Answer key:</span> {result.correct_answer}</p>}
                <p className="result-copy">{result.source_grounded_feedback}</p>
                {result.misconception_detected && <p className="result-copy result-misconception"><span className="result-answer">Concept to revisit:</span> {result.misconception_detected}</p>}
                {result.citations?.length > 0 && <div className="citation-list">{result.citations.map((citation, citationIndex) => <span className="citation-tag" key={`${citation.source_name}-${citation.location}-${citationIndex}`}>{citation.source_name} · {citation.location}</span>)}</div>}
              </div>
            )}
          </article>
        )
      })}
    </div>
  )
}