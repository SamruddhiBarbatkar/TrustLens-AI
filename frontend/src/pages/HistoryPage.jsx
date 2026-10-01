import { ArrowRight, CalendarDays, FileText, History, ScanSearch } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchAnalysisHistory } from '../lib/api'
import { clearAccessToken, getAccessToken } from '../lib/auth'
import { Button } from '../components/ui/Button'
import { AsyncState } from '../components/ui/AsyncState'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { PageHeader } from '../components/ui/PageHeader'
import { StatusIndicator } from '../components/ui/StatusIndicator'

const signalNames = {
  ai_generation: 'AI-generated detection',
  ela: 'Error level analysis',
  ocr: 'OCR',
  quality: 'Image quality',
  tampering: 'Tampering detection',
}

function statusVariant(status) {
  if (status === 'available') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'unavailable') return 'unavailable'
  return 'neutral'
}

function formatCreatedAt(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString()
}

function signalName(name) {
  return signalNames[name] ?? name.replaceAll('_', ' ')
}

function scoreStatus(category) {
  if (category === 'Likely Authentic') return 'success'
  if (category === 'Needs Review') return 'warning'
  if (category === 'Potentially Suspicious') return 'error'
  return 'neutral'
}

async function requestHistory() {
  return fetchAnalysisHistory(getAccessToken())
}

export function HistoryPage() {
  const [state, setState] = useState({ status: 'loading', items: [] })

  useEffect(() => {
    let isCurrent = true

    async function loadInitialHistory() {
      try {
        const data = await requestHistory()
        if (isCurrent) setState({ status: 'ready', items: data.items })
      } catch (error) {
        if (!isCurrent) return
        if (error.status === 401) {
          clearAccessToken()
          setState({ status: 'unauthorized', items: [] })
          return
        }
        setState({ status: 'error', items: [] })
      }
    }

    loadInitialHistory()
    return () => { isCurrent = false }
  }, [])

  async function retry() {
    setState((current) => ({ ...current, status: 'loading' }))
    try {
      const data = await requestHistory()
      setState({ status: 'ready', items: data.items })
    } catch (error) {
      if (error.status === 401) {
        clearAccessToken()
        setState({ status: 'unauthorized', items: [] })
        return
      }
      setState({ status: 'error', items: [] })
    }
  }

  return (
    <main className="app-page history-page" aria-labelledby="history-title">
      <PageHeader
        actions={<Link className="primary-link history-page__action" to="/analyze">Analyze an image <ArrowRight aria-hidden="true" size={17} /></Link>}
        className="history-page__header"
        eyebrow="Private workspace"
        title="Analysis history"
        titleId="history-title"
      >
        <p className="lede">Review analyses saved to your account. Each record shows only the evidence returned by the server.</p>
      </PageHeader>

      {state.status === 'loading' && <LoadingSkeleton className="history-state history-state--loading" label="Loading your analysis history" lines={4} />}
      {state.status === 'unauthorized' && (
        <AsyncState actions={<Link className="secondary-link" to="/login">Sign in</Link>} announcement="Your session has expired. Sign in to view your history." kind="unauthorized" title="Your session has expired.">
          Sign in to view your history.
        </AsyncState>
      )}
      {state.status === 'error' && (
        <AsyncState actions={<Button onClick={retry} variant="secondary">Try again</Button>} announcement="Analysis history could not be loaded. Try again." className="history-state" kind="error" title="Unable to load analysis history." />
      )}
      {state.status === 'ready' && state.items.length === 0 && (
        <AsyncState actions={<Link className="secondary-link" to="/analyze">Start an analysis</Link>} announcement="No saved analyses are available yet." className="history-state" kind="empty" title="No analyses yet">
          Start an image analysis to create your first saved review.
        </AsyncState>
      )}
      {state.status === 'ready' && state.items.length > 0 && (
        <section className="history-results" aria-label="Saved analyses">
          <p className="history-results__summary"><History aria-hidden="true" size={16} />Showing {state.items.length} saved {state.items.length === 1 ? 'analysis' : 'analyses'}.</p>
          <ul className="history-record-list">
            {state.items.map((item) => {
              const signalEntries = Object.entries(item.signals ?? {})
              return (
                <li key={item.id}>
                  <div className="history-record__topline">
                    <div className="history-record__identity">
                      <strong><span className="history-record__icon"><ScanSearch aria-hidden="true" size={17} /></span>Analysis <code>{item.id}</code></strong>
                      <span><CalendarDays aria-hidden="true" size={15} />Created {formatCreatedAt(item.created_at)}</span>
                    </div>
                    <div className="history-record__actions">
                      <Link state={{ analysis: item }} to={`/results/${item.id}`}>View results <ArrowRight aria-hidden="true" size={15} /></Link>
                      <Link to="/reports"><FileText aria-hidden="true" size={15} />Reports</Link>
                    </div>
                  </div>
                  {Number.isFinite(item.trust_score?.score) && (
                    <div className="history-record__score" aria-label={`Trust score for analysis ${item.id}`}>
                      <span>Trust Score</span>
                      <strong>{item.trust_score.score}/100</strong>
                      <StatusIndicator status={scoreStatus(item.trust_score.category)}>{item.trust_score.category}</StatusIndicator>
                    </div>
                  )}
                  {signalEntries.length > 0 && (
                    <div className="history-record__signals" aria-label={`Signal availability for analysis ${item.id}`}>
                      {signalEntries.map(([name, signal]) => <StatusIndicator key={name} status={statusVariant(signal.status)}>{signalName(name)}: {signal.status}</StatusIndicator>)}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      )}
    </main>
  )
}
