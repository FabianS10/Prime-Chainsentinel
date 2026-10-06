import { Activity, Blocks, Cpu, Database, Gauge, GitCompareArrows, Landmark, LineChart, Network, ScrollText, Shield, Sigma } from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'

const nav = [
  ['overview', 'Inicio', Activity],
  ['evidence', 'Evidencia', Database],
  ['hardware', 'Hardware', Cpu],
  ['gpu', 'Laboratorio GPU', Gauge],
  ['hash', 'Laboratorio Hash', Sigma],
  ['merkle', 'Merkle', Network],
  ['blockchain', 'Blockchain', Blocks],
  ['stocks', 'Mercado', LineChart],
  ['montecarlo', 'Monte Carlo', Landmark],
  ['modelcompare', 'Comparación', GitCompareArrows],
  ['reports', 'Reportes', ScrollText],
]

export default function Layout({ page, setPage, children }) {
  const { t } = useLanguage()
  return <div className="min-h-screen bg-prime-black text-[#e8e0d0] scanlines">
    <header className="sticky top-0 z-20 border-b border-prime-red/30 bg-prime-black/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1500px] items-center gap-4 px-4 py-3">
        <button onClick={() => setPage('overview')} className="flex items-center gap-3">
          <Shield className="text-prime-gold" size={28}/>
          <div className="font-display text-sm uppercase tracking-[.24em] text-prime-gold">Prime ChainSentinel</div>
        </button>
        <nav className="flex flex-1 flex-wrap gap-2">
          {nav.map(([id, label, Icon]) => <button key={id} onClick={() => setPage(id)} className={`flex items-center gap-1 rounded-lg border px-3 py-2 text-[10px] uppercase tracking-[.13em] transition ${page===id?'border-prime-gold bg-prime-gold/10 text-prime-gold':'border-transparent text-white/35 hover:border-white/10 hover:text-white/70'}`}><Icon size={13}/>{t(label)}</button>)}
        </nav>
      </div>
    </header>
    <main className="mx-auto max-w-[1500px] px-4 py-6">{children}</main>
    <footer className="border-t border-white/10 px-4 py-4 text-center text-[10px] uppercase tracking-[.14em] text-white/25">{t('Simulación educativa · Sin negociación en vivo · Sin minería real · Resultados sujetos a su procedencia y dominio de validez')}</footer>
  </div>
}
