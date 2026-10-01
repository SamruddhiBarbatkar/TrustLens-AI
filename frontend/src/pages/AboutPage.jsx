import { PublicCallToAction } from '../components/ui/PublicCallToAction'

export function AboutPage() {
  return (
    <main className="public-page" aria-labelledby="about-title">
      <section className="page-hero">
        <p className="eyebrow">About TrustLens</p>
        <h1 id="about-title">Decision support for image review.</h1>
        <p className="lede">
          TrustLens helps people inspect several technical image signals in one place while keeping the limits of those signals clear.
        </p>
      </section>

      <section className="about-grid" aria-label="TrustLens principles">
        <article>
          <h2>Transparent by design</h2>
          <p>Signals, availability states, methods, and limitations are intended to be visible rather than hidden behind a certainty claim.</p>
        </article>
        <article>
          <h2>Private by default</h2>
          <p>Analysis records are associated with the authenticated account that created them, and model assets remain on the server.</p>
        </article>
        <article>
          <h2>Human judgment remains essential</h2>
          <p>TrustLens does not establish provenance, copyright ownership, authenticity, fraud, or intent. It supports—not replaces—careful review.</p>
        </article>
      </section>
      <PublicCallToAction description="TrustLens presents available technical evidence to support human review; it does not provide a verdict." title="Bring evidence into one review workspace." />
    </main>
  )
}
