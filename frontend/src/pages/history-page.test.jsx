import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { HistoryPage } from './HistoryPage'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

function renderHistory() {
  window.localStorage.setItem('trustlens_access_token', 'test-token')
  return render(<MemoryRouter><HistoryPage /></MemoryRouter>)
}

describe('HistoryPage', () => {
  it('shows returned owner-scoped records with safe actions and signal availability', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 'analysis-1', created_at: '2026-09-30T10:00:00Z', trust_score: { score: 72, category: 'Needs Review' }, signals: { ai_generation: { status: 'available' }, ocr: { status: 'unavailable' } } }] }),
    })
    renderHistory()
    expect(await screen.findByText('analysis-1', { selector: 'code' })).toBeInTheDocument()
    expect(screen.getByText('72/100')).toBeInTheDocument()
    expect(screen.getByText('AI-generated detection: available')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View results' })).toHaveAttribute('href', '/results/analysis-1')
    expect(screen.getByRole('link', { name: 'Reports' })).toHaveAttribute('href', '/reports')
  })

  it('shows an empty history state', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) })
    renderHistory()
    expect(await screen.findByRole('heading', { name: 'No analyses yet' })).toBeInTheDocument()
  })

  it('shows a retry action after a loading failure', async () => {
    global.fetch = vi.fn().mockRejectedValueOnce(new Error('network unavailable')).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) })
    renderHistory()
    expect(await screen.findByText('Unable to load analysis history.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'No analyses yet' })).toBeInTheDocument()
  })

  it('clears a stale session and offers sign-in after an unauthorized response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 })
    renderHistory()
    expect(await screen.findByRole('alert')).toHaveTextContent('Your session has expired.')
    expect(window.localStorage.getItem('trustlens_access_token')).toBeNull()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })
})
