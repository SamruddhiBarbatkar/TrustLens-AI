import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '../components/ProtectedRoute'
import { ResultsPage } from './ResultsPage'

const analysis = {
  id: 'analysis-1',
  created_at: '2026-09-30T10:00:00Z',
  signals: {
    tampering: { status: 'available', result: { label: 'tampered', top_class_softmax_score: 0.82, preprocessing_note: 'Verified preprocessing.' } },
    ai_generation: { status: 'unavailable', message: 'Signal is unavailable.' },
    ocr: { status: 'available', result: { regions: [{ text: 'TRUSTLENS', confidence: 0.91 }] } },
    quality: { status: 'available', result: { width: 640, height: 480, brightness_mean: 120.5, contrast_standard_deviation: 42.25, sharpness_laplacian_variance: 87.5, method: 'Measured image properties.' } },
    ela: { status: 'available', result: { mean_absolute_difference: 8.25, differing_pixel_fraction: 0.2, recompression_quality: 90, method: 'JPEG recompression', limitations: ['Compression changes evidence.'] } },
  },
  trust_score: {
    score: 55,
    category: 'Needs Review',
    signal_weights: { tampering: 0.5, ai_generation: 0.5 },
    contributing_signals: ['tampering', 'ai_generation'],
    limitations: ['Decision support only.'],
  },
  explanation: {
    overall_summary: 'TrustLens completed 4 available signals, with 1 unavailable and 0 failed signals.',
    trust_score: {
      score: 55,
      category: 'Needs Review',
      explanation: 'TrustLens assigned 55/100 (Needs Review) using the available adaptive model signals.',
      contributing_factors: [{ signal: 'tampering', direction: 'requires_review', explanation: 'Tampering detection returned tampered with a recorded top-class score of 82%; adaptive fusion assigned 50%.' }],
      caution_factors: [{ signal: 'ai_generation', direction: 'requires_review', explanation: 'AI-generated detection was unavailable and did not contribute a score.' }],
    },
    tampering: { status: 'available', interpretation: 'The tampering detector classified the image as tampered with a recorded top-class score of 82%.', contribution: 'This classification contributes review-direction evidence.' },
    ai_generated: { status: 'unavailable', interpretation: 'AI-generated image detector is unavailable.' },
    ocr: { status: 'available', interpretation: 'OCR returned one text region.' },
    image_quality: { status: 'available', interpretation: 'Image-quality analysis completed with resolution 640×480.' },
    ela: { status: 'available', interpretation: 'ELA completed.', observations: ['Mean absolute recompression difference: 8.25.'] },
    fusion: { signals_considered: ['tampering', 'ai_generation'], signal_weights: { tampering: 0.5, ai_generation: 0.5 }, explanation: 'Adaptive fusion used tampering detection and AI-generated detection.' },
    limitations: ['Model scores are not calibrated evidence.'],
  },
}

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

function renderResults(initialEntry) {
  window.localStorage.setItem('trustlens_access_token', 'test-token')
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/results/:analysisId" element={<ResultsPage />} />
        <Route path="/login" element={<p>Sign in screen</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ResultsPage', () => {
  it('renders returned evidence and the server-provided adaptive Trust Score', () => {
    renderResults({ pathname: '/results/analysis-1', state: { analysis } })
    expect(screen.getByRole('heading', { name: 'Analysis results' })).toBeInTheDocument()
    expect(screen.getByLabelText('Trust Score 55 out of 100')).toBeInTheDocument()
    expect(screen.getByText('tampered')).toBeInTheDocument()
    expect(screen.getByText('TRUSTLENS')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Available technical signals' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Image quality' })).toBeInTheDocument()
    expect(screen.getByText('640 × 480')).toBeInTheDocument()
    expect(screen.getByText(/Measured image properties/)).toBeInTheDocument()
    expect(screen.getByText('Score breakdown')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Available analysis modules' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What TrustLens found' })).toBeInTheDocument()
    expect(screen.getByText(/TrustLens completed 4 available signals/)).toBeInTheDocument()
    expect(screen.getByText(/TrustLens assigned 55\/100/)).toBeInTheDocument()
    expect(screen.getByText('Evidence requiring review')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Limitations to consider' })).toBeInTheDocument()
  })

  it('reads an available AI detector result from the backend ai_generation signal key', () => {
    const analysisWithAiResult = {
      ...analysis,
      signals: {
        ...analysis.signals,
        ai_generation: { status: 'available', result: { label: 'generated', top_class_softmax_score: 0.77 } },
      },
    }
    renderResults({ pathname: '/results/analysis-1', state: { analysis: analysisWithAiResult } })
    expect(screen.getByRole('heading', { name: 'AI-generated detection' })).toBeInTheDocument()
    expect(screen.getByText('generated')).toBeInTheDocument()
    expect(screen.getByText('77%')).toBeInTheDocument()
  })

  it('displays the owner-authorized uploaded image when the API marks it available', async () => {
    const sourceImageAnalysis = { ...analysis, source_image_available: true }
    const sourceBlob = new Blob(['image'], { type: 'image/png' })
    URL.createObjectURL = vi.fn(() => 'blob:source-image')
    URL.revokeObjectURL = vi.fn()
    global.fetch = vi.fn().mockResolvedValue({ ok: true, blob: async () => sourceBlob })

    renderResults({ pathname: '/results/analysis-1', state: { analysis: sourceImageAnalysis } })

    expect(await screen.findByRole('img', { name: 'Uploaded image used for this analysis' })).toHaveAttribute('src', 'blob:source-image')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/analyses/analysis-1/source-image',
      expect.objectContaining({ headers: { Authorization: 'Bearer test-token' } }),
    )
  })

  it('loads an owner-scoped result from existing history when opened directly', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [analysis] }) })
    renderResults('/results/analysis-1')
    expect(await screen.findByText('tampered')).toBeInTheDocument()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/analyses?limit=50&offset=0',
      expect.objectContaining({ headers: { Authorization: 'Bearer test-token' } }),
    )
  })

  it('renders a missing-result state without manufacturing an analysis', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) })
    renderResults('/results/missing')
    expect(await screen.findByRole('heading', { name: 'Analysis is not available.' })).toBeInTheDocument()
  })

  it('keeps a legacy record explicit when no structured explanation was returned', () => {
    const legacyAnalysis = { ...analysis, explanation: null }
    renderResults({ pathname: '/results/analysis-1', state: { analysis: legacyAnalysis } })
    expect(screen.getByRole('heading', { name: 'Structured explanation unavailable' })).toBeInTheDocument()
    expect(screen.getByText(/created before TrustLens stored explainable evidence/)).toBeInTheDocument()
  })

  it('keeps the results route protected', () => {
    window.localStorage.clear()
    render(
      <MemoryRouter initialEntries={['/results/analysis-1']}>
        <Routes>
          <Route path="/results/:analysisId" element={<ProtectedRoute><ResultsPage /></ProtectedRoute>} />
          <Route path="/login" element={<p>Sign in screen</p>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Sign in screen')).toBeInTheDocument()
  })
})
