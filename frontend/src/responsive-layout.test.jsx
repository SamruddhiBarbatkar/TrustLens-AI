import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const appStyles = readFileSync(resolve(process.cwd(), 'src', 'App.css'), 'utf8')
const globalStyles = readFileSync(resolve(process.cwd(), 'src', 'index.css'), 'utf8')

describe('responsive layout safeguards', () => {
  it('keeps global visual content and controls within narrow viewports', () => {
    expect(globalStyles).toContain('min-width: 0;')
    expect(globalStyles).toContain('max-width: 100%;')
    expect(globalStyles).toContain('touch-action: manipulation;')
  })

  it('uses an accessible workspace drawer below the tablet breakpoint', () => {
    expect(appStyles).toContain('@media (max-width: 48rem)')
    expect(appStyles).toContain('.workspace-mobile-drawer { display: block; position: fixed; z-index: 30; inset: 0; }')
    expect(appStyles).toContain('.workspace-mobile-drawer__overlay')
    expect(appStyles).toContain('.workspace-mobile-nav__close')
    expect(appStyles).toContain('min-height: 2.75rem;')
  })

  it('provides a compact layout for very narrow screens', () => {
    expect(appStyles).toContain('@media (max-width: 30rem)')
    expect(appStyles).toContain('flex: 1 1 100%;')
    expect(appStyles).toContain('overflow-wrap: anywhere;')
    expect(appStyles).toContain('.trust-score-card { grid-template-columns: 1fr; justify-items: start; }')
    expect(appStyles).toContain('.analysis-file-field__dropzone { min-height: 7.5rem;')
  })
})
