import { Activity, ArrowRight, FileText, History, ScanSearch, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchAnalysisHistory } from '../lib/api'
import { clearAccessToken, getAccessToken, getCurrentUser } from '../lib/auth'
import { Button } from '../components/ui/Button'
import { AsyncState } from '../components/ui/AsyncState'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { MetricCard } from '../components/ui/MetricCard'

function formatCreatedAt(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString()
}

function signalLabel(signal) {
  return signal?.status === 'available' ? signal?.result?.label ?? signal?.result?.classification ?? 'Available' : 'Unavailable'
}

const reviewSteps = [
  ['01', 'Submit an authorized image', 'The server validates the selected file before analysis begins.'],
  ['02', 'Inspect available evidence', 'Model signals and supporting evidence remain visibly separated.'],
  ['03', 'Use context for review', 'A Trust Score supports a decision; it is not a verdict.'],
]

export function DashboardPage() {
  const currentUser = getCurrentUser()
  const [historyState, setHistoryState] = useState({ status: 'loading', items: [] })
  const scoredItems = historyState.items.filter((item) => Number.isFinite(item?.trust_score?.score))
  const averageScore = scoredItems.length ? Math.round(scoredItems.reduce((sum, item) => sum + item.trust_score.score, 0) / scoredItems.length) : null
  const reviewCount = scoredItems.filter((item) => item.trust_score.category === 'Needs Review').length
  const recentItems = historyState.items.slice(0, 3)

  async function retryRecentActivity() {
    setHistoryState((current) => ({ ...current, status: 'loading' }))
    try {
      const data = await fetchAnalysisHistory(getAccessToken())
      setHistoryState({ status: 'ready', items: data.items })
    } catch (error) {
      if (error.status === 401) {
        clearAccessToken()
        setHistoryState({ status: 'unauthorized', items: [] })
        return
      }
      setHistoryState({ status: 'error', items: [] })
    }
  }

  useEffect(() => {
    let isCurrent = true

    async function loadInitialActivity() {
      try {
        const data = await fetchAnalysisHistory(getAccessToken())
        if (isCurrent) setHistoryState({ status: 'ready', items: data.items })
      } catch (error) {
        if (!isCurrent) return
        if (error.status === 401) {
          clearAccessToken()
          setHistoryState({ status: 'unauthorized', items: [] })
          return
        }
        setHistoryState({ status: 'error', items: [] })
      }
    }

    loadInitialActivity()
    return () => { isCurrent = false }
  }, [])

  return (
    <main className="app-page dashboard-page" aria-labelledby="dashboard-title">
      <header className="dashboard-hero">
        <div>
          <p className="eyebrow">Private workspace</p>
          <h1 id="dashboard-title">{currentUser?.name ? `Welcome back, ${currentUser.name}` : 'Your image review workspace'}</h1>
          <p className="lede">Review your returned image evidence, keep recent analyses in context, and begin a new server-backed assessment.</p>
        </div>
        <div className="dashboard-hero__actions"><Link aria-label="Analyze an image" className="primary-link dashboard-hero__action" to="/analyze">Analyze new image <ArrowRight aria-hidden="true" size={17} /></Link><Link className="secondary-link" to="/history">View history</Link></div>
      </header>
      <aside className="dashboard-pipeline-summary" aria-label="TrustLens analysis architecture"><Activity aria-hidden="true" size={21} /><div><strong>Multimodal analysis</strong><span>Image → AI signals → evidence → Trust Score</span></div><p>Conceptual architecture; results remain server-derived.</p></aside>
      <section className="dashboard-kpis" aria-label="Workspace summary">
        <MetricCard detail="Current owner-scoped API response (up to 20)" icon={ScanSearch} label="Loaded analyses" value={historyState.status === 'ready' ? historyState.items.length : null} />
        <MetricCard detail="Available server-derived scores only" icon={ShieldCheck} label="Average Trust Score" value={historyState.status === 'ready' && averageScore !== null ? `${averageScore}/100` : null} />
        <MetricCard detail="Available server categories only" icon={Activity} label="Needs Review" value={historyState.status === 'ready' ? reviewCount : null} />
      </section>
      <section className="dashboard-review-guide" aria-labelledby="review-guide-title">
        <div className="dashboard-review-guide__intro">
          <p className="eyebrow">A focused review process</p>
          <h2 id="review-guide-title">Start with evidence, then make the call.</h2>
          <p>TrustLens brings available technical signals into one private workspace while keeping uncertainty visible for careful human review.</p>
        </div>
        <ol className="dashboard-review-guide__steps">
          {reviewSteps.map(([number, title, detail]) => <li key={number}><span>{number}</span><div><strong>{title}</strong><p>{detail}</p></div></li>)}
        </ol>
        <aside className="dashboard-review-guide__note">
          <ShieldCheck aria-hidden="true" size={22} />
          <div><strong>Evidence, not a verdict</strong><p>TrustLens does not establish authenticity, fraud, provenance, ownership, or intent.</p></div>
        </aside>
      </section>

      <section className="dashboard-actions" aria-label="Workspace actions">
        <article className="dashboard-action-card">
          <ScanSearch aria-hidden="true" className="dashboard-action-card__icon" size={22} />
          <p className="eyebrow">New review</p>
          <h2>Start an analysis</h2>
          <p>Uploads are processed by the server. Returned signals are decision support, not a conclusion.</p>
          <Link className="secondary-link" to="/analyze">Choose an image <ArrowRight aria-hidden="true" size={16} /></Link>
        </article>
        <article className="dashboard-action-card">
          <FileText aria-hidden="true" className="dashboard-action-card__icon" size={22} />
          <p className="eyebrow">Your records</p>
          <h2>Continue your review</h2>
          <p>Return to owner-scoped analysis history or download reports generated from completed records.</p>
          <div className="dashboard-action-card__links">
            <Link to="/history"><History aria-hidden="true" size={16} />View history</Link>
            <Link to="/reports"><FileText aria-hidden="true" size={16} />View reports</Link>
          </div>
        </article>
      </section>

      <section className="dashboard-recent" aria-labelledby="recent-title">
        <div className="dashboard-section-heading">
          <div>
            <p className="eyebrow">Recent activity</p>
            <h2 id="recent-title">Your latest analyses</h2>
          </div>
          {historyState.status === 'ready' && recentItems.length > 0 && <Link to="/history">View all history</Link>}
        </div>

        {historyState.status === 'loading' && <LoadingSkeleton className="dashboard-state" label="Loading your recent analyses" lines={3} />}
        {historyState.status === 'error' && (
          <AsyncState actions={<Button onClick={retryRecentActivity} variant="secondary">Try again</Button>} announcement="Unable to load recent analyses. Try again." className="dashboard-state" kind="error" title="Unable to load recent analyses." />
        )}
        {historyState.status === 'unauthorized' && (
          <AsyncState actions={<Link className="secondary-link" to="/login">Sign in</Link>} announcement="Your session has expired. Sign in to load recent analyses." className="dashboard-state" kind="unauthorized" title="Your session has expired.">
            Sign in to load your recent analyses.
          </AsyncState>
        )}
        {historyState.status === 'ready' && recentItems.length === 0 && (
          <AsyncState actions={<Link className="secondary-link" to="/analyze">Start an analysis</Link>} announcement="No analyses are available yet." className="dashboard-state" kind="empty" title="No analyses yet">
            No analyses yet. Start an image review when you are ready.
          </AsyncState>
        )}
        {historyState.status === 'ready' && recentItems.length > 0 && (
          <ul className="dashboard-recent-list">
            {recentItems.map((item) => (
              <li key={item.id}>
                <div>
                  <span className="dashboard-recent-list__record-icon"><ShieldCheck aria-hidden="true" size={17} /></span>
                  <strong>{item.filename || `Analysis ${item.id}`}</strong>
                  <span>{formatCreatedAt(item.created_at)}</span>
                </div>
                <div className="dashboard-recent-list__evidence"><span>Trust Score: {Number.isFinite(item?.trust_score?.score) ? `${item.trust_score.score}/100` : 'Unavailable'}</span><span>Tampering: {signalLabel(item.signals?.tampering)}</span><span>AI: {signalLabel(item.signals?.ai_generation)}</span></div>
                <Link state={{ analysis: item }} to={`/results/${item.id}`}>View results <ArrowRight aria-hidden="true" size={15} /></Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
