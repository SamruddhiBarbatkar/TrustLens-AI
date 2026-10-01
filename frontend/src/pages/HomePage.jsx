import { Activity, ArrowRight, CheckCircle2, CircleAlert, Database, Eye, FileText, Image, LockKeyhole, ScanSearch, ShieldCheck, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'

const capabilities = [
  { icon: ScanSearch, title: 'Tampering detection', description: 'Uses the server-side ResNet18 signal to support review of possible visual tampering.' },
  { icon: Eye, title: 'AI-generated detection', description: 'Uses the server-side EfficientNet-B0 signal to assess whether an image may be AI-generated.' },
  { icon: FileText, title: 'OCR evidence', description: 'EasyOCR returns visible text as supporting evidence when extraction is available.' },
  { icon: Image, title: 'Image quality', description: 'Surfaces returned image-quality measurements, including image dimensions and clarity-related evidence.' },
  { icon: Activity, title: 'Error Level Analysis', description: 'Presents ELA evidence as a forensic-supporting signal, not proof of manipulation.' },
  { icon: ShieldCheck, title: 'Adaptive Trust Score', description: 'The backend combines available directional signals into a transparent decision-support score.' },
]

const pipelineSignals = [
  ['01', 'Tampering', 'Visual tampering signal'],
  ['02', 'AI-generated', 'Generation-likelihood signal'],
  ['03', 'OCR', 'Visible-text evidence'],
  ['04', 'Quality', 'Image-quality evidence'],
  ['05', 'ELA', 'Compression-error evidence'],
]

const workflowSteps = [
  { icon: Upload, title: 'Upload', description: 'Submit a supported image you are authorized to review.' },
  { icon: ScanSearch, title: 'Analyze', description: 'TrustLens runs the available server-side analysis modules.' },
  { icon: Activity, title: 'Combine evidence', description: 'Adaptive multimodal fusion applies the documented Trust Score logic.' },
  { icon: FileText, title: 'Understand results', description: 'Review returned evidence, limitations, explainable analysis, and available reports.' },
]

const useCases = [
  ['Insurance claim verification', 'Use image-analysis evidence to support careful review of submitted claim images.'],
  ['Warranty claim verification', 'Review product or damage images with multiple independent technical signals.'],
  ['Digital image verification', 'Provide an AI-assisted assessment for an image submitted for review.'],
]

export function HomePage() {
  return (
    <main className="public-page landing-page" aria-labelledby="home-title">
      <section className="landing-hero">
        <div className="landing-hero__content">
          <p className="eyebrow">AI-assisted image authenticity verification</p>
          <h1 id="home-title">Verify images. Understand the evidence.</h1>
          <p className="lede">TrustLens brings available tampering, AI-generated-image, OCR, image-quality, and ELA signals into a careful, explainable assessment. It does not provide proof of authenticity or fraud.</p>
          <div className="landing-actions">
            <Link className="primary-link" to="/signup">Create an account <ArrowRight aria-hidden="true" size={17} /></Link>
            <Link className="secondary-link" to="/how-it-works">How it works</Link>
          </div>
          <ul className="landing-hero__assurances" aria-label="TrustLens principles">
            <li><LockKeyhole aria-hidden="true" size={16} />Private workspace</li>
            <li><ShieldCheck aria-hidden="true" size={16} />Evidence, not a verdict</li>
          </ul>
        </div>

        <aside className="landing-hero__visual landing-capability-panel" aria-labelledby="capability-panel-title">
          <div className="landing-capability-panel__header">
            <div>
              <p className="landing-capability-panel__eyebrow">Analysis pipeline</p>
              <h2 id="capability-panel-title">One image. Multiple signals.</h2>
            </div>
            <ScanSearch aria-hidden="true" size={22} />
          </div>
          <ol className="landing-pipeline" aria-label="TrustLens analysis stages">
            {pipelineSignals.map(([number, title, detail]) => <li key={title}><span>{number}</span><strong>{title}</strong><small>{detail}</small></li>)}
            <li className="landing-pipeline__score"><span>06</span><strong>Trust Score</strong><small>Server-calculated decision support</small></li>
          </ol>
          <p className="landing-capability-panel__note"><CircleAlert aria-hidden="true" size={16} />Conceptual workflow only. Signals remain explicit when unavailable or limited.</p>
        </aside>
      </section>

      <section className="landing-section" aria-labelledby="capabilities-title">
        <p className="eyebrow">Available capabilities</p>
        <h2 id="capabilities-title">A review built from independent evidence.</h2>
        <p className="landing-section__lede">Each completed analysis makes the returned signals and their limitations visible for human review.</p>
        <div className="landing-signal-grid">
          {capabilities.map(({ icon: Icon, title, description }, index) => (
            <article className="landing-signal-card" key={title}>
              <div className="landing-signal-card__topline"><span className="landing-signal-card__number">0{index + 1}</span><Icon aria-hidden="true" size={22} /></div>
              <h3>{title}</h3><p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-intelligence" aria-labelledby="intelligence-title">
        <div><p className="eyebrow">Multimodal intelligence</p><h2 id="intelligence-title">One image. Multiple signals.</h2><p>TrustLens keeps individual evidence visible before presenting the server-derived Trust Score. OCR, image quality, and ELA remain contextual evidence; no signal alone decides the outcome.</p></div>
        <div className="landing-fusion" aria-label="Multiple signal categories feed adaptive multimodal fusion">
          <div className="landing-fusion__signals">{pipelineSignals.map(([, title, detail]) => <div key={title}><CheckCircle2 aria-hidden="true" size={17} /><span><strong>{title}</strong><small>{detail}</small></span></div>)}</div>
          <div className="landing-fusion__outcome"><Activity aria-hidden="true" size={22} /><strong>Adaptive multimodal fusion</strong><span>Trust Score and explainable analysis returned by the server</span></div>
        </div>
      </section>

      <section className="landing-score-section" id="explainable-analysis" aria-labelledby="score-title">
        <div className="landing-score-section__heading"><p className="eyebrow">Explainable analysis</p><h2 id="score-title">Understand why a score was returned.</h2><p>Completed analyses can present the server-returned score explanation, signal evidence, fusion factors, and limitations alongside the result.</p></div>
        <div className="landing-score-categories" aria-label="Trust Score categories">
          <div><span>80–100</span><strong>Likely Authentic</strong><p>Decision support only.</p></div>
          <div><span>50–79</span><strong>Needs Review</strong><p>Additional inspection may help.</p></div>
          <div><span>0–49</span><strong>Potentially Suspicious</strong><p>Not proof of manipulation.</p></div>
        </div>
      </section>

      <section className="landing-workflow" aria-labelledby="workflow-title">
        <div><p className="eyebrow">How it works</p><h2 id="workflow-title">A focused path from upload to review.</h2></div>
        <ol>
          {workflowSteps.map(({ icon: Icon, title, description }) => <li key={title}><Icon aria-hidden="true" size={18} /><strong>{title}</strong><span>{description}</span></li>)}
        </ol>
      </section>

      <section className="landing-use-cases" aria-labelledby="use-cases-title">
        <p className="eyebrow">Built for image-review workflows</p><h2 id="use-cases-title">Use evidence to support better verification decisions.</h2>
        <div>{useCases.map(([title, description]) => <article key={title}><ShieldCheck aria-hidden="true" size={20} /><h3>{title}</h3><p>{description}</p></article>)}</div>
      </section>

      <section className="landing-security-report" aria-labelledby="security-title">
        <div><p className="eyebrow">Private by design</p><h2 id="security-title">Your review history stays tied to your account.</h2><p>TrustLens uses authenticated access, owner-scoped records and reports, controlled uploads, and environment-based configuration. It does not claim external compliance certifications.</p></div>
        <div className="landing-report-flow"><Database aria-hidden="true" size={22} /><span>Completed analysis</span><ArrowRight aria-hidden="true" size={17} /><span>Evidence and explanation</span><ArrowRight aria-hidden="true" size={17} /><span>Owner-scoped PDF report</span></div>
      </section>

      <aside className="landing-limitation" aria-labelledby="limitation-title">
        <p className="eyebrow">Important limitation</p><h2 id="limitation-title">Evidence is not a verdict.</h2>
        <p>TrustLens does not prove authenticity, fraud, provenance, ownership, copyright, or intent. Interpret every available signal with appropriate human judgment.</p>
        <Link className="secondary-link" to="/features">Explore available signals</Link>
      </aside>

      <footer className="landing-footer" aria-label="TrustLens links">
        <div><strong>TrustLens AI</strong><p>AI-assisted image authenticity verification using multimodal analysis.</p></div>
        <nav aria-label="Product links"><strong>Product</strong><Link to="/features">Features</Link><Link to="/how-it-works">How it works</Link><a href="#explainable-analysis">Explainable analysis</a></nav>
        <nav aria-label="Application links"><strong>Application</strong><Link to="/login">Log in</Link><Link to="/signup">Get started</Link><Link to="/about">About</Link></nav>
        <p className="landing-footer__copyright">© 2026 TrustLens AI</p>
      </footer>
    </main>
  )
}
