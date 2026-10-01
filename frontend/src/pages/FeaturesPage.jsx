import { PublicCallToAction } from '../components/ui/PublicCallToAction'

const features = [
  {
    title: 'Visual tampering signal',
    description: 'A backend-only model examines visual patterns associated with the supplied tampering detector contract.',
  },
  {
    title: 'AI-generation signal',
    description: 'A separate backend-only model reports its recorded AI-image classification signal when available.',
  },
  {
    title: 'Text extraction',
    description: 'OCR identifies visible text and confidence values so you can review image context yourself.',
  },
  {
    title: 'Image-quality evidence',
    description: 'Returned image dimensions and clarity-related measurements remain supporting context for review.',
  },
  {
    title: 'Compression evidence',
    description: 'Error Level Analysis measures JPEG recompression differences and explains its limits.',
  },
]

export function FeaturesPage() {
  return (
    <main className="public-page" aria-labelledby="features-title">
      <section className="page-hero">
        <p className="eyebrow">TrustLens capabilities</p>
        <h1 id="features-title">Signals to help you look closer.</h1>
        <p className="lede">
          TrustLens brings several server-side image signals into one review workflow. Each signal is evidence to consider, not proof of authenticity, fraud, ownership, or intent.
        </p>
      </section>

      <section className="feature-grid" aria-label="TrustLens features">
        {features.map((feature) => (
          <article className="feature-card" key={feature.title}>
            <h2>{feature.title}</h2>
            <p>{feature.description}</p>
          </article>
        ))}
      </section>

      <aside className="limitations-callout" aria-label="Important limitation">
        <h2>Evidence, not a verdict</h2>
        <p>
          Images can be resized, compressed, edited, or sourced from incomplete context. Review available signals alongside the source and the circumstances in which an image was shared.
        </p>
      </aside>
      <PublicCallToAction description="Create a private workspace to submit an authorized image and review only the signals the server returns." title="Ready to review an image with context?" />
    </main>
  )
}
