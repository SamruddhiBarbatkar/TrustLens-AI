const supportedTones = new Set(['neutral', 'info', 'success', 'warning', 'danger'])

export function Badge({ children, className = '', tone = 'neutral' }) {
  const resolvedTone = supportedTones.has(tone) ? tone : 'neutral'
  return <span className={['badge', `badge--${resolvedTone}`, className].filter(Boolean).join(' ')}>{children}</span>
}
