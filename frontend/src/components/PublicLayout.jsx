import { Menu, X } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { TrustLensLogo } from './TrustLensLogo'

const publicLinks = [
  { to: '/features', label: 'Features' },
  { to: '/how-it-works', label: 'How it works' },
  { to: '/about', label: 'About' },
]

export function PublicLayout({ children }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const menuButtonRef = useRef(null)

  function closeMenu({ restoreFocus = false } = {}) {
    if (restoreFocus) menuButtonRef.current?.focus()
    setIsMenuOpen(false)
  }

  useEffect(() => {
    if (!isMenuOpen) return undefined

    function handleKeyDown(event) {
      if (event.key === 'Escape') closeMenu({ restoreFocus: true })
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isMenuOpen])

  return (
    <div className="public-shell">
      <header className="public-header">
        <nav className="site-nav" aria-label="Primary navigation">
          <NavLink aria-label="TrustLens home" className="brand" end to="/">
            <TrustLensLogo aria-hidden="true" className="brand__mark" />
            <span>TrustLens</span>
          </NavLink>
          <button aria-controls="public-navigation-links" aria-expanded={isMenuOpen} className="layout-menu-button site-nav__menu-button" onClick={() => setIsMenuOpen((open) => !open)} ref={menuButtonRef} type="button">
            {isMenuOpen ? <X aria-hidden="true" size={18} /> : <Menu aria-hidden="true" size={18} />}
            <span className="sr-only">{isMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}</span>
          </button>
          <div className={`site-nav__links${isMenuOpen ? ' is-open' : ''}`} id="public-navigation-links">
            {publicLinks.map((link) => <NavLink className={({ isActive }) => isActive ? 'is-active' : undefined} key={link.to} to={link.to} onClick={() => closeMenu()}>{link.label}</NavLink>)}
          </div>
          <div className={`site-nav__actions${isMenuOpen ? ' is-open' : ''}`}>
            <NavLink className={({ isActive }) => isActive ? 'is-active' : undefined} to="/login" onClick={() => closeMenu()}>Sign in</NavLink>
            <NavLink className="site-nav__signup" to="/signup" onClick={() => closeMenu()}>Sign up</NavLink>
          </div>
        </nav>
      </header>
      {children}
    </div>
  )
}
