import { FileImage, ShieldCheck, UploadCloud } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { submitAnalysis } from '../lib/api'
import { clearAccessToken, getAccessToken } from '../lib/auth'
import { Button } from '../components/ui/Button'
import { StatusIndicator } from '../components/ui/StatusIndicator'
import { AsyncState } from '../components/ui/AsyncState'

const maximumImageSize = 10 * 1024 * 1024

function statusVariant(status) {
  if (status === 'available') return 'success'
  if (status === 'unavailable') return 'unavailable'
  if (status === 'error' || status === 'failed') return 'error'
  return 'neutral'
}

function createPreviewUrl(file) {
  if (typeof URL.createObjectURL !== 'function') return null
  try {
    return URL.createObjectURL(file)
  } catch {
    return null
  }
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return 'Size unavailable'
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatFileType(type) {
  const subtype = typeof type === 'string' ? type.split('/')[1] : null
  return subtype ? subtype.toUpperCase() : 'Image type unavailable'
}

export function AnalyzeImagePage() {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [state, setState] = useState({ status: 'idle', message: '', result: null })

  useEffect(() => () => {
    if (previewUrl && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  function setSelectedFile(selectedFile) {
    if (!selectedFile) {
      setFile(null)
      setPreviewUrl(null)
      return
    }
    if (!selectedFile.type.startsWith('image/')) {
      setFile(null)
      setPreviewUrl(null)
      setState({ status: 'error', message: 'Choose a supported image file before starting analysis.', result: null })
      return
    }
    if (selectedFile.size > maximumImageSize) {
      setFile(null)
      setPreviewUrl(null)
      setState({ status: 'error', message: 'Choose an image smaller than 10 MB before starting analysis.', result: null })
      return
    }

    setFile(selectedFile)
    setPreviewUrl(createPreviewUrl(selectedFile))
    setState({ status: 'idle', message: '', result: null })
  }

  function selectFile(event) {
    setSelectedFile(event.target.files?.[0] ?? null)
  }

  function handleDrop(event) {
    event.preventDefault()
    setIsDragging(false)
    setSelectedFile(event.dataTransfer.files?.[0] ?? null)
  }

  function resetAnalysis() {
    setFile(null)
    setPreviewUrl(null)
    setState({ status: 'idle', message: '', result: null })
    if (inputRef.current) inputRef.current.value = ''
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (state.status === 'loading') return
    if (!file) {
      setState({ status: 'error', message: 'Choose an image before starting analysis.', result: null })
      return
    }
    setState({ status: 'loading', message: '', result: null })
    try {
      const result = await submitAnalysis(file, getAccessToken())
      setState({ status: 'success', message: '', result })
    } catch (error) {
      if (error.status === 401) {
        clearAccessToken()
        setState({ status: 'unauthorized', message: 'Your session has expired. Sign in to continue.', result: null })
        return
      }
      setState({ status: 'error', message: error.message, result: null })
    }
  }

  const signalEntries = Object.entries(state.result?.signals ?? {})

  return (
    <main className="app-page analyze-page" aria-labelledby="analyze-title">
      <header className="analyze-page__header">
        <p className="eyebrow">New analysis</p>
        <h1 id="analyze-title">Analyze an image</h1>
        <p className="lede">Choose an image you are authorized to review. TrustLens reports available signals and identifies services that could not run.</p>
      </header>

      <form aria-busy={state.status === 'loading'} className="analysis-form analysis-upload-card" onSubmit={handleSubmit}>
        <div className="analysis-upload-card__heading">
          <h2>Choose an image</h2>
          <p>Image files up to 10 MB are accepted. The server performs the final file and image validation.</p>
        </div>
        <div className="analysis-file-field">
          <input aria-describedby="image-file-help" aria-label="Image file" className="analysis-file-field__input" id="image-file" name="image" ref={inputRef} type="file" accept="image/*" onChange={selectFile} />
          <label className={`analysis-file-field__dropzone${isDragging ? ' is-dragging' : ''}`} htmlFor="image-file" onDragEnter={(event) => { event.preventDefault(); setIsDragging(true) }} onDragLeave={(event) => { event.preventDefault(); setIsDragging(false) }} onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
            <UploadCloud aria-hidden="true" size={26} />
            <span><strong>Drop an image here or browse</strong><small>PNG, JPEG, WebP, and other supported image types up to 10 MB.</small></span>
          </label>
          <p id="image-file-help"><ShieldCheck aria-hidden="true" size={15} />Final validation and analysis happen securely on the server.</p>
        </div>
        {file && (
          <aside className="analysis-selected-file analysis-file-summary" aria-label="Selected file">
            {previewUrl && <img alt="Selected image preview" className="analysis-selected-file__preview" src={previewUrl} />}
            <div>
              <strong><FileImage aria-hidden="true" size={17} />{file.name}</strong>
              <span>{formatFileSize(file.size)} · {formatFileType(file.type)}</span>
            </div>
            <Button onClick={resetAnalysis} type="button" variant="ghost">Remove</Button>
            <p className="analysis-file-summary__privacy"><ShieldCheck aria-hidden="true" size={16} />Your image is processed by the server only after you start an analysis.</p>
          </aside>
        )}
        {!file && <aside className="analysis-file-summary analysis-file-summary--empty" aria-label="Selected file"><p className="eyebrow">Selected file</p><div className="analysis-file-summary__empty"><FileImage aria-hidden="true" size={34} /><strong>No file selected</strong><span>A preview and file details will appear here.</span></div><p className="analysis-file-summary__privacy"><ShieldCheck aria-hidden="true" size={16} />Your image is processed by the server only after you start an analysis.</p></aside>}
        <Button className="analysis-submit" loading={state.status === 'loading'} type="submit">{state.status === 'loading' ? 'Analyzing image…' : 'Start analysis'}</Button>
      </form>

      <div className="analysis-state">
        {state.status === 'loading' && <AsyncState announcement="Analyzing the selected image." kind="loading" title="Analyzing image" />}
        {state.status === 'error' && <AsyncState className="error-message" kind="error" announcement={state.message}>{state.message}</AsyncState>}
        {state.status === 'unauthorized' && (
          <AsyncState actions={<Link className="secondary-link" to="/login">Sign in</Link>} className="error-message" kind="unauthorized" announcement={state.message}>
            {state.message}
          </AsyncState>
        )}
        {state.status === 'success' && (
          <AsyncState
            actions={<><Link className="primary-link" state={{ analysis: state.result }} to={`/results/${state.result.id}`}>View results</Link><Link className="secondary-link" to="/history">View history</Link><Button onClick={resetAnalysis} variant="ghost">Analyze another image</Button></>}
            announcement="Analysis submitted and saved."
            className="analysis-complete"
            kind="success"
            title="Analysis submitted"
          >
            <StatusIndicator status="success">Analysis saved</StatusIndicator>
            <p>Your analysis was saved. Signal availability is shown below; no conclusion is implied by this status list.</p>
            {signalEntries.length > 0 && (
              <ul className="analysis-signal-list">
                {signalEntries.map(([name, signal]) => (
                  <li key={name}>
                    <strong>{name}</strong>
                    <StatusIndicator status={statusVariant(signal.status)}>{signal.status}</StatusIndicator>
                  </li>
              ))}
            </ul>
            )}
          </AsyncState>
        )}
      </div>
    </main>
  )
}
