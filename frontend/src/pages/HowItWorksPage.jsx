import { PublicCallToAction } from '../components/ui/PublicCallToAction'

const steps = [
  ['1', 'Choose an image', 'Submit an image you are authorized to review. Files are processed by the server, not the browser.'],
  ['2', 'Validate and prepare', 'TrustLens validates the uploaded image before it is made available to analysis services.'],
  ['3', 'Collect available signals', 'Tampering, AI-generation, OCR, image-quality, and ELA checks run independently so unavailable services stay visible.'],
  ['4', 'Review with context', 'Use the returned evidence and limitations to decide what deserves further human review.'],
]

export function HowItWorksPage() {
  return (
    <main className="public-page" aria-labelledby="how-title">
      <section className="page-hero">
        <p className="eyebrow">How it works</p>
        <h1 id="how-title">A clear path from image to review.</h1>
        <p className="lede">
          TrustLens keeps the process transparent: every check is separate, unavailable services are identified, and no single signal is presented as conclusive.
        </p>
      </section>

      <ol className="process-list">
        {steps.map(([number, title, description]) => (
          <li key={number}>
            <span className="step-number" aria-hidden="true">{number}</span>
            <div>
              <h2>{title}</h2>
              <p>{description}</p>
            </div>
          </li>
        ))}
      </ol>
      <PublicCallToAction description="Start an authorized image review in a private workspace. Completed evidence and report access stay tied to your account." title="Start a careful image review." />
    </main>
  )
}
