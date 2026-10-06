import { useState } from 'react'
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

export default function App(){
  return <LanguageProvider><AppBody/></LanguageProvider>
}
