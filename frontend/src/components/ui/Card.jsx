const supportedTones = new Set(['default', 'subtle', 'accent'])

export function Card({ as: Element = 'section', children, className = '', tone = 'default', ...props }) {
  const resolvedTone = supportedTones.has(tone) ? tone : 'default'
  return <Element {...props} className={['card', `card--${resolvedTone}`, className].filter(Boolean).join(' ')}>{children}</Element>
}
