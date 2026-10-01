import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ReportsPage } from './ReportsPage'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

function renderReports() {
  window.localStorage.setItem('trustlens_access_token', 'test-token')
  return render(<MemoryRouter><ReportsPage /></MemoryRouter>)
}

const analysis = { id: 'analysis-1', created_at: '2026-09-30T10:00:00Z', trust_score: { score: 72, category: 'Needs Review' }, signals: {} }

describe('ReportsPage', () => {
  it('shows returned records and reports download progress and success', async () => {
    let resolveDownload
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [analysis] }) })
      .mockImplementationOnce(() => new Promise((resolve) => { resolveDownload = resolve }))
    const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report')
    const revokeUrl = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderReports()

    expect(await screen.findByText('Analysis report · Sep 30, 2026')).toBeInTheDocument()
    expect(screen.getByText('72/100')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }))
    expect(screen.getByRole('button', { name: 'Preparing PDF…' })).toBeDisabled()
    resolveDownload({ ok: true, blob: async () => new Blob(['report']) })

    expect(await screen.findByRole('status', { name: '' })).toHaveTextContent('Report download started for analysis analysis-1.')
    expect(createUrl).toHaveBeenCalled()
    expect(revokeUrl).toHaveBeenCalledWith('blob:report')
    expect(click).toHaveBeenCalled()
  })

  it('shows an empty reports state', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) })
    renderReports()
    expect(await screen.findByRole('heading', { name: 'No reports available yet' })).toBeInTheDocument()
  })

  it('shows a retry action after a report-list loading failure', async () => {
    global.fetch = vi.fn().mockRejectedValueOnce(new Error('network unavailable')).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) })
    renderReports()
    expect(await screen.findByText('Unable to load available reports.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'No reports available yet' })).toBeInTheDocument()
  })

  it('shows a download error without claiming a report was downloaded', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [analysis] }) })
      .mockResolvedValueOnce({ ok: false, status: 500 })
    renderReports()
    await screen.findByText('Analysis report · Sep 30, 2026')
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to generate the report for this analysis.')
  })

  it('clears a stale session when the report list is unauthorized', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 })
    renderReports()
    expect(await screen.findByRole('alert')).toHaveTextContent('Your session has expired.')
    expect(window.localStorage.getItem('trustlens_access_token')).toBeNull()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })

  it('saves an owner-scoped report title after the user renames it', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [analysis] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...analysis, report_title: 'Kitchen claim review' }) })
    renderReports()
    const rename = await screen.findByRole('button', { name: 'Rename Analysis report · Sep 30, 2026' })
    fireEvent.click(rename)
    fireEvent.change(screen.getByLabelText('Report name'), { target: { value: 'Kitchen claim review' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Kitchen claim review')).toBeInTheDocument()
    expect(global.fetch).toHaveBeenLastCalledWith(
      'http://127.0.0.1:8000/api/v1/analyses/analysis-1/report-title',
      expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ report_title: 'Kitchen claim review' }) }),
    )
  })
})
