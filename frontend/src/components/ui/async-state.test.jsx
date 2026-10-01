import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { AsyncState } from './AsyncState'

afterEach(cleanup)

describe('AsyncState', () => {
  it('announces a loading state politely and labels its content', () => {
    render(<AsyncState announcement="Loading analyses now." kind="loading" title="Loading analyses">Please wait.</AsyncState>)
    expect(screen.getByRole('status')).toHaveTextContent('Loading analyses')
    expect(screen.getByRole('heading', { name: 'Loading analyses' })).toBeInTheDocument()
  })

  it('uses an assertive alert for errors and retains recovery actions', () => {
    render(<AsyncState actions={<button type="button">Try again</button>} announcement="Unable to load. Try again." kind="error" title="Unable to load">Check your connection.</AsyncState>)
    expect(screen.getByRole('alert')).toHaveTextContent('Unable to load. Try again.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('announces unavailable capabilities without presenting them as success', () => {
    render(<AsyncState announcement="The signal is unavailable." kind="unavailable" title="Signal unavailable">The service did not return a result.</AsyncState>)
    expect(screen.getByRole('status')).toHaveTextContent('The signal is unavailable.')
    expect(screen.getByText('The service did not return a result.')).toBeInTheDocument()
  })

  it.each(['success', 'empty', 'unauthorized'])('uses a distinct semantic state treatment for %s', (kind) => {
    const { container } = render(<AsyncState kind={kind} title={`${kind} state`}>State content.</AsyncState>)
    expect(container.querySelector(`.async-state--${kind}`)).toBeInTheDocument()
    expect(container.querySelector('.async-state__heading svg')).toHaveAttribute('aria-hidden', 'true')
  })
})
