export function LoadingSkeleton({ className = '', label = 'Loading content', lines = 3 }) {
  const count = Number.isInteger(lines) && lines > 0 ? lines : 3

  return (
    <div aria-label={label} className={['loading-skeleton', className].filter(Boolean).join(' ')} role="status">
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }, (_, index) => <span aria-hidden="true" className="loading-skeleton__line" key={index} />)}
    </div>
  )
}
