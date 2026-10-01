import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})

describe('profile and settings routes', () => {
  it('shows an honest unavailable profile state in the protected workspace', () => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    const view = render(<MemoryRouter initialEntries={['/profile']}><App /></MemoryRouter>)
    expect(within(view.container).getByRole('heading', { name: 'Profile' })).toBeInTheDocument()
    expect(within(view.container).getByRole('heading', { name: 'Profile details are unavailable.' })).toBeInTheDocument()
    expect(within(view.container).getByRole('link', { name: 'View settings availability' })).toHaveAttribute('href', '/settings')
  })

  it('shows only safe identity fields returned by the stored authenticated session', () => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    window.localStorage.setItem('trustlens_current_user', JSON.stringify({
      id: 'user-1',
      name: 'Alex Mercer',
      email: 'alex@example.com',
      role: 'Claims analyst',
      created_at: '2026-09-30T10:00:00Z',
      last_login: '2026-09-30T11:00:00Z',
    }))
    const view = render(<MemoryRouter initialEntries={['/profile']}><App /></MemoryRouter>)
    expect(within(view.container).getByRole('heading', { name: 'Signed-in account' })).toBeInTheDocument()
    expect(within(view.container).getByText('Alex Mercer')).toBeInTheDocument()
    expect(within(view.container).getByText('alex@example.com')).toBeInTheDocument()
    expect(within(view.container).getByText('Claims analyst')).toBeInTheDocument()
    expect(within(view.container).queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('shows settings as unavailable instead of offering unsupported fields', () => {
    window.localStorage.setItem('trustlens_access_token', 'test-token')
    const view = render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>)
    expect(within(view.container).getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    expect(within(view.container).getByRole('heading', { name: 'Saved settings are unavailable.' })).toBeInTheDocument()
    expect(within(view.container).queryByRole('textbox')).not.toBeInTheDocument()
    expect(within(view.container).getByRole('link', { name: 'View profile' })).toHaveAttribute('href', '/profile')
  })

  it('keeps settings protected when no session is present', () => {
    render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Continue your image review.' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Settings' })).not.toBeInTheDocument()
  })
})
