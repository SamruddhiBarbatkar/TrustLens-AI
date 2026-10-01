export function PageHeader({ actions, children, className = '', eyebrow, title, titleId }) {
  return (
    <header className={['page-header', className].filter(Boolean).join(' ')}>
      <div className="page-header__content">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 id={titleId}>{title}</h1>
        {children && <div className="page-header__description">{children}</div>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  )
}
