import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from './DashboardPage'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

function renderDashboard() {
  window.localStorage.setItem('trustlens_access_token', 'test-token')
  return render(<MemoryRouter><DashboardPage /></MemoryRouter>)
}

describe('DashboardPage', () => {
  it('shows recent owner-scoped activity returned by the history API', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [
        { id: 'analysis-1', created_at: '2026-09-30T10:00:00Z', signals: { ai_generation: { status: 'available', result: { label: 'real' } } }, trust_score: { score: 70, category: 'Needs Review' } },
        { id: 'analysis-2', created_at: '2026-09-29T10:00:00Z', signals: {}, trust_score: { score: 50, category: 'Likely Authentic' } },
      ] }),
    })
    renderDashboard()

    expect(await screen.findByText('Analysis analysis-1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analyze an image' })).toHaveAttribute('href', '/analyze')
    expect(screen.getAllByRole('link', { name: 'View results' })[0]).toHaveAttribute('href', '/results/analysis-1')
    expect(screen.getByText('AI: real')).toBeInTheDocument()
    expect(screen.getByText('60/100')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Start with evidence, then make the call.' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Workspace summary' })).getByText('2')).toBeInTheDocument()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/analyses?limit=20&offset=0',
      expect.objectContaining({ headers: { Authorization: 'Bearer test-token' } }),
    )
  })

  it('shows an explicit empty state when no analyses are returned', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) })
    renderDashboard()
    expect(await screen.findByText('No analyses yet. Start an image review when you are ready.')).toBeInTheDocument()
  })

  it('shows a retry action when recent activity cannot be loaded', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network unavailable'))
    renderDashboard()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load recent analyses.')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })
})
