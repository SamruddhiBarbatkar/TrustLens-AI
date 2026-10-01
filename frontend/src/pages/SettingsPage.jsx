import { ArrowRight, LockKeyhole } from 'lucide-react'
import { Link } from 'react-router-dom'
import { AsyncState } from '../components/ui/AsyncState'
import { PageHeader } from '../components/ui/PageHeader'

export function SettingsPage() {
  return (
    <main className="app-page account-page" aria-labelledby="settings-title">
      <PageHeader
        actions={<Link className="secondary-link" to="/profile">View profile <ArrowRight aria-hidden="true" size={16} /></Link>}
        className="account-page__header"
        eyebrow="Private workspace"
        title="Settings"
        titleId="settings-title"
      >
        <p className="lede">Preference and account changes appear here only when they can be saved by an authenticated API.</p>
      </PageHeader>
      <AsyncState announcement="Saved settings are unavailable because this API capability is not supported." className="account-unavailable-card" kind="unavailable" title="Saved settings are unavailable.">
        The current TrustLens API does not provide saved preferences, notification controls, password changes, or account-update operations. No editable settings are shown until they can be saved securely.
      </AsyncState>
      <aside className="account-security-note" aria-labelledby="settings-security-title">
        <h2 id="settings-security-title"><LockKeyhole aria-hidden="true" size={19} />Account safety</h2>
        <p>Use the workspace sign-out action when you are finished. TrustLens does not expose account settings in the browser without a supported authenticated API.</p>
      </aside>
    </main>
  )
}
