const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

export async function submitAnalysis(file, accessToken) {
  const formData = new FormData()
  formData.append('image', file)
  const response = await fetch(`${apiBaseUrl}/analyses`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
    body: formData,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const error = new Error(payload.detail ?? 'Unable to analyze this image.')
    error.status = response.status
    throw error
  }
  return response.json()
}

export async function fetchAnalysisHistory(accessToken, limit = 20, offset = 0) {
  const response = await fetch(`${apiBaseUrl}/analyses?limit=${limit}&offset=${offset}`, { headers: { Authorization: `Bearer ${accessToken}` } })
  if (!response.ok) {
    const error = new Error('Unable to load analysis history.')
    error.status = response.status
    throw error
  }
  return response.json()
}

export async function fetchSourceImage(id, accessToken) {
  const response = await fetch(`${apiBaseUrl}/analyses/${id}/source-image`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    const error = new Error('Unable to load the uploaded image.')
    error.status = response.status
    throw error
  }
  return response.blob()
}

export async function downloadReport(id, token) {
  const response = await fetch(`${apiBaseUrl}/analyses/${id}/report`, { headers: { Authorization: `Bearer ${token}` } })
  if (!response.ok) {
    const error = new Error('Unable to generate report.')
    error.status = response.status
    throw error
  }
  return response.blob()
}

export async function updateReportTitle(id, reportTitle, token) {
  const response = await fetch(`${apiBaseUrl}/analyses/${id}/report-title`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_title: reportTitle }),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const error = new Error(payload.detail ?? 'Unable to rename report.')
    error.status = response.status
    throw error
  }
  return response.json()
}
