import { useEffect, useRef, useState } from 'react'
import { BookOpenText, CircleAlert, FileText, LoaderCircle, Send } from 'lucide-react'
import { api, getApiError } from '../services/api.js'

const suggestions = [
  'Explain ACID properties using a bank transfer example.',
  'How does a primary key differ from a foreign key?',
  'What does the uploaded material say about transaction isolation?',
]

export default function Assistant() {
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, sending])

  async function ask(value = question) {
    const prompt = value.trim()
    if (!prompt || sending) return
    setQuestion('')
    setError('')
    setMessages((current) => [...current, { id: `${Date.now()}-user`, role: 'user', content: prompt }])
    setSending(true)
    try {
      const response = await api.ask(prompt)
      setMessages((current) => [...current, {
        id: `${Date.now()}-assistant`, role: 'assistant', content: response.answer,
        supported: response.supported, citations: response.citations || [],
      }])
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setSending(false)
    }
  }

  function submit(event) {
    event.preventDefault()
    ask()
  }

  return (
    <div className="page-stack">
      {error && <div className="error-banner"><CircleAlert size={16} /><span>{error}</span></div>}
      <section className="panel chat-shell" aria-label="Course-grounded learning assistant">
        <div className="chat-messages" aria-live="polite">
          {!messages.length && !sending && (
            <div className="chat-empty">
              <div className="empty-state-icon"><BookOpenText size={23} /></div>
              <h2>What are you working through?</h2>
              <p>Ask about uploaded course content. Responses show the source locations returned by the backend; if there is not enough evidence, the assistant will say so.</p>
              <div className="prompt-suggestions">{suggestions.map((suggestion) => <button className="prompt-chip" key={suggestion} onClick={() => ask(suggestion)}>{suggestion}</button>)}</div>
            </div>
          )}
          {messages.map((message) => (
            <div className={`chat-message chat-message-${message.role}`} key={message.id}>
              <div className="chat-role">{message.role === 'user' ? 'You' : message.supported ? 'NovaMind · Source-grounded' : 'NovaMind · Unsupported'}</div>
              <div className={`chat-bubble${message.supported === false ? ' chat-bubble-unsupported' : ''}`}>{message.content}</div>
              {message.citations?.length > 0 && <div className="citation-list">{message.citations.map((citation, index) => <span className="citation-tag" key={`${citation.source_name}-${citation.location}-${index}`}><FileText size={12} />{citation.source_name} · {citation.location}</span>)}</div>}
            </div>
          ))}
          {sending && <div className="chat-message chat-message-assistant"><div className="chat-role">NovaMind</div><div className="chat-bubble"><LoaderCircle size={14} className="spinner" style={{ verticalAlign: 'middle', marginRight: 7 }} />Searching your course sources…</div></div>}
          <div ref={bottomRef} />
        </div>
        <form className="chat-composer" onSubmit={submit}>
          <div className="composer-inner">
            <label className="screen-reader-only" htmlFor="assistant-question">Ask a question</label>
            <textarea id="assistant-question" className="composer-textarea" rows="1" maxLength="2000" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(event) } }} placeholder="Ask a question about your course material…" />
            <button className="composer-send" aria-label="Send question" type="submit" disabled={!question.trim() || sending}><Send size={16} /></button>
          </div>
          <div className="composer-note">Answers depend on retrieved course evidence. Citations identify returned source locations.</div>
        </form>
      </section>
    </div>
  )
}