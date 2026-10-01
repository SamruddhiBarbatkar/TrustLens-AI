import { LockKeyhole, ShieldCheck } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { setAccessToken, setCurrentUser } from '../lib/auth'
import { Button } from '../components/ui/Button'
import { AsyncState } from '../components/ui/AsyncState'
import { PasswordField } from '../components/ui/PasswordField'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function getReturnPath(state) {
  const from = state?.from
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') ? from : '/dashboard'
}

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [attemptedSubmit, setAttemptedSubmit] = useState(false)
  const [touched, setTouched] = useState({ email: false, password: false })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const emailInputRef = useRef(null)
  const passwordInputRef = useRef(null)
  const location = useLocation()
  const navigate = useNavigate()
  const normalizedEmail = email.trim()
  const emailIsValid = emailPattern.test(normalizedEmail)
  const passwordIsValid = password.length > 0
  const emailError = (attemptedSubmit || touched.email) && !emailIsValid ? 'Enter a valid email address.' : ''
  const passwordError = (attemptedSubmit || touched.password) && !passwordIsValid ? 'Enter your password.' : ''

  async function submit(event) {
    event.preventDefault()
    setAttemptedSubmit(true)
    setError('')
    if (!emailIsValid || !passwordIsValid || isSubmitting) {
      if (!emailIsValid) emailInputRef.current?.focus()
      else passwordInputRef.current?.focus()
      return
    }
    setIsSubmitting(true)

    try {
      const response = await fetch(`${apiBaseUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail, password }),
      })
      if (!response.ok) {
        setError(response.status === 401 || response.status === 422
          ? 'Email or password is incorrect.'
          : response.status === 503
            ? 'Authentication is temporarily unavailable. Please try again shortly.'
          : 'We could not sign you in. Please try again shortly.')
        return
      }
      const data = await response.json()
      setAccessToken(data.access_token)
      setCurrentUser(data.user)
      navigate(getReturnPath(location.state), { replace: true })
    } catch {
      setError('We could not reach TrustLens. Check your connection and try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-page" aria-labelledby="login-title">
      <section className="auth-intro" aria-label="TrustLens sign in information">
        <p className="eyebrow">Welcome back</p>
        <h1 id="login-title">Continue your image review.</h1>
        <p>Sign in to access your private analyses and reports. TrustLens keeps decision-support evidence in one review workspace.</p>
        <ul className="auth-intro__principles">
          <li><LockKeyhole aria-hidden="true" size={17} />Private account access</li>
          <li><ShieldCheck aria-hidden="true" size={17} />Evidence remains decision support</li>
        </ul>
      </section>
      <section className="auth-card" aria-label="Sign in form">
        <div className="auth-card__heading">
          <p className="eyebrow">Account access</p>
          <h2>Sign in</h2>
          <p>Use the email address and password associated with your account.</p>
        </div>
        <form className="auth-form" noValidate onSubmit={submit}>
          <div className="auth-field">
            <label htmlFor="email">Email address</label>
            <input aria-describedby={emailError ? 'email-error' : undefined} aria-invalid={Boolean(emailError)} autoComplete="email" id="email" onBlur={() => setTouched((current) => ({ ...current, email: true }))} onChange={(event) => setEmail(event.target.value)} ref={emailInputRef} required type="email" value={email} />
            {emailError && <p className="auth-field__error" id="email-error" role="alert">{emailError}</p>}
          </div>
          <PasswordField autoComplete="current-password" error={passwordError} id="password" inputRef={passwordInputRef} onBlur={() => setTouched((current) => ({ ...current, password: true }))} onChange={(event) => setPassword(event.target.value)} value={password} />
          {isSubmitting && <AsyncState className="auth-error" kind="loading" title="Signing in" />}
          {error && <AsyncState className="error-message auth-error" kind="error" announcement={error}>{error}</AsyncState>}
          <Button className="auth-submit" loading={isSubmitting} type="submit">{isSubmitting ? 'Signing in…' : 'Sign in'}</Button>
        </form>
        <p className="auth-card__footer">New to TrustLens? <Link to="/signup">Create an account</Link></p>
      </section>
    </main>
  )
}
