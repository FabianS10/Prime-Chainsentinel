import { FileCheck2, Fingerprint } from 'lucide-react'

const short = (v='') => v && v.length > 26 ? `${v.slice(0,14)}…${v.slice(-8)}` : (v || '—')
const originText = value => ({
  IMPORTED:'IMPORTADO',
  MANIFEST_VERIFIED:'MANIFIESTO VERIFICADO',
  MANIFEST_PARTIAL:'MANIFIESTO PARCIAL',
  EXTERNAL_PROVIDER_RECORDED:'FUENTE EXTERNA REGISTRADA',
  INTERNAL_SYNTHETIC_GENERATOR:'GENERADOR SINTÉTICO INTERNO',
}[value] || value || '—')

export default function SourceBanner({ source, label='Fuente activa' }){
  if(!source) return null
  return <div className="glass mb-5 rounded-2xl border border-prime-gold/15 p-4 text-xs leading-6 text-white/45">
    <div className="mb-2 flex items-center gap-2 font-display uppercase tracking-[.15em] text-prime-gold"><FileCheck2 size={15}/>{label}</div>
    <div className="flex flex-wrap gap-x-5 gap-y-1">
      <span>Campaña: <strong className="text-white/70">{source.campaign || source.filename || '—'}</strong></span>
      {source.logical_path && <span>Artefacto: <strong className="text-white/70">{source.logical_path}</strong></span>}
      {source.import_id && <span>Importación: <span className="font-mono text-white/60">{short(source.import_id)}</span></span>}
      {source.sha256 && <span className="flex items-center gap-1"><Fingerprint size={12}/>SHA-256: <span className="font-mono text-white/60">{short(source.sha256)}</span></span>}
      {source.origin_status && <span>Origen: <strong className="text-white/70">{originText(source.origin_status)}</strong></span>}
    </div>
  </div>
}
