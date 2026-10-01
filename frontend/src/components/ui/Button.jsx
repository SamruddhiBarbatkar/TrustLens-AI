const supportedVariants = new Set(['primary', 'secondary', 'ghost', 'danger'])

export function Button({ children, className = '', loading = false, variant = 'primary', type = 'button', ...props }) {
  const resolvedVariant = supportedVariants.has(variant) ? variant : 'primary'
  const classes = ['button', `button--${resolvedVariant}`, className].filter(Boolean).join(' ')

  return (
    <button {...props} aria-busy={loading || undefined} className={classes} disabled={loading || props.disabled} type={type}>
      {children}
    </button>
  )
}
