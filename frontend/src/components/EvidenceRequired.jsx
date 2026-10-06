import { Database, UploadCloud } from 'lucide-react'

export default function EvidenceRequired({ setPage, title='No hay evidencia importada disponible', detail='Importa una campaña compatible para habilitar este módulo y conservar la procedencia de los resultados.' }){
  return <div className="panel max-w-3xl p-6">
    <div className="flex items-start gap-4">
      <div className="rounded-xl border border-prime-gold/25 bg-prime-gold/10 p-3 text-prime-gold"><Database size={22}/></div>
      <div className="flex-1">
        <h3 className="font-display text-lg uppercase tracking-[.12em] text-prime-gold">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-white/50">{detail}</p>
        <button className="btn mt-4 flex items-center gap-2" onClick={()=>setPage?.('evidence')}><UploadCloud size={14}/>Ir a Evidencia e importar</button>
      </div>
    </div>
  </div>
}
