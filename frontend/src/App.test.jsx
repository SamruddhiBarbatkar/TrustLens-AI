import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('App', () => {
  it('renders the home route instead of a blank page', () => {
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Verify images. Understand the evidence.' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Create an account' })).toHaveAttribute('href', '/signup')
    expect(screen.getAllByRole('link', { name: 'How it works' }).at(-1)).toHaveAttribute('href', '/how-it-works')
    expect(screen.getByRole('heading', { name: 'Evidence is not a verdict.' })).toBeInTheDocument()
    expect(screen.getByText('Conceptual workflow only. Signals remain explicit when unavailable or limited.')).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toHaveTextContent('AI-assisted image authenticity verification using multimodal analysis.')
    expect(screen.getByText('TrustLens does not prove authenticity, fraud, provenance, ownership, copyright, or intent. Interpret every available signal with appropriate human judgment.')).toBeInTheDocument()
  })
  it.each([
    ['/features', 'Signals to help you look closer.'],
    ['/how-it-works', 'A clear path from image to review.'],
    ['/about', 'Decision support for image review.'],
    ['/login', 'Continue your image review.'],
    ['/signup', 'Create your private image-review workspace.'],
  ])('renders the %s public route', (path, heading) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
  })

  it('provides an accessible collapsible public navigation control', () => {
    render(<MemoryRouter initialEntries={['/features']}><App /></MemoryRouter>)
    const toggle = screen.getByRole('button', { name: 'Open navigation menu' })
    expect(toggle).toHaveAttribute('aria-controls', 'public-navigation-links')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Close navigation menu' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Features' })).toHaveClass('is-active')
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveFocus()
  })

  it.each([
    ['/dashboard', 'Your image review workspace'],
    ['/analyze', 'Analyze an image'],
    ['/history', 'Analysis history'],
    ['/reports', 'Reports'],
    ['/profile', 'Profile'],
    ['/settings', 'Settings'],
  ])('renders the %s protected route with workspace navigation', (path, heading) => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) })

    render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Workspace navigation' })).toBeInTheDocument()
    const commandBarLabels = {
      '/dashboard': 'Dashboard',
      '/analyze': 'Analyze image',
      '/history': 'History',
      '/reports': 'Reports',
      '/profile': 'Profile',
      '/settings': 'Settings',
    }
    expect(within(screen.getByRole('banner', { name: 'Workspace command bar' })).getByText(commandBarLabels[path])).toBeInTheDocument()
  })

  it('renders a direct protected results route with an explicit unavailable state instead of a blank page', async () => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) })

    render(<MemoryRouter initialEntries={['/results/missing-analysis']}><App /></MemoryRouter>)

    expect(await screen.findByRole('heading', { name: 'Analysis is not available.' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Workspace navigation' })).toBeInTheDocument()
    expect(within(screen.getByRole('banner', { name: 'Workspace command bar' })).getByText('Analysis results')).toBeInTheDocument()
  })

  it('redirects unauthenticated users from the dashboard', () => {
    render(<MemoryRouter initialEntries={['/dashboard']}><App /></MemoryRouter>)
    expect(screen.queryByRole('heading', { name: 'Your image review workspace' })).not.toBeInTheDocument()
  })

  it('renders the protected workspace navigation for authenticated users', () => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    render(<MemoryRouter initialEntries={['/dashboard']}><App /></MemoryRouter>)
    const workspaceNav = screen.getByRole('navigation', { name: 'Workspace navigation' })
    expect(workspaceNav).toBeInTheDocument()
    expect(within(workspaceNav).getByRole('link', { name: 'Analyze image' })).toHaveAttribute('href', '/analyze')
    expect(within(workspaceNav).getByRole('link', { name: 'Profile' })).toHaveAttribute('href', '/profile')
    expect(within(workspaceNav).getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings')
    const mobileToggle = screen.getByRole('button', { name: 'Open workspace navigation' })
    expect(mobileToggle).toHaveAttribute('aria-controls', 'workspace-mobile-navigation')
    fireEvent.click(mobileToggle)
    expect(mobileToggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('navigation', { name: 'Mobile workspace navigation' })).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('navigation', { name: 'Mobile workspace navigation' })).not.toBeInTheDocument()
    expect(mobileToggle).toHaveFocus()
    window.localStorage.clear()
  })

  it('signs out from the workspace and returns to the public home page', () => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    const view = render(<MemoryRouter initialEntries={['/dashboard']}><App /></MemoryRouter>)
    fireEvent.click(within(view.container).getAllByRole('button', { name: 'Sign out' })[0])
    expect(window.localStorage.getItem('trustlens_access_token')).toBeNull()
    expect(within(view.container).getByRole('heading', { name: 'Verify images. Understand the evidence.' })).toBeInTheDocument()
  })

  it('shows a clear not-found page for unknown routes', () => {
    render(<MemoryRouter initialEntries={['/missing']}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'This page is not available.' })).toBeInTheDocument()
  })

  it('requires a file before starting analysis', () => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    render(<MemoryRouter initialEntries={['/analyze']}><App /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: 'Start analysis' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Choose an image')
    window.localStorage.clear()
  })

  it('submits the selected image with the bearer token and shows returned statuses', async () => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'analysis-1', signals: { ela: { status: 'available' }, ocr: { status: 'unavailable' } } }),
    })
    const view = render(<MemoryRouter initialEntries={['/analyze']}><App /></MemoryRouter>)
    const page = within(view.container)
    const input = view.container.querySelector('#image-file')
    expect(input).not.toBeNull()
    fireEvent.change(input, { target: { files: [new File(['image'], 'sample.png', { type: 'image/png' })] } })
    fireEvent.click(page.getByRole('button', { name: 'Start analysis' }))

    expect(await page.findByRole('heading', { name: 'Analysis submitted' })).toBeInTheDocument()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/analyses',
      expect.objectContaining({ headers: { Authorization: 'Bearer test-token' }, method: 'POST' }),
    )
    window.localStorage.clear()
    vi.restoreAllMocks()
  })
})
