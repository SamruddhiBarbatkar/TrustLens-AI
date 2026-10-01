import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const appStyles = readFileSync(resolve(process.cwd(), 'src', 'App.css'), 'utf8')
const globalStyles = readFileSync(resolve(process.cwd(), 'src', 'index.css'), 'utf8')

describe('motion safeguards', () => {
  it('defines brief reusable motion tokens and non-blocking busy feedback', () => {
    expect(globalStyles).toContain('--motion-fast: 120ms;')
    expect(globalStyles).toContain('--motion-base: 180ms;')
    expect(appStyles).toContain('.button[aria-busy="true"]::after')
    expect(appStyles).toContain('@keyframes trustlens-spin')
    expect(appStyles).toContain('@keyframes trustlens-status-pulse')
    expect(appStyles).toContain('.status-indicator--success::before')
  })

  it('limits hover elevation to fine pointer devices', () => {
    expect(appStyles).toContain('@media (hover: hover) and (pointer: fine)')
    expect(appStyles).toContain('transform: translateY(-2px);')
  })

  it('honors reduced-motion preferences for animations and transitions', () => {
    expect(appStyles).toContain('@media (prefers-reduced-motion: reduce)')
    expect(appStyles).toContain('animation-duration: 0.01ms !important;')
    expect(appStyles).toContain('transition-duration: 0.01ms !important;')
  })
})
