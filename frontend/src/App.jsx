import { useEffect, useState } from 'react'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Hardware from './pages/Hardware'
import GpuLab from './pages/GpuLab'
import HashLab from './pages/HashLab'
import MerkleLab from './pages/MerkleLab'
import BlockchainLab from './pages/BlockchainLab'
import StockMarketLab from './pages/StockMarketLab'
import MonteCarloLab from './pages/MonteCarloLab'
import ModelComparisonLab from './pages/ModelComparisonLab'
import Reports from './pages/Reports'
import EvidenceLab from './pages/EvidenceLab'
import { LanguageProvider } from './i18n/LanguageContext'
import { api, setDemoCredentials } from './api/client'

const pages = { overview: Overview, evidence: EvidenceLab, hardware: Hardware, gpu: GpuLab, hash: HashLab, merkle: MerkleLab, blockchain: BlockchainLab, stocks: StockMarketLab, montecarlo: MonteCarloLab, modelcompare: ModelComparisonLab, reports: Reports }

function AppBody(){
  const [page,setPage]=useState('overview')
  const [portfolioAssets,setPortfolioAssets]=useState([])
  const [financialSession,setFinancialSession]=useState({ market:null, monteCarlo:null, comparison:null })
  const Page = pages[page] || Overview
  return <Layout page={page} setPage={setPage}>
    <Page
      setPage={setPage}
      portfolioAssets={portfolioAssets}
      setPortfolioAssets={setPortfolioAssets}
      financialSession={financialSession}
      setFinancialSession={setFinancialSession}
    />
  </Layout>
}

function AppGate() {
  const [status, setStatus] = useState('checking')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function verifySession() {
    setStatus('checking')
    try {
      await api.summary()
      setStatus('ready')
      setError('')
    } catch (err) {
      setStatus(String(err.message).startsWith('401 ') ? 'login' : 'offline')
      setError(err.message)
    }
  }

  useEffect(() => { verifySession() }, [])

  async function submitLogin(event) {
    event.preventDefault()
    setDemoCredentials(username, password)
    setStatus('checking')
    try {
      await api.summary()
      setStatus('ready')
      setPassword('')
      setError('')
    } catch (err) {
      setDemoCredentials('', '')
      setStatus(String(err.message).startsWith('401 ') ? 'login' : 'offline')
      setError(String(err.message).startsWith('401 ') ? 'Credenciales incorrectas.' : err.message)
    }
  }

  if (status === 'ready') return <AppBody />

  return (
    <div className="min-h-screen bg-prime-black text-[#e8e0d0] flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border border-white/15 bg-black/50 p-8 space-y-5">
        <h1 className="text-xl font-semibold tracking-wide text-prime-gold">Prime ChainSentinel</h1>
        {status === 'checking' ? <p>Conectando con el servidor...</p> :
          status === 'offline' ? (
            <div className="space-y-4">
              <p>El backend no responde. Compruebe la dirección de API y su disponibilidad.</p>
              <p className="text-sm text-red-300 break-words">{error}</p>
              <button className="rounded bg-prime-gold px-4 py-2 text-black" onClick={verifySession}>Reintentar</button>
            </div>
          ) : (
            <form onSubmit={submitLogin} className="space-y-4">
              <p className="text-sm text-white/70">Ingrese las credenciales de la demostración para continuar.</p>
              <label className="block text-sm">Usuario
                <input className="mt-1 w-full rounded border border-white/20 bg-black/60 p-2" type="text" autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} />
              </label>
              <label className="block text-sm">Contraseña
                <input className="mt-1 w-full rounded border border-white/20 bg-black/60 p-2" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} />
              </label>
              {error && <p className="text-sm text-red-300">{error}</p>}
              <button className="rounded bg-prime-gold px-4 py-2 text-black" type="submit">Ingresar</button>
            </form>
          )}
      </div>
    </div>
  )
}

export default function App(){
  return <LanguageProvider><AppGate/></LanguageProvider>
}
