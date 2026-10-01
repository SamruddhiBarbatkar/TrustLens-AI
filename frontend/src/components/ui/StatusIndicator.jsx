const supportedStatuses = new Set(['success', 'warning', 'error', 'unavailable', 'neutral'])

export function StatusIndicator({ children, status = 'neutral' }) {
  const resolvedStatus = supportedStatuses.has(status) ? status : 'neutral'
  return <span className={`status-indicator status-indicator--${resolvedStatus}`}>{children}</span>
}
