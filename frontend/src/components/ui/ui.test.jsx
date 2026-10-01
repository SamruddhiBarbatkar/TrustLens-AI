import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Button } from './Button'
import { Badge } from './Badge'
import { Card } from './Card'
import { LoadingSkeleton } from './LoadingSkeleton'
import { MetricCard } from './MetricCard'
import { PageHeader } from './PageHeader'
import { StatusIndicator } from './StatusIndicator'

describe('design-system primitives', () => {
  it('renders an accessible loading button', () => {
    render(<Button loading type="submit">Save</Button>)
    const button = screen.getByRole('button', { name: 'Save' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toHaveClass('button--primary')
  })

  it('renders a card with its semantic element', () => {
    render(<Card as="article">Evidence</Card>)
    expect(screen.getByText('Evidence').closest('article')).toHaveClass('card')
  })

  it('renders supported statuses and safely falls back to neutral', () => {
    const { rerender } = render(<StatusIndicator status="success">Available</StatusIndicator>)
    expect(screen.getByText('Available')).toHaveClass('status-indicator--success')
    rerender(<StatusIndicator status="unknown">Waiting</StatusIndicator>)
    expect(screen.getByText('Waiting')).toHaveClass('status-indicator--neutral')
  })

  it('provides semantic card, button, and badge variants with safe fallbacks', () => {
    render(<><Button variant="danger">Remove</Button><Card tone="accent">Summary</Card><Badge tone="success">Completed</Badge></>)
    expect(screen.getByRole('button', { name: 'Remove' })).toHaveClass('button--danger')
    expect(screen.getByText('Summary')).toHaveClass('card--accent')
    expect(screen.getByText('Completed')).toHaveClass('badge--success')
  })

  it('renders reusable headers, real-or-unavailable metrics, and labelled loading placeholders', () => {
    render(<><PageHeader eyebrow="Overview" title="Analysis workspace">Review returned evidence.</PageHeader><MetricCard detail="Returned by the API" label="Trust Score" value={null} /><LoadingSkeleton label="Loading analysis history" lines={2} /></>)
    expect(screen.getByRole('heading', { name: 'Analysis workspace' })).toBeInTheDocument()
    expect(screen.getByText('Not available')).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Loading analysis history' })).toBeInTheDocument()
  })
})
