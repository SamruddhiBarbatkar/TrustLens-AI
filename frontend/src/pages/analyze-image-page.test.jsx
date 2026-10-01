import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AnalyzeImagePage } from './AnalyzeImagePage'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

function renderPage() {
  window.localStorage.setItem('trustlens_access_token', 'test-token')
  return render(<MemoryRouter><AnalyzeImagePage /></MemoryRouter>)
}

describe('AnalyzeImagePage', () => {
  it('rejects a non-image selection before submission', () => {
    renderPage()
    expect(screen.getByText('Final validation and analysis happen securely on the server.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Image file'), { target: { files: [new File(['text'], 'notes.txt', { type: 'text/plain' })] } })
    expect(screen.getByRole('alert')).toHaveTextContent('Choose a supported image file')
  })

  it('accepts a dropped image and shows only its real local metadata', () => {
    renderPage()
    const image = new File(['image'], 'evidence.webp', { type: 'image/webp' })
    fireEvent.drop(screen.getByText('Drop an image here or browse'), { dataTransfer: { files: [image] } })
    expect(screen.getByText('evidence.webp')).toBeInTheDocument()
    expect(screen.getByText(/WEBP/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument()
  })

  it('shows saved analysis availability and a next action after a successful submission', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'analysis-1', signals: { ela: { status: 'available' }, ocr: { status: 'unavailable' } } }),
    })
    renderPage()
    fireEvent.change(screen.getByLabelText('Image file'), { target: { files: [new File(['image'], 'sample.png', { type: 'image/png' })] } })
    fireEvent.click(screen.getByRole('button', { name: 'Start analysis' }))

    expect(await screen.findByRole('heading', { name: 'Analysis submitted' })).toBeInTheDocument()
    expect(screen.getByText('Analysis saved')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View history' })).toHaveAttribute('href', '/history')
  })

  it('clears the local session and provides a sign-in action after an expired session', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: 'Unauthorized' }) })
    renderPage()
    fireEvent.change(screen.getByLabelText('Image file'), { target: { files: [new File(['image'], 'sample.png', { type: 'image/png' })] } })
    fireEvent.click(screen.getByRole('button', { name: 'Start analysis' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Your session has expired.')
    expect(window.localStorage.getItem('trustlens_access_token')).toBeNull()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })
})
