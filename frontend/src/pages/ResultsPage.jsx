import { Activity, FileText, Image, ImageOff, ScanSearch, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { fetchAnalysisHistory, fetchSourceImage } from '../lib/api'
import { clearAccessToken, getAccessToken } from '../lib/auth'
import { Button } from '../components/ui/Button'
import { AsyncState } from '../components/ui/AsyncState'
import { StatusIndicator } from '../components/ui/StatusIndicator'

const signalLabels = {
  tampering: 'Tampering detection',
  ai_generation: 'AI-generated detection',
  ocr: 'OCR',
  quality: 'Image quality',
  ela: 'Error level analysis',
}

const signalIcons = {
  tampering: ScanSearch,
  ai_generation: Sparkles,
  ocr: FileText,
  quality: Image,
  ela: Activity,
}

function isAnalysis(value, analysisId) {
  return value && value.id === analysisId && value.signals && typeof value.signals === 'object'
}

function statusVariant(status) {
  if (status === 'available') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'unavailable') return 'unavailable'
  return 'neutral'
}

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString()
}

function formatPercent(value) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : 'Not returned'
}

function formatScore(value) {
  return typeof value === 'number' ? `${value}/100` : 'Not returned'
}

function Term({ children, description }) {
  return <abbr className="result-term" title={description}>{children}</abbr>
}

function ExplanationDetail({ explanation, title = 'Explanation' }) {
  if (!explanation || typeof explanation !== 'object') return null
  const limitations = Array.isArray(explanation.limitations) ? explanation.limitations : []
  return (
    <details className="result-explanation-detail">
      <summary>{title}</summary>
      {typeof explanation.interpretation === 'string' && <p>{explanation.interpretation}</p>}
      {typeof explanation.contribution === 'string' && <p><strong>Contribution:</strong> {explanation.contribution}</p>}
      {Array.isArray(explanation.observations) && explanation.observations.length > 0 && <ul>{explanation.observations.map((observation) => <li key={observation}>{observation}</li>)}</ul>}
      {limitations.length > 0 && <ul className="result-limitations">{limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>}
    </details>
  )
}

function SignalCard({ children, name, signal, signalName }) {
  const status = signal?.status ?? 'unavailable'
  const message = signal?.message ?? (signal ? 'No additional message was returned.' : 'This signal is not returned by the current analysis API.')
  const Icon = signalIcons[signalName] ?? Activity

  return (
    <article className="result-signal-card">
      <div className="result-signal-card__heading">
        <h2><span className="result-signal-card__icon"><Icon aria-hidden="true" size={19} /></span>{name}</h2>
        <StatusIndicator status={statusVariant(status)}>{status}</StatusIndicator>
      </div>
      {status === 'available' ? children : <p className="result-signal-card__message">{message}</p>}
    </article>
  )
}

function GradCAMEvidence({ value }) {
  if (typeof value !== 'string' || !value.startsWith('data:image/png;base64,')) return null
  return <figure className="result-gradcam"><img alt="Grad-CAM regions influencing this model prediction" src={value} /><figcaption>Grad-CAM: regions influencing this model prediction. This is explanatory evidence, not proof or a tampering mask.</figcaption></figure>
}

function TamperingResult({ explanation, signal }) {
  const result = signal?.result ?? {}
  return (
    <SignalCard name={signalLabels.tampering} signal={signal} signalName="tampering">
      <dl className="result-fact-list">
        <div><dt>Model signal</dt><dd>{typeof result.label === 'string' ? result.label : 'Not returned'}</dd></div>
        <div><dt>Top-class score</dt><dd>{formatPercent(result.top_class_softmax_score)}</dd></div>
      </dl>
      <GradCAMEvidence value={result.gradcam_data_url} />
      {typeof result.preprocessing_note === 'string' && <p className="result-note">{result.preprocessing_note}</p>}
      <ExplanationDetail explanation={explanation} title="What this classification means" />
    </SignalCard>
  )
}

function AIGenerationResult({ explanation, signal }) {
  const result = signal?.result ?? {}
  return (
    <SignalCard name={signalLabels.ai_generation} signal={signal} signalName="ai_generation">
      <dl className="result-fact-list">
        <div><dt>Model signal</dt><dd>{typeof result.label === 'string' ? result.label : 'Not returned'}</dd></div>
        <div><dt>Top-class score</dt><dd>{formatPercent(result.top_class_softmax_score)}</dd></div>
      </dl>
      <GradCAMEvidence value={result.gradcam_data_url} />
      {typeof result.preprocessing_note === 'string' && <p className="result-note">{result.preprocessing_note}</p>}
      <ExplanationDetail explanation={explanation} title="What this classification means" />
    </SignalCard>
  )
}

function OCRResult({ explanation, signal }) {
  const regions = Array.isArray(signal?.result?.regions) ? signal.result.regions : []
  return (
    <SignalCard name={signalLabels.ocr} signal={signal} signalName="ocr">
      {regions.length === 0 ? <p className="result-signal-card__message">No text regions were returned.</p> : (
        <ul className="ocr-region-list">
          {regions.map((region, index) => (
            <li key={`${region.text ?? 'region'}-${index}`}>
              <strong>{typeof region.text === 'string' ? region.text : 'Text unavailable'}</strong>
              <span>Confidence: {formatPercent(region.confidence)}</span>
            </li>
          ))}
        </ul>
      )}
      <ExplanationDetail explanation={explanation} title="What the OCR result means" />
    </SignalCard>
  )
}

function ELAResult({ explanation, signal }) {
  const result = signal?.result ?? {}
  const limitations = Array.isArray(result.limitations) ? result.limitations : []
  return (
    <SignalCard name={signalLabels.ela} signal={signal} signalName="ela">
      <dl className="result-fact-list">
        <div><dt>Mean difference</dt><dd>{typeof result.mean_absolute_difference === 'number' ? result.mean_absolute_difference.toFixed(2) : 'Not returned'}</dd></div>
        <div><dt>Differing pixels</dt><dd>{formatPercent(result.differing_pixel_fraction)}</dd></div>
        <div><dt>Recompression quality</dt><dd>{typeof result.recompression_quality === 'number' ? result.recompression_quality : 'Not returned'}</dd></div>
      </dl>
      {typeof result.method === 'string' && <p className="result-note">Method: {result.method}</p>}
      {limitations.length > 0 && <ul className="result-limitations">{limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>}
      <ExplanationDetail explanation={explanation} title="What this ELA result means" />
    </SignalCard>
  )
}

function QualityResult({ explanation, signal }) {
  const result = signal?.result ?? {}
  return (
    <SignalCard name={signalLabels.quality} signal={signal} signalName="quality">
      <dl className="result-fact-list">
        <div><dt>Dimensions</dt><dd>{typeof result.width === 'number' && typeof result.height === 'number' ? `${result.width} × ${result.height}` : 'Not returned'}</dd></div>
        <div><dt>Mean brightness</dt><dd>{typeof result.brightness_mean === 'number' ? result.brightness_mean.toFixed(2) : 'Not returned'}</dd></div>
        <div><dt>Contrast deviation</dt><dd>{typeof result.contrast_standard_deviation === 'number' ? result.contrast_standard_deviation.toFixed(2) : 'Not returned'}</dd></div>
        <div><dt>Sharpness variance</dt><dd>{typeof result.sharpness_laplacian_variance === 'number' ? result.sharpness_laplacian_variance.toFixed(2) : 'Not returned'}</dd></div>
      </dl>
      {typeof result.method === 'string' && <p className="result-note">Method: {result.method}</p>}
      <ExplanationDetail explanation={explanation} title="What these quality measurements mean" />
    </SignalCard>
  )
}

export function TrustScoreCard({ trustScore }) {
  if (!trustScore || typeof trustScore.score !== 'number') {
    return (
      <section className="trust-score-card" aria-labelledby="trust-score-title">
        <div className="trust-score-card__visual" aria-label="Trust Score unavailable">—</div>
        <div>
          <p className="eyebrow">Trust Score</p>
          <h2 id="trust-score-title">Not available</h2>
          <p>The server did not return a Trust Score because no verified model output was available to calculate one.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="trust-score-card" aria-labelledby="trust-score-title">
      <div className="trust-score-card__visual" aria-label={`Trust Score ${trustScore.score} out of 100`} style={{ '--trust-score-degrees': `${trustScore.score * 3.6}deg` }}><span>{trustScore.score}</span><small>/100</small></div>
      <div>
        <p className="eyebrow">Adaptive Trust Score</p>
        <h2 id="trust-score-title">{formatScore(trustScore.score)} · {trustScore.category}</h2>
        <p>This score is the value returned by the server from the currently available, verified-direction model signals. It is decision support, not proof.</p>
      </div>
    </section>
  )
}

function ResultModuleRail({ signals, trustScore }) {
  const modules = Object.keys(signalLabels).map((name) => {
    const signal = signals[name]
    return { Icon: signalIcons[name] ?? Activity, name, status: signal?.status ?? 'unavailable' }
  })

  return (
    <aside className="results-module-rail" aria-label="Analysis module breakdown">
      <section className="results-module-rail__score">
        <p className="eyebrow">Score breakdown</p>
        {typeof trustScore?.score === 'number' ? <><strong aria-label={`Trust Score ${trustScore.score} out of 100`}>{formatScore(trustScore.score)}</strong><span>{trustScore.category}</span><p>This server-returned score is decision support, not proof.</p></> : <><strong>Not available</strong><span>The server did not return a Trust Score.</span></>}
      </section>
      <section className="results-module-rail__modules" aria-labelledby="module-rail-title">
        <h2 id="module-rail-title">Available analysis modules</h2>
        <ul>
          {modules.map(({ Icon, name, status }) => <li key={name}><span className="results-module-rail__icon"><Icon aria-hidden="true" size={17} /></span><span>{signalLabels[name]}</span><StatusIndicator status={statusVariant(status)}>{status}</StatusIndicator></li>)}
        </ul>
      </section>
      <p className="results-module-rail__note">Modules remain explicit when unavailable. Availability alone is not a conclusion.</p>
    </aside>
  )
}

function FactorList({ factors, title }) {
  if (!Array.isArray(factors) || factors.length === 0) return null
  return (
    <section className="result-factor-list" aria-label={title}>
      <h3>{title}</h3>
      <ul>{factors.map((factor, index) => <li key={`${factor.signal ?? 'factor'}-${index}`}>{typeof factor.explanation === 'string' ? factor.explanation : 'Explanation was not returned.'}</li>)}</ul>
    </section>
  )
}

function ExplainableSummary({ explanation }) {
  if (!explanation || typeof explanation !== 'object') {
    return (
      <section className="results-xai results-xai--unavailable" aria-labelledby="xai-title">
        <p className="eyebrow">Explainable AI</p>
        <h2 id="xai-title">Structured explanation unavailable</h2>
        <p>This saved analysis was created before TrustLens stored explainable evidence. The returned signal values above remain the available record.</p>
      </section>
    )
  }

  const score = explanation.trust_score
  const fusion = explanation.fusion
  return (
    <section className="results-xai" aria-labelledby="xai-title">
      <div>
        <p className="eyebrow">Explainable AI</p>
        <h2 id="xai-title">What TrustLens found</h2>
        <p>{typeof explanation.overall_summary === 'string' ? explanation.overall_summary : 'No overall explanation was returned for this analysis.'}</p>
      </div>
      <details className="results-xai__details" open>
        <summary>Why this score?</summary>
        {typeof score?.explanation === 'string' ? <p>{score.explanation}</p> : <p>The server did not return a Trust Score explanation.</p>}
        <FactorList factors={score?.contributing_factors} title="Evidence supporting authenticity" />
        <FactorList factors={score?.caution_factors} title="Evidence requiring review" />
      </details>
      <details className="results-xai__details">
        <summary>How <Term description="TrustLens combines the available model signals that have a verified authenticity-direction mapping.">multimodal fusion</Term> used the signals</summary>
        {typeof fusion?.explanation === 'string' ? <p>{fusion.explanation}</p> : <p>The server did not return a fusion explanation.</p>}
        {Array.isArray(fusion?.signals_considered) && fusion.signals_considered.length > 0 && <p>Signals considered: {fusion.signals_considered.map((name) => signalLabels[name] ?? name).join(', ')}.</p>}
      </details>
    </section>
  )
}

function Limitations({ explanation, trustScore }) {
  const limitations = Array.isArray(explanation?.limitations) && explanation.limitations.length > 0
    ? explanation.limitations
    : (Array.isArray(trustScore?.limitations) ? trustScore.limitations : [])
  return (
    <aside className="results-caveat" aria-labelledby="results-caveat-title">
      <h2 id="results-caveat-title">Limitations to consider</h2>
      {limitations.length > 0 ? <ul className="result-limitations">{limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul> : <p>No structured limitations were returned for this saved analysis. Treat all returned signals as decision support, not proof.</p>}
      <p>Confidence is a model’s recorded output, not proof. <Term description="Error Level Analysis compares the image with a controlled JPEG recompression.">ELA</Term>, <Term description="Sharpness is reported as a calculated Laplacian variance and is image-quality context only.">sharpness</Term>, OCR, and model classifications require human review in context.</p>
    </aside>
  )
}

function SourceImageArtifact({ analysis }) {
  const [state, setState] = useState({ status: analysis.source_image_available ? 'loading' : 'unavailable', url: null })

  useEffect(() => {
    if (!analysis.source_image_available) return undefined
    let active = true
    let objectUrl = null

    async function loadSourceImage() {
      try {
        const image = await fetchSourceImage(analysis.id, getAccessToken())
        if (!active || typeof URL.createObjectURL !== 'function') return
        objectUrl = URL.createObjectURL(image)
        setState({ status: 'available', url: objectUrl })
      } catch {
        if (active) setState({ status: 'unavailable', url: null })
      }
    }

    loadSourceImage()
    return () => {
      active = false
      if (objectUrl && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(objectUrl)
    }
  }, [analysis.id, analysis.source_image_available])

  if (state.status === 'available' && state.url) {
    return (
      <article className="results-artifact results-artifact--image">
        <img alt="Uploaded image used for this analysis" src={state.url} />
        <div><h3>Uploaded image</h3><p>Owner-authorized source image retained with this saved analysis.</p></div>
      </article>
    )
  }

  if (state.status === 'loading') {
    return <article className="results-artifact results-artifact--loading" aria-live="polite"><Image aria-hidden="true" size={29} /><h3>Loading uploaded image</h3><p>Retrieving your owner-authorized source image.</p></article>
  }

  return <article className="results-artifact"><ImageOff aria-hidden="true" size={29} /><h3>Original image unavailable</h3><p>This saved analysis does not include a retained uploaded image.</p></article>
}

async function findAnalysis(analysisId) {
  const data = await fetchAnalysisHistory(getAccessToken(), 50)
  return data.items.find((item) => item.id === analysisId) ?? null
}

export function ResultsPage() {
  const { analysisId } = useParams()
  const location = useLocation()
  const stateAnalysis = isAnalysis(location.state?.analysis, analysisId) ? location.state.analysis : null
  const [state, setState] = useState(() => stateAnalysis ? { status: 'ready', analysis: stateAnalysis } : { status: 'loading', analysis: null })

  useEffect(() => {
    if (stateAnalysis) return undefined
    let isCurrent = true

    async function loadAnalysis() {
      try {
        const analysis = await findAnalysis(analysisId)
        if (isCurrent) setState(analysis ? { status: 'ready', analysis } : { status: 'missing', analysis: null })
      } catch (error) {
        if (!isCurrent) return
        if (error.status === 401) {
          clearAccessToken()
          setState({ status: 'unauthorized', analysis: null })
          return
        }
        setState({ status: 'error', analysis: null })
      }
    }

    loadAnalysis()
    return () => { isCurrent = false }
  }, [analysisId, stateAnalysis])

  async function retry() {
    setState({ status: 'loading', analysis: null })
    try {
      const analysis = await findAnalysis(analysisId)
      setState(analysis ? { status: 'ready', analysis } : { status: 'missing', analysis: null })
    } catch (error) {
      if (error.status === 401) {
        clearAccessToken()
        setState({ status: 'unauthorized', analysis: null })
        return
      }
      setState({ status: 'error', analysis: null })
    }
  }

  if (state.status === 'loading') return <main className="app-page results-page" aria-live="polite"><p className="dashboard-state" role="status">Loading analysis results…</p></main>
  if (state.status === 'unauthorized') return <main className="app-page results-page"><AsyncState actions={<Link className="secondary-link" to="/login">Sign in</Link>} announcement="Your session has expired. Sign in to view results." kind="unauthorized" title="Your session has expired.">Sign in to view results.</AsyncState></main>
  if (state.status === 'missing') return <main className="app-page results-page"><AsyncState actions={<Link className="secondary-link" to="/history">Return to history</Link>} announcement="This analysis is not available." className="results-unavailable" kind="unavailable" title="Analysis is not available.">This analysis was not found in your recent owner-scoped history.</AsyncState></main>
  if (state.status === 'error') return <main className="app-page results-page"><AsyncState actions={<><Button onClick={retry} variant="secondary">Try again</Button><Link className="secondary-link" to="/history">Return to history</Link></>} announcement="Analysis results could not be loaded. Try again." className="results-unavailable" kind="error" title="Unable to load analysis results.">Try again, or return to your history.</AsyncState></main>

  const { analysis } = state
  const signals = analysis.signals ?? {}
  const trustScore = analysis.trust_score
  const explanation = analysis.explanation

  return (
    <main className="app-page results-page" aria-labelledby="results-title">
      <header className="results-header">
        <div>
          <p className="eyebrow">Saved analysis</p>
          <h1 id="results-title">Analysis results</h1>
          <p className="lede">Created {formatDate(analysis.created_at)}. This saved report shows only evidence returned by the server.</p>
        </div>
        <Link className="secondary-link" to="/history">Back to history</Link>
      </header>

      <div className="results-workspace">
        <div className="results-workspace__main">
          <section className="results-artifact-panel" aria-labelledby="artifact-panel-title">
            <div className="results-artifact-panel__heading"><Image aria-hidden="true" size={20} /><div><p className="eyebrow">Evidence workspace</p><h2 id="artifact-panel-title">Source artifacts</h2><p>TrustLens displays originals and visual artifacts only when the server returns them.</p></div></div>
            <div className="results-artifact-panel__slots">
              <SourceImageArtifact analysis={analysis} />
              <article className="results-artifact"><Activity aria-hidden="true" size={29} /><h3>ELA visualization unavailable</h3><p>The server returned ELA measurements, not a display artifact.</p></article>
            </div>
          </section>
          <ExplainableSummary explanation={explanation} />
        </div>
        <ResultModuleRail signals={signals} trustScore={trustScore} />
      </div>

      <section className="results-evidence" aria-labelledby="results-evidence-title">
        <div className="results-evidence__heading">
          <p className="eyebrow">Detailed evidence</p>
          <h2 id="results-evidence-title">Available technical signals</h2>
          <p>Each detail below reflects the saved server response. Availability is not a conclusion.</p>
        </div>
        <div className="results-signal-grid" aria-label="Available analysis signals">
          <TamperingResult explanation={explanation?.tampering} signal={signals.tampering} />
          <AIGenerationResult explanation={explanation?.ai_generated} signal={signals.ai_generation} />
          <OCRResult explanation={explanation?.ocr} signal={signals.ocr} />
          <QualityResult explanation={explanation?.image_quality} signal={signals.quality} />
          <ELAResult explanation={explanation?.ela} signal={signals.ela} />
        </div>
      </section>

      <Limitations explanation={explanation} trustScore={trustScore} />
    </main>
  )
}
