import { useEffect, useState } from 'react'
import { ArrowRight, Database, FileCheck2, FlaskConical, ScrollText } from 'lucide-react'
import { api } from '../api/client'
import MetricCard from '../components/MetricCard'
import SectionTitle from '../components/SectionTitle'
import SourceBanner from '../components/SourceBanner'

const fmt = n => {
  if (n === null || n === undefined) return '—'
  return n >= 1e9 ? `${(n/1e9).toFixed(2)}B` : n >= 1e6 ? `${(n/1e6).toFixed(1)}M` : n?.toLocaleString?.() || n
}

export default function Overview({ setPage }) {
  const [summary, setSummary] = useState(null)
  const [provenance, setProvenance] = useState(null)

  useEffect(() => {
    Promise.all([api.summary(), api.provenanceSummary()])
      .then(([s,p]) => { setSummary(s); setProvenance(p) })
      .catch(()=>{})
  }, [])

  const available = Boolean(summary?.available)
  return <div>
    <SectionTitle title="Prime ChainSentinel" subtitle="Procedencia, evidencia computacional y simulación con límites de interpretación explícitos." />

    {!available ? <div className="glass mb-6 rounded-2xl border-l-4 border-l-prime-gold p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="font-display uppercase tracking-[.16em] text-prime-gold">Comienza incorporando evidencia</div>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-white/55">Los módulos de hardware, GPU, hash, Merkle y simulación blockchain no muestran líneas base hasta que se importe una campaña compatible. Así, las métricas visibles siempre pueden rastrearse hasta un artefacto fuente.</p>
        </div>
        <button className="btn flex items-center gap-2" onClick={()=>setPage('evidence')}><Database size={15}/>Importar evidencia <ArrowRight size={14}/></button>
      </div>
    </div> : <SourceBanner source={summary.source} label="Campaña computacional activa" />}

    <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Importaciones" value={provenance?.imports ?? '—'} sub="Paquetes incorporados" />
      <MetricCard label="Artefactos" value={provenance?.artifacts ?? '—'} sub="Fuentes registradas" />
      <MetricCard label="Resultados" value={provenance?.results ?? '—'} sub="Medidos y derivados" />
      <MetricCard label="Derivaciones" value={provenance?.derivations ?? '—'} tone="green" sub="Relaciones de linaje" />
    </div>

    {available && <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Pico GPU sustituto" value={fmt(summary.gpu_synthetic_peak_run1)} unit="ops/s" sub="Obtenido de evidencia importada" />
      <MetricCard label="Diferencia entre ejecuciones" value={summary.gpu_repeatability_error_pct != null ? summary.gpu_repeatability_error_pct.toFixed(3) : '—'} unit="%" tone="green" sub="Solo cuando existen dos ejecuciones" />
      <MetricCard label="VRAM detectada" value={summary.hardware?.vram_gb ?? '—'} unit="GB" sub="Perfil de hardware importado" />
      <MetricCard label="Pico SHA-256 CPU" value={fmt(summary.best_hash_rates?.sha256)} unit="ops/s" tone="amber" sub="Línea base medida importada" />
    </div>}

    <div className="grid gap-4 lg:grid-cols-3">
      <div className="panel p-5 lg:col-span-2">
        <SectionTitle title="Flujo recomendado" subtitle="La evidencia entra al sistema antes de alimentar los laboratorios que dependen de campañas computacionales." />
        <div className="grid gap-3 md:grid-cols-4">
          {[
            [Database, '1', 'Importar evidencia', 'Incorpora la campaña y conserva sus archivos, hashes y metadatos.'],
            [FileCheck2, '2', 'Revisar procedencia', 'Comprueba clase, fuente, integridad y relaciones de derivación.'],
            [FlaskConical, '3', 'Ejecutar laboratorios', 'Usa únicamente líneas base importadas para los módulos blockchain.'],
            [ScrollText, '4', 'Exportar reporte', 'Genera un reporte con procedencia y límites de interpretación.'],
          ].map(([Icon,n,title,description]) => <div key={n} className="rounded-xl border border-white/10 bg-prime-panel2 p-4"><div className="flex items-center justify-between"><div className="font-display text-prime-gold">{n}</div><Icon size={16} className="text-white/25"/></div><div className="mt-2 text-sm text-white/80">{title}</div><p className="mt-2 text-xs leading-5 text-white/40">{description}</p></div>)}
        </div>
      </div>
      <div className="panel p-5">
        <SectionTitle title="Accesos rápidos" />
        <div className="flex flex-col gap-3">
          <button className="btn" onClick={()=>setPage('evidence')}>Evidencia y procedencia</button>
          <button className="btn" onClick={()=>setPage('gpu')}>Laboratorio GPU</button>
          <button className="btn" onClick={()=>setPage('blockchain')}>Simulación blockchain</button>
          <button className="btn" onClick={()=>setPage('stocks')}>Laboratorio de mercado</button>
          <button className="btn" onClick={()=>setPage('reports')}>Generar reporte</button>
        </div>
      </div>
    </div>
  </div>
}
