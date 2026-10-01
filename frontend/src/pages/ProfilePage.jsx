import { ArrowRight, LockKeyhole, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { AsyncState } from '../components/ui/AsyncState'
import { PageHeader } from '../components/ui/PageHeader'
import { getCurrentUser } from '../lib/auth'

function formatCreatedAt(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleDateString()
}

export function ProfilePage() {
  const currentUser = getCurrentUser()
  const hasStoredIdentity = typeof currentUser?.email === 'string' && currentUser.email.length > 0

  if (hasStoredIdentity) {
    const details = [
      currentUser.name && ['Full name', currentUser.name],
      ['Email', currentUser.email],
      currentUser.role && ['Professional role / organization', currentUser.role],
      currentUser.created_at && ['Account created', formatCreatedAt(currentUser.created_at)],
      currentUser.last_login && ['Last sign-in', formatCreatedAt(currentUser.last_login)],
    ].filter(Boolean)

    return (
      <main className="app-page account-page" aria-labelledby="profile-title">
        <PageHeader
          actions={<Link className="secondary-link" to="/settings">Settings availability <ArrowRight aria-hidden="true" size={16} /></Link>}
          className="account-page__header"
          eyebrow="Private workspace"
          title="Profile"
          titleId="profile-title"
        >
          <p className="lede">Safe account details returned during authentication and stored for this browser session.</p>
        </PageHeader>
        <section className="account-security-note account-profile-card" aria-labelledby="account-details-title">
          <UserRound aria-hidden="true" className="account-page__icon" size={24} />
          <p className="eyebrow">Stored account identity</p>
          <h2 id="account-details-title">Signed-in account</h2>
          <p>These fields are read-only. Account updates are not shown until the API supports saving them securely.</p>
          <dl className="profile-details">
            {details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
        </section>
      </main>
    )
  }

  return (
    <main className="app-page account-page" aria-labelledby="profile-title">
      <PageHeader
        actions={<Link className="secondary-link" to="/settings">View settings availability <ArrowRight aria-hidden="true" size={16} /></Link>}
        className="account-page__header"
        eyebrow="Private workspace"
        title="Profile"
        titleId="profile-title"
      >
        <p className="lede">Account details are shown only when safely returned by the authenticated session.</p>
      </PageHeader>
      <AsyncState announcement="Profile details are unavailable because this browser has no stored authenticated identity." className="account-unavailable-card" kind="unavailable" title="Profile details are unavailable.">
        The current TrustLens API does not provide profile data or an account-update endpoint. To avoid displaying incorrect information, no name or email field is shown here.
      </AsyncState>
      <aside className="account-security-note" aria-labelledby="profile-security-title">
        <h2 id="profile-security-title"><LockKeyhole aria-hidden="true" size={19} />Session access</h2>
        <p>You can sign out at any time from the workspace navigation. Profile data remains unavailable until a supported account API is added.</p>
      </aside>
    </main>
  )
}
