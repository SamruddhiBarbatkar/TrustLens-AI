import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { LoginPage } from './LoginPage'
import { SignupPage } from './SignupPage'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('authentication pages', () => {
  it('shows accessible signup guidance, terms consent, and the sign-in path', () => {
    render(<MemoryRouter><SignupPage /></MemoryRouter>)
    expect(screen.getByText('At least 8 characters')).toBeInTheDocument()
    expect(screen.getByLabelText('I agree to TrustLens data handling terms for my account.')).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Create account' })).toBeDisabled()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })

  it('requires matching passwords and accepted terms before signup can be submitted', () => {
    render(<MemoryRouter><SignupPage /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Alex Mercer' } })
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'reviewer@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password123!' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'different123' } })
    expect(screen.getByRole('button', { name: 'Create account' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'Password123!' } })
    fireEvent.click(screen.getByLabelText('I agree to TrustLens data handling terms for my account.'))
    expect(screen.getByRole('button', { name: 'Create account' })).toBeEnabled()
  })

  it('submits only the supported signup payload and preserves the automatic sign-in flow', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ access_token: 'signup-token' }) })
    render(<MemoryRouter><SignupPage /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Alex Mercer' } })
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: ' reviewer@example.com ' } })
    fireEvent.change(screen.getByLabelText('Professional role / organization Optional'), { target: { value: 'Claims analyst' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password123!' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'Password123!' } })
    fireEvent.click(screen.getByLabelText('I agree to TrustLens data handling terms for my account.'))
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => expect(window.localStorage.getItem('trustlens_access_token')).toBe('signup-token'))
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/auth/signup',
      expect.objectContaining({ body: JSON.stringify({ name: 'Alex Mercer', email: 'reviewer@example.com', role: 'Claims analyst', password: 'Password123!' }), method: 'POST' }),
    )
  })

  it('lets a user deliberately reveal or hide their password without changing its value', () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    const password = screen.getByLabelText('Password')
    fireEvent.change(password, { target: { value: 'password123' } })
    expect(password).toHaveAttribute('type', 'password')
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'text')
    expect(screen.getByLabelText('Password')).toHaveValue('password123')
    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
  })

  it('keeps invalid login data in the browser and moves focus to the first invalid field', () => {
    global.fetch = vi.fn()
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(screen.getByLabelText('Email address')).toHaveFocus()
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('shows a loading state and stores a token after signing in', async () => {
    let resolveRequest
    global.fetch = vi.fn(() => new Promise((resolve) => { resolveRequest = resolve }))
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'reviewer@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled()
    resolveRequest({ ok: true, json: async () => ({ access_token: 'test-token' }) })

    await waitFor(() => expect(window.localStorage.getItem('trustlens_access_token')).toBe('test-token'))
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/auth/login',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('shows a safe account-conflict message when signup is rejected', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 409 })
    render(<MemoryRouter><SignupPage /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Alex Mercer' } })
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'reviewer@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password123!' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'Password123!' } })
    fireEvent.click(screen.getByLabelText('I agree to TrustLens data handling terms for my account.'))
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('An account already uses this email address.')
  })

  it('shows a safe connection error when login cannot reach the API', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network unavailable'))
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'reviewer@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not reach TrustLens.')
  })

  it('explains when signup authentication is temporarily unavailable', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 })
    render(<MemoryRouter><SignupPage /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Alex Mercer' } })
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'reviewer@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password123!' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'Password123!' } })
    fireEvent.click(screen.getByLabelText('I agree to TrustLens data handling terms for my account.'))
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Authentication is temporarily unavailable.')
  })
})
