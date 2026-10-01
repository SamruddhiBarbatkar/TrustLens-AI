import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <main className="public-page not-found-page" aria-labelledby="not-found-title">
      <p className="eyebrow">Page not found</p>
      <h1 id="not-found-title">This page is not available.</h1>
      <p className="lede">The link may be outdated, or the page may have moved.</p>
      <Link className="primary-link" to="/">Return home</Link>
    </main>
  )
}
