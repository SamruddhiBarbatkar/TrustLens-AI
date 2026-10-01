import { CircleAlert, CircleCheck, CircleX, Info, LoaderCircle, LockKeyhole } from 'lucide-react'
import { useId } from 'react'

const stateRoles = {
  error: 'alert',
  unauthorized: 'alert',
  loading: 'status',
  success: 'status',
  empty: 'status',
  unavailable: 'status',
}

const stateIcons = {
  error: CircleX,
  unauthorized: LockKeyhole,
  loading: LoaderCircle,
  success: CircleCheck,
  empty: Info,
  unavailable: CircleAlert,
}

export function AsyncState({ actions, announcement, children, className = '', kind = 'loading', title }) {
  const titleId = useId()
  const role = stateRoles[kind] ?? 'status'
  const message = announcement ?? null
  const Icon = stateIcons[kind] ?? Info

  return (
    <section aria-labelledby={title ? titleId : undefined} className={['async-state', `async-state--${kind}`, className].filter(Boolean).join(' ')}>
      {message && <p aria-atomic="true" className="async-state__announcement" role={role}>{message}</p>}
      {title && <div className="async-state__heading"><Icon aria-hidden="true" className={kind === 'loading' ? 'async-state__icon--loading' : undefined} size={21} /><h2 id={titleId}>{title}</h2></div>}
      {children && <div className="async-state__content">{children}</div>}
      {actions && <div className="async-state__actions">{actions}</div>}
    </section>
  )
}
