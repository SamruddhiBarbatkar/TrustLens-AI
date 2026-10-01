import { Activity, CheckCircle2, CircleAlert, Eye, EyeOff, FileText, Image, LockKeyhole, Mail, ScanSearch, ShieldCheck, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { setAccessToken, setCurrentUser } from '../lib/auth'
import { Button } from '../components/ui/Button'
import { AsyncState } from '../components/ui/AsyncState'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const productFeatures = [
  'Multimodal image authenticity assessment',
  'Tampering and AI-generated-image detection',
  'OCR and image-quality evidence',
  'Explainable analysis for completed assessments',
  'Owner-scoped PDF reports and history',
]

const pipelineStages = [
  [Image, 'Image', 'Validated upload'],
  [ScanSearch, 'Tampering detection', 'Visual model signal'],
  [Activity, 'AI-generated detection', 'Generation-likelihood signal'],
  [FileText, 'OCR, quality, and ELA', 'Supporting evidence'],
  [ShieldCheck, 'Adaptive Trust Score', 'Server-derived decision support'],
]

function getReturnPath(state) {
  const from = state?.from
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') ? from : '/dashboard'
}

function SignupPasswordField({ error, id, label, onBlur, onChange, value }) {
  const [isVisible, setIsVisible] = useState(false)
  const describedBy = error ? `${id}-error` : undefined
  return (
    <div className="auth-field signup-field">
      <label htmlFor={id}>{label}</label>
      <div className="auth-field__control signup-field__control">
        <LockKeyhole aria-hidden="true" size={17} />
        <input aria-describedby={describedBy} aria-invalid={Boolean(error)} autoComplete="new-password" id={id} minLength="8" onBlur={onBlur} onChange={onChange} required type={isVisible ? 'text' : 'password'} value={value} />
        <button aria-label={isVisible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`} aria-pressed={isVisible} className="password-visibility-toggle" onClick={() => setIsVisible((visible) => !visible)} type="button">
          {isVisible ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}
        </button>
      </div>
      {error && <p className="signup-field__error" id={`${id}-error`} role="alert">{error}</p>}
    </div>
  )
}

export function SignupPage() {
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [attemptedSubmit, setAttemptedSubmit] = useState(false)
  const [touched, setTouched] = useState({ name: false, email: false, password: false, confirmPassword: false, terms: false })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  const normalizedName = name.trim()
  const normalizedEmail = email.trim()
  const nameIsValid = normalizedName.length >= 2
  const emailIsValid = emailPattern.test(normalizedEmail)
  const passwordIsValid = password.length >= 8
  const passwordHasUppercase = /[A-Z]/.test(password)
  const passwordHasLowercase = /[a-z]/.test(password)
  const passwordHasNumber = /\d/.test(password)
  const passwordHasSpecial = /[^A-Za-z0-9]/.test(password)
  const passwordIsStrong = passwordIsValid && passwordHasUppercase && passwordHasLowercase && passwordHasNumber && passwordHasSpecial
  const passwordsMatch = password.length > 0 && password === confirmPassword
  const formIsValid = nameIsValid && emailIsValid && passwordIsStrong && passwordsMatch && acceptedTerms
  const nameError = (attemptedSubmit || touched.name) && !nameIsValid ? 'Please enter your full name.' : ''
  const emailError = (attemptedSubmit || touched.email) && !emailIsValid ? 'Enter a valid email address.' : ''
  const passwordError = (attemptedSubmit || touched.password) && !passwordIsStrong ? 'Use a stronger password that meets every requirement.' : ''
  const confirmPasswordError = (attemptedSubmit || touched.confirmPassword) && !passwordsMatch ? 'Passwords do not match.' : ''
  const termsError = (attemptedSubmit || touched.terms) && !acceptedTerms ? 'Accept the data handling policy to continue.' : ''

  async function submit(event) {
    event.preventDefault()
    setAttemptedSubmit(true)
    setError('')
    if (!formIsValid || isSubmitting) return
    setIsSubmitting(true)

    try {
      const response = await fetch(`${apiBaseUrl}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: normalizedName, email: normalizedEmail, role: role.trim() || undefined, password }),
      })
      if (!response.ok) {
        setError(response.status === 409
          ? 'An account already uses this email address.'
          : response.status === 422
            ? 'Check your email address and password requirements.'
            : response.status === 503
              ? 'Authentication is temporarily unavailable. Please try again shortly.'
              : 'We could not create your account. Please try again shortly.')
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
    <main className="auth-page signup-page" aria-labelledby="signup-title">
      <section className="auth-intro signup-showcase" aria-label="TrustLens capabilities">
        <p className="eyebrow">Multimodal forensic intelligence</p>
        <h1 id="signup-title">Create your private image-review workspace.</h1>
        <p>TrustLens AI evaluates insurance and warranty claim images using available tampering, AI-generated-image, OCR, image-quality, and ELA signals, with an adaptive Trust Score for decision support.</p>
        <ul className="auth-intro__principles signup-feature-list">
          {productFeatures.map((feature) => <li key={feature}><CheckCircle2 aria-hidden="true" size={17} />{feature}</li>)}
        </ul>
        <section className="signup-pipeline" aria-labelledby="signup-pipeline-title">
          <div><p className="signup-pipeline__eyebrow">TrustLens analysis pipeline</p><h2 id="signup-pipeline-title">From image to explainable assessment.</h2></div>
          <ol>
            {pipelineStages.map(([Icon, title, detail], index) => <li key={title}><span>{String(index + 1).padStart(2, '0')}</span><Icon aria-hidden="true" size={17} /><strong>{title}</strong><small>{detail}</small></li>)}
          </ol>
          <p><CircleAlert aria-hidden="true" size={16} />Conceptual workflow only; completed analysis results come from the server.</p>
        </section>
      </section>

      <section className="auth-card signup-card" aria-label="Create account form">
        <div className="auth-card__heading"><p className="eyebrow">Get started</p><h2>Create your TrustLens account</h2><p>Set up your account to securely access image analysis, reports, and analysis history.</p></div>
        <form className="auth-form" noValidate onSubmit={submit}>
          <div className="auth-field signup-field">
            <label htmlFor="signup-name">Full name</label>
            <div className="auth-field__control signup-field__control"><UserRound aria-hidden="true" size={17} /><input aria-describedby={nameError ? 'signup-name-error' : undefined} aria-invalid={Boolean(nameError)} autoComplete="name" id="signup-name" onBlur={() => setTouched((current) => ({ ...current, name: true }))} onChange={(event) => setName(event.target.value)} placeholder="e.g. Alex Mercer" required value={name} /></div>
            {nameError && <p className="signup-field__error" id="signup-name-error" role="alert">{nameError}</p>}
          </div>
          <div className="auth-field signup-field">
            <label htmlFor="signup-email">Email address</label>
            <div className="auth-field__control signup-field__control"><Mail aria-hidden="true" size={17} /><input aria-describedby={emailError ? 'signup-email-error' : undefined} aria-invalid={Boolean(emailError)} autoComplete="email" id="signup-email" onBlur={() => setTouched((current) => ({ ...current, email: true }))} onChange={(event) => setEmail(event.target.value)} placeholder="analyst@organization.com" required type="email" value={email} /></div>
            {emailError && <p className="signup-field__error" id="signup-email-error" role="alert">{emailError}</p>}
          </div>
          <div className="auth-field signup-field">
            <label htmlFor="signup-role">Professional role / organization <span className="signup-field__optional">Optional</span></label>
            <div className="auth-field__control signup-field__control"><ShieldCheck aria-hidden="true" size={17} /><input autoComplete="organization-title" id="signup-role" maxLength="160" onChange={(event) => setRole(event.target.value)} placeholder="e.g. Insurance Claims Analyst" value={role} /></div>
          </div>
          <SignupPasswordField error={passwordError} id="signup-password" label="Password" onBlur={() => setTouched((current) => ({ ...current, password: true }))} onChange={(event) => setPassword(event.target.value)} value={password} />
          <ul className="signup-password-requirements" aria-label="Password requirements">
            {[[passwordIsValid, 'At least 8 characters'], [passwordHasUppercase, 'One uppercase letter'], [passwordHasLowercase, 'One lowercase letter'], [passwordHasNumber, 'One number'], [passwordHasSpecial, 'One special character']].map(([complete, requirement]) => <li className={complete ? 'is-complete' : ''} key={requirement}><CheckCircle2 aria-hidden="true" size={15} />{requirement}</li>)}
          </ul>
          <SignupPasswordField error={confirmPasswordError} id="signup-confirm-password" label="Confirm password" onBlur={() => setTouched((current) => ({ ...current, confirmPassword: true }))} onChange={(event) => setConfirmPassword(event.target.value)} value={confirmPassword} />
          {confirmPassword && passwordsMatch && <p className="signup-password-match"><CheckCircle2 aria-hidden="true" size={15} />Passwords match.</p>}
          <div className="signup-terms"><label><input checked={acceptedTerms} onBlur={() => setTouched((current) => ({ ...current, terms: true }))} onChange={(event) => setAcceptedTerms(event.target.checked)} type="checkbox" />I agree to TrustLens data handling terms for my account.</label>{termsError && <p role="alert">{termsError}</p>}</div>
          {isSubmitting && <AsyncState className="auth-error" kind="loading" title="Creating account" />}
          {error && <AsyncState className="error-message auth-error" kind="error" announcement={error}>{error}</AsyncState>}
          <Button className="auth-submit signup-submit" disabled={!formIsValid} loading={isSubmitting} type="submit">{isSubmitting ? 'Creating account…' : 'Create account'}</Button>
        </form>
        <p className="auth-card__footer">Already have an account? <Link to="/login">Sign in</Link></p>
      </section>
    </main>
  )
}
