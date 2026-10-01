import { ArrowRight, CalendarDays, Download, FileText, Pencil, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { downloadReport, fetchAnalysisHistory, updateReportTitle } from '../lib/api'
import { clearAccessToken, getAccessToken } from '../lib/auth'
import { Button } from '../components/ui/Button'
import { AsyncState } from '../components/ui/AsyncState'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { PageHeader } from '../components/ui/PageHeader'

function scoreStatus(category) {
  if (category === 'Likely Authentic') return 'success'
  if (category === 'Needs Review') return 'warning'
  if (category === 'Potentially Suspicious') return 'error'
  return 'neutral'
}

function formatCreatedAt(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString()
}

function defaultReportTitle(item) {
  const date = new Date(item.created_at)
  const dateLabel = Number.isNaN(date.getTime()) ? 'saved analysis' : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
  return `Analysis report · ${dateLabel}`
}

function saveReport(blob, title) {
  if (typeof URL.createObjectURL !== 'function') throw new Error('File downloads are unavailable in this browser.')
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${title.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(0, 80) || 'trustlens-report'}.pdf`
  link.click()
  URL.revokeObjectURL(url)
}

async function requestReports() {
  return fetchAnalysisHistory(getAccessToken())
}

export function ReportsPage() {
  const [state, setState] = useState({ status: 'loading', items: [] })
  const [downloadState, setDownloadState] = useState({ status: 'idle', id: null, message: '' })
  const [renameState, setRenameState] = useState({ id: null, value: '', status: 'idle', message: '' })

  useEffect(() => {
    let isCurrent = true

    async function loadInitialReports() {
      try {
        const data = await requestReports()
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

    loadInitialReports()
    return () => { isCurrent = false }
  }, [])

  async function retry() {
    setState((current) => ({ ...current, status: 'loading' }))
    try {
      const data = await requestReports()
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

  async function handleDownload(id) {
    setDownloadState({ status: 'loading', id, message: '' })
    try {
      const blob = await downloadReport(id, getAccessToken())
      const item = state.items.find((record) => record.id === id)
      saveReport(blob, item?.report_title || (item ? defaultReportTitle(item) : 'trustlens-report'))
      setDownloadState({ status: 'success', id, message: `Report download started for analysis ${id}.` })
    } catch (error) {
      if (error.status === 401) {
        clearAccessToken()
        setState({ status: 'unauthorized', items: [] })
        setDownloadState({ status: 'idle', id: null, message: '' })
        return
      }
      setDownloadState({ status: 'error', id, message: 'Unable to generate the report for this analysis.' })
    }
  }

  function beginRename(item) {
    setRenameState({ id: item.id, value: item.report_title || defaultReportTitle(item), status: 'editing', message: '' })
  }

  async function saveRename(id) {
    const title = renameState.value.trim()
    if (!title) {
      setRenameState((current) => ({ ...current, status: 'editing', message: 'Enter a report name.' }))
      return
    }
    setRenameState((current) => ({ ...current, status: 'saving', message: '' }))
    try {
      const updated = await updateReportTitle(id, title, getAccessToken())
      setState((current) => ({ ...current, items: current.items.map((item) => item.id === id ? updated : item) }))
      setRenameState({ id: null, value: '', status: 'idle', message: '' })
    } catch (error) {
      if (error.status === 401) {
        clearAccessToken()
        setState({ status: 'unauthorized', items: [] })
        setRenameState({ id: null, value: '', status: 'idle', message: '' })
        return
      }
      setRenameState((current) => ({ ...current, status: 'editing', message: 'Unable to rename this report. Try again.' }))
    }
  }

  return (
    <main className="app-page reports-page" aria-labelledby="reports-title">
      <PageHeader
        actions={<Link className="secondary-link" to="/history">View history <ArrowRight aria-hidden="true" size={16} /></Link>}
        className="reports-page__header"
        eyebrow="Private workspace"
        title="Reports"
        titleId="reports-title"
      >
        <p className="lede">Generate an owner-scoped PDF from a saved analysis record. Report content comes from the server.</p>
      </PageHeader>

      <div className="reports-feedback">
        {downloadState.status === 'success' && <AsyncState className="reports-feedback__success" kind="success" announcement={downloadState.message}>{downloadState.message}</AsyncState>}
        {downloadState.status === 'error' && <AsyncState className="error-message" kind="error" announcement={downloadState.message}>{downloadState.message}</AsyncState>}
      </div>

      {state.status === 'loading' && <LoadingSkeleton className="reports-state reports-state--loading" label="Loading available reports" lines={4} />}
      {state.status === 'unauthorized' && (
        <AsyncState actions={<Link className="secondary-link" to="/login">Sign in</Link>} announcement="Your session has expired. Sign in to view reports." kind="unauthorized" title="Your session has expired.">
          Sign in to view reports.
        </AsyncState>
      )}
      {state.status === 'error' && (
        <AsyncState actions={<Button onClick={retry} variant="secondary">Try again</Button>} announcement="Available reports could not be loaded. Try again." className="reports-state" kind="error" title="Unable to load available reports." />
      )}
      {state.status === 'ready' && state.items.length === 0 && (
        <AsyncState actions={<Link className="secondary-link" to="/analyze">Start an analysis</Link>} announcement="No reports are available yet." className="reports-state" kind="empty" title="No reports available yet">
          Complete an image analysis to create a saved record for a report.
        </AsyncState>
      )}
      {state.status === 'ready' && state.items.length > 0 && (
        <section className="reports-list" aria-label="Available reports">
          <p className="reports-list__summary"><FileText aria-hidden="true" size={16} />Reports are generated from the saved analysis you select.</p>
          <ul>
            {state.items.map((item) => (
              <li key={item.id}>
                <div className="report-record__identity">
                  {renameState.id === item.id ? (
                    <div className="report-record__rename"><label className="sr-only" htmlFor={`report-title-${item.id}`}>Report name</label><input id={`report-title-${item.id}`} maxLength="120" onChange={(event) => setRenameState((current) => ({ ...current, value: event.target.value, message: '' }))} value={renameState.value} /><Button disabled={renameState.status === 'saving'} loading={renameState.status === 'saving'} onClick={() => saveRename(item.id)} type="button">Save</Button><Button onClick={() => setRenameState({ id: null, value: '', status: 'idle', message: '' })} type="button" variant="ghost"><X aria-hidden="true" size={16} /><span className="sr-only">Cancel rename</span></Button>{renameState.message && <p role="alert">{renameState.message}</p>}</div>
                  ) : <strong><span className="report-record__icon"><FileText aria-hidden="true" size={17} /></span>{item.report_title || defaultReportTitle(item)} <button aria-label={`Rename ${item.report_title || defaultReportTitle(item)}`} className="report-record__rename-button" onClick={() => beginRename(item)} type="button"><Pencil aria-hidden="true" size={15} /></button></strong>}
                  <span><CalendarDays aria-hidden="true" size={15} />Created {formatCreatedAt(item.created_at)}</span>
                  {Number.isFinite(item.trust_score?.score) && (
                    <span className="report-record__score" aria-label={`Trust score for analysis ${item.id}`}>
                      Trust Score <strong>{item.trust_score.score}/100</strong> <em className={`report-record__category report-record__category--${scoreStatus(item.trust_score.category)}`}>{item.trust_score.category}</em>
                    </span>
                  )}
                </div>
                <div className="report-record__actions">
                  <Link state={{ analysis: item }} to={`/results/${item.id}`}>View results <ArrowRight aria-hidden="true" size={15} /></Link>
                  <Button disabled={downloadState.status === 'loading'} loading={downloadState.status === 'loading' && downloadState.id === item.id} onClick={() => handleDownload(item.id)}>{downloadState.status === 'loading' && downloadState.id === item.id ? 'Preparing PDF…' : <>Download PDF <Download aria-hidden="true" size={16} /></>}</Button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}
