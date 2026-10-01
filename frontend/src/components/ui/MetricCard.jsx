export function MetricCard({ className = '', detail, icon: Icon, label, value }) {
  const hasValue = value !== null && value !== undefined && value !== ''

  return (
    <article className={['metric-card', className].filter(Boolean).join(' ')}>
      <div className="metric-card__heading">
        {Icon && <span className="metric-card__icon"><Icon aria-hidden="true" size={18} /></span>}
        <span>{label}</span>
      </div>
      <strong className={hasValue ? '' : 'metric-card__value--unavailable'}>{hasValue ? value : 'Not available'}</strong>
      {detail && <small>{detail}</small>}
    </article>
  )
}
