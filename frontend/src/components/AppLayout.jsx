import { BarChart3, ChevronLeft, ChevronRight, FileText, History, LogOut, Menu, ScanSearch, Settings, UserRound, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { clearAccessToken } from '../lib/auth'
import { Button } from './ui/Button'
import { TrustLensLogo } from './TrustLensLogo'

const workspaceLinks = [
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  { to: '/analyze', label: 'Analyze image', icon: ScanSearch },
  { to: '/history', label: 'History', icon: History },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/profile', label: 'Profile', icon: UserRound },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function AppLayout({ children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const mobileMenuButtonRef = useRef(null)
  const currentPage = workspaceLinks.find((link) => link.to === location.pathname)?.label
    ?? (location.pathname.startsWith('/results/') ? 'Analysis results' : 'Private workspace')

  function signOut() {
    clearAccessToken()
    navigate('/', { replace: true })
  }

  function closeMobileNavigation({ restoreFocus = false } = {}) {
    if (restoreFocus) mobileMenuButtonRef.current?.focus()
    setIsMobileNavOpen(false)
  }

  useEffect(() => {
    if (!isMobileNavOpen) return undefined

    function handleKeyDown(event) {
      if (event.key === 'Escape') closeMobileNavigation({ restoreFocus: true })
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isMobileNavOpen])

  function renderWorkspaceLink(link) {
    const Icon = link.icon
    return (
      <NavLink aria-label={link.label} className={({ isActive }) => isActive ? 'is-active' : undefined} key={link.to} title={isSidebarCollapsed ? link.label : undefined} to={link.to} onClick={() => closeMobileNavigation()}>
        <Icon aria-hidden="true" size={18} />
        <span className="workspace-nav__label">{link.label}</span>
      </NavLink>
    )
  }

  return (
    <div className={`workspace-shell${isSidebarCollapsed ? ' is-sidebar-collapsed' : ''}`}>
      <aside className="workspace-sidebar">
        <button aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-pressed={isSidebarCollapsed} className="workspace-sidebar__toggle" onClick={() => setIsSidebarCollapsed((collapsed) => !collapsed)} type="button">{isSidebarCollapsed ? <ChevronRight aria-hidden="true" size={18} /> : <ChevronLeft aria-hidden="true" size={18} />}</button>
        <NavLink aria-label="TrustLens dashboard" className="brand workspace-brand" end to="/dashboard">
          <TrustLensLogo aria-hidden="true" className="brand__mark" />
          <span className="workspace-nav__label">TrustLens</span>
        </NavLink>
        <p className="workspace-label">Private workspace</p>
        <nav className="workspace-nav" aria-label="Workspace navigation">
          {workspaceLinks.map(renderWorkspaceLink)}
        </nav>
        <Button aria-label="Sign out" className="workspace-signout" onClick={signOut} title={isSidebarCollapsed ? 'Sign out' : undefined} variant="ghost"><LogOut aria-hidden="true" size={17} /><span className="workspace-nav__label">Sign out</span></Button>
      </aside>
      <div className="workspace-content">
        <header className="workspace-command-bar" aria-label="Workspace command bar"><div><p>Private workspace</p><strong>{currentPage}</strong></div><div className="workspace-command-bar__actions"><span>Owner-scoped data</span><NavLink aria-label="Open profile" to="/profile"><UserRound aria-hidden="true" size={18} /></NavLink></div></header>
        <header className="workspace-mobile-header">
          <div className="workspace-mobile-header__context"><NavLink aria-label="TrustLens dashboard" className="brand" end to="/dashboard"><TrustLensLogo aria-hidden="true" className="brand__mark" /><span>TrustLens</span></NavLink><span>{currentPage}</span></div>
          <div className="workspace-mobile-header__actions">
            <Button className="workspace-mobile-signout" onClick={signOut} variant="ghost"><LogOut aria-hidden="true" size={17} /><span className="sr-only">Sign out</span></Button>
            <button aria-controls="workspace-mobile-navigation" aria-expanded={isMobileNavOpen} className="layout-menu-button" onClick={() => setIsMobileNavOpen((open) => !open)} ref={mobileMenuButtonRef} type="button">
              {isMobileNavOpen ? <X aria-hidden="true" size={18} /> : <Menu aria-hidden="true" size={18} />}
              <span className="sr-only">{isMobileNavOpen ? 'Close workspace navigation' : 'Open workspace navigation'}</span>
            </button>
          </div>
        </header>
        {isMobileNavOpen && <div className="workspace-mobile-drawer" role="presentation"><button aria-label="Close workspace navigation" className="workspace-mobile-drawer__overlay" onClick={() => closeMobileNavigation({ restoreFocus: true })} type="button" /><nav aria-label="Mobile workspace navigation" className="workspace-mobile-nav" id="workspace-mobile-navigation"><div className="workspace-mobile-nav__header"><span>Navigate workspace</span><button aria-label="Close workspace navigation" className="workspace-mobile-nav__close" onClick={() => closeMobileNavigation({ restoreFocus: true })} type="button"><X aria-hidden="true" size={18} /></button></div>{workspaceLinks.map(renderWorkspaceLink)}</nav></div>}
        {children}
      </div>
    </div>
  )
}
