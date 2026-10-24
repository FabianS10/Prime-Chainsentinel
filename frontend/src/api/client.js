const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  summary: () => request('/api/baselines/summary'),
  hardware: () => request('/api/baselines/hardware'),
  gpu: () => request('/api/baselines/gpu-synthetic'),
  hash: () => request('/api/baselines/hash'),
  merkleBaselines: () => request('/api/baselines/merkle'),
  powBaselines: () => request('/api/baselines/pow'),
  marketMetrics: (ticker, years = 5, refresh = false) => request(`/api/market/metrics/${ticker}?years=${years}&refresh=${refresh}`),
  marketHistory: (ticker, years = 5, refresh = false) => request(`/api/market/history/${ticker}?years=${years}&refresh=${refresh}`),
  portfolioMetrics: (tickers, years = 5, refresh = false) => request(`/api/market/portfolio-metrics?tickers=${encodeURIComponent(tickers.join(','))}&years=${years}&refresh=${refresh}`),
  hashWorkload: (payload) => request('/api/blockchain/hash-workload', { method: 'POST', body: JSON.stringify(payload) }),
  merkle: (payload) => request('/api/blockchain/merkle', { method: 'POST', body: JSON.stringify(payload) }),
  pow: (payload) => request('/api/blockchain/pow', { method: 'POST', body: JSON.stringify(payload) }),
  monteCarlo: (payload) => request('/api/portfolio/monte-carlo', { method: 'POST', body: JSON.stringify(payload) }),
  modelComparison: (payload) => request('/api/portfolio/model-comparison', { method: 'POST', body: JSON.stringify(payload) }),
  listImports: (limit = 20) => request(`/api/imports?limit=${limit}`),
  provenanceSummary: () => request('/api/provenance/summary'),
  provenanceResults: (limit = 50) => request(`/api/provenance/results?limit=${limit}`),
  provenanceResult: (resultId) => request(`/api/provenance/results/${encodeURIComponent(resultId)}`),
  verifyArtifact: (artifactId) => request(`/api/provenance/artifacts/${encodeURIComponent(artifactId)}/verify`),
  uploadEvidence: async (file, campaign = '') => {
    const form = new FormData()
    form.append('file', file)
    if (campaign) form.append('campaign', campaign)
    const res = await fetch(`${API_BASE}/api/imports`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },
  generateReport: async (payload) => {
    const res = await fetch(`${API_BASE}/api/reports/generate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.blob()
  }
}
