import { useEffect, useState } from 'react'
import { CheckCircle2, Fingerprint, GitBranch, RefreshCw, ShieldCheck, UploadCloud, XCircle } from 'lucide-react'
import { api } from '../api/client'
import Badge from '../components/Badge'
import MetricCard from '../components/MetricCard'
import SectionTitle from '../components/SectionTitle'

const shortId = (value='') => value.length > 42 ? `${value.slice(0,28)}…${value.slice(-10)}` : value
const badgeType = cls => cls === 'MEASURED' ? 'measured' : cls === 'SURROGATE' ? 'surrogate' : 'sim'
const statusText = value => ({COMPLETED:'COMPLETADA',COMPLETED_WITH_ERRORS:'COMPLETADA CON ADVERTENCIAS',FAILED:'FALLIDA',VALID:'VÁLIDO',INVALID:'INVÁLIDO'}[value] || value)
const evidenceText = value => ({
  MEASURED:'MEDIDO',
  SURROGATE:'SUSTITUTO',
  ESTIMATED:'ESTIMADO',
  CORRECTED:'CORREGIDO',
  SIMULATED:'SIMULADO',
  EXPERIMENTAL:'EXPERIMENTAL',
}[value] || value)

const resultTypeText = value => ({
  hardware_profile:'Perfil de hardware',
  gpu_synthetic_baseline:'Línea base GPU sustituta',
  gpu_surrogate_baseline:'Línea base GPU sustituta',
  hash_baseline:'Línea base de hash',
  merkle_measured:'Medición de árbol de Merkle',
  pow_measured:'Medición de prueba de trabajo',
  hash_workload_estimate:'Estimación de carga hash',
  merkle_estimate:'Estimación de árbol de Merkle',
  merkle_corrected:'Estimación corregida de árbol de Merkle',
  pow_simulation:'Simulación de prueba de trabajo',
  market_series:'Serie histórica de mercado',
  market_metrics:'Métricas históricas de mercado',
  synthetic_market_generator:'Generador sintético de mercado',
  portfolio_simulation:'Simulación de cartera',
  model_comparison:'Comparación temporal de modelos',
}[value] || String(value || '—').replaceAll('_',' '))

const originText = value => ({
  IMPORTED:'IMPORTADO',
  MANIFEST_VERIFIED:'MANIFIESTO VERIFICADO',
  MANIFEST_PARTIAL:'MANIFIESTO PARCIAL',
  EXTERNAL_PROVIDER_RECORDED:'FUENTE EXTERNA REGISTRADA',
  INTERNAL_SYNTHETIC_GENERATOR:'GENERADOR SINTÉTICO INTERNO',
}[value] || value || '—')

const integrityText = value => ({
  INTEGRITY_VERIFIED:'INTEGRIDAD VERIFICADA',
  INTEGRITY_MISMATCH:'DIFERENCIA DE INTEGRIDAD',
  DIGEST_RECORDED:'DIGEST REGISTRADO',
  LOCAL_COPY_MISSING:'COPIA LOCAL NO DISPONIBLE',
}[value] || value || '—')

const transformationText = value => ({
  'Monte Carlo portfolio simulation':'Simulación Monte Carlo de cartera',
  'rolling-origin model comparison':'Comparación de modelos con origen móvil',
  'external market acquisition':'Adquisición externa de mercado',
  'deterministic synthetic market fallback':'Serie sintética determinista de respaldo',
  'prices_to_returns_and_metrics':'Cálculo de retornos y métricas',
  'operations_divided_by_measured_hash_rate':'Operaciones divididas por la tasa hash medida',
  'Merkle structural estimate':'Estimación estructural de Merkle',
  'Merkle structural estimate plus measured residual overhead':'Estimación estructural de Merkle con sobrecosto residual medido',
  'offline PoW probability model':'Modelo probabilístico de prueba de trabajo fuera de línea',
  'Merkle naive N-1 model':'Modelo Merkle ingenuo N-1',
  'Merkle structural 2N-1 correction':'Corrección estructural Merkle 2N-1',
}[value] || value || '—')

export default function EvidenceLab({ setPage }){
  const [file,setFile]=useState(null)
  const [campaign,setCampaign]=useState('')
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')
  const [lastImport,setLastImport]=useState(null)
  const [imports,setImports]=useState([])
  const [summary,setSummary]=useState(null)
  const [results,setResults]=useState([])
  const [selected,setSelected]=useState(null)
  const [integrity,setIntegrity]=useState(null)

  async function refresh(){
    const [i,s,r] = await Promise.all([api.listImports(12), api.provenanceSummary(), api.provenanceResults(60)])
    setImports(i.items || [])
    setSummary(s)
    setResults(r.items || [])
  }
  useEffect(()=>{ refresh().catch(()=>{}) },[])

  async function upload(){
    if(!file) return
    setLoading(true); setError(''); setIntegrity(null)
    try{
      const out = await api.uploadEvidence(file,campaign)
      setLastImport(out)
      await refresh()
    }catch(err){ setError(err.message || 'Falló la importación') }
    finally{ setLoading(false) }
  }

  async function inspect(resultId){
    setError(''); setIntegrity(null)
    try{ setSelected(await api.provenanceResult(resultId)) }
    catch(err){ setError(err.message) }
  }

  async function verify(){
    const artifactId = selected?.source_artifact?.artifact_id
    if(!artifactId) return
    try{ setIntegrity(await api.verifyArtifact(artifactId)) }
    catch(err){ setError(err.message) }
  }

  return <div>
    <SectionTitle title="Evidencia y procedencia" subtitle="Importa artefactos, verifica su integridad, revisa su clase de evidencia y sigue sus relaciones de derivación.">
      <Badge type="measured">SHA-256 + linaje</Badge>
    </SectionTitle>

    <div className="mb-5 grid gap-4 md:grid-cols-4">
      <MetricCard label="Importaciones" value={summary?.imports ?? '—'} />
      <MetricCard label="Artefactos" value={summary?.artifacts ?? '—'} />
      <MetricCard label="Resultados" value={summary?.results ?? '—'} />
      <MetricCard label="Derivaciones" value={summary?.derivations ?? '—'} tone="green" />
    </div>

    <div className="grid gap-5 xl:grid-cols-[1.05fr_.95fr]">
      <div className="space-y-5">
        <div className="panel p-5">
          <div className="mb-2 flex items-center gap-2 font-display uppercase tracking-[.16em] text-prime-gold"><UploadCloud size={18}/>Importar evidencia</div>
          <p className="mb-4 text-xs leading-6 text-white/40">Para habilitar Hardware, GPU, Hash, Merkle y Blockchain, incorpora una campaña que contenga los artefactos de pruebas correspondientes. La importación más reciente se utiliza como campaña activa.</p>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-xs uppercase tracking-[.14em] text-white/40">Nombre o descripción de campaña
              <input className="input mt-2 w-full" value={campaign} onChange={e=>setCampaign(e.target.value)} placeholder="Ej. MI300X ejecución completa"/>
            </label>
            <label className="text-xs uppercase tracking-[.14em] text-white/40">Archivo ZIP, JSON, CSV o TXT
              <input className="mt-2 block w-full text-xs text-white/60 file:mr-3 file:rounded-lg file:border-0 file:bg-prime-gold/15 file:px-3 file:py-2 file:text-prime-gold" type="file" accept=".zip,.json,.csv,.txt" onChange={e=>setFile(e.target.files?.[0] || null)}/>
            </label>
          </div>
          <button className="btn mt-4 flex items-center gap-2" disabled={!file || loading} onClick={upload}>{loading?<RefreshCw className="animate-spin" size={14}/>:<ShieldCheck size={14}/>} {loading?'Importando...':'Validar e importar'}</button>
          {error && <div className="mt-4 rounded-lg border border-prime-brightRed/30 bg-prime-brightRed/10 p-3 text-sm text-prime-brightRed">{error}</div>}
          {lastImport && <div className="mt-4 rounded-xl border border-prime-green/30 bg-prime-green/5 p-4 text-xs leading-6 text-white/55">
            <div className="flex items-center gap-2 text-prime-green"><CheckCircle2 size={15}/><strong>{statusText(lastImport.status)}</strong></div>
            <div>ID de importación: <span className="font-mono text-white/70">{lastImport.import_id}</span></div>
            <div>SHA-256: <span className="font-mono text-white/70">{shortId(lastImport.sha256)}</span></div>
            <div>Estado de origen: <span className="text-prime-gold">{originText(lastImport.origin_status)}</span></div>
            <div>Resultados registrados: {lastImport.result_ids?.length || 0}</div>
            <p className="mt-2 text-white/35">Un hash coincidente comprueba que los bytes almacenados no cambiaron desde la incorporación. No demuestra por sí solo la autenticidad del productor externo ni la veracidad del contenido.</p>
            <div className="mt-3 flex flex-wrap gap-2"><button className="btn-red" onClick={()=>setPage?.('hardware')}>Ver hardware</button><button className="btn-red" onClick={()=>setPage?.('gpu')}>Ver GPU</button><button className="btn-red" onClick={()=>setPage?.('blockchain')}>Ir a Blockchain</button></div>
          </div>}
        </div>

        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between"><div className="font-display uppercase tracking-[.16em] text-prime-gold">Importaciones recientes</div><button className="btn-red flex items-center gap-2" onClick={()=>refresh()}><RefreshCw size={13}/>Actualizar</button></div>
          <div className="space-y-2">{imports.length ? imports.map((item,idx)=><div key={item.import_id} className="rounded-xl border border-white/10 bg-prime-panel2 p-3 text-xs text-white/50">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-mono text-white/70">{item.filename}</span><div className="flex items-center gap-2">{idx===0&&<Badge type="measured">ACTIVA</Badge>}<Badge type={item.status==='COMPLETED'?'measured':'surrogate'}>{statusText(item.status)}</Badge></div></div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1"><span>{item.campaign || 'Sin descripción'}</span><span>{originText(item.origin_status)}</span><span>{Math.round(item.size_bytes/1024)} KB</span></div>
          </div>):<div className="text-sm text-white/35">Aún no hay importaciones.</div>}</div>
        </div>
      </div>

      <div className="space-y-5">
        <div className="panel p-5">
          <div className="mb-4 font-display uppercase tracking-[.16em] text-prime-gold">Resultados recientes</div>
          <div className="max-h-[430px] space-y-2 overflow-auto pr-1">{results.length?results.map(row=><button key={row.result_id} onClick={()=>inspect(row.result_id)} className="w-full rounded-xl border border-white/10 bg-prime-panel2 p-3 text-left hover:border-prime-gold/35">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-mono text-[11px] text-white/65">{shortId(row.result_id)}</span><Badge type={badgeType(row.evidence_class)}>{evidenceText(row.evidence_class)}</Badge></div>
            <div className="mt-2 text-[11px] uppercase tracking-[.12em] text-white/30">{resultTypeText(row.result_type)}</div>
          </button>):<div className="text-sm text-white/35">Importa evidencia o ejecuta un laboratorio para registrar resultados.</div>}</div>
        </div>

        <div className="panel p-5">
          <div className="mb-4 flex items-center gap-2 font-display uppercase tracking-[.16em] text-prime-gold"><Fingerprint size={17}/>Detalle de procedencia</div>
          {!selected ? <p className="text-sm text-white/40">Selecciona un resultado para inspeccionar su procedencia.</p> : <div className="space-y-4 text-xs leading-6 text-white/55">
            <div><span className="text-white/30">ID del resultado</span><div className="break-all font-mono text-white/75">{selected.result_id}</div></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><span className="text-white/30">Clase de evidencia</span><div><Badge type={badgeType(selected.evidence_class)}>{evidenceText(selected.evidence_class)}</Badge></div></div>
              <div><span className="text-white/30">Tipo de resultado</span><div className="text-prime-gold">{resultTypeText(selected.result_type)}</div></div>
            </div>
            <div><span className="text-white/30">Contrato</span><div className="flex items-center gap-2">{selected.contract?.valid?<CheckCircle2 className="text-prime-green" size={15}/>:<XCircle className="text-prime-brightRed" size={15}/>} {selected.contract?.valid?'Válido':'Inválido'}</div></div>
            <div><span className="text-white/30">Derivado de</span>{selected.derived_from?.length?<div className="mt-1 space-y-1">{selected.derived_from.map(p=><button key={p.parent_result_id} onClick={()=>inspect(p.parent_result_id)} className="flex w-full items-center gap-2 rounded border border-white/10 px-2 py-1 text-left font-mono text-[10px] hover:border-prime-gold/30"><GitBranch size={12}/>{shortId(p.parent_result_id)} · {transformationText(p.transformation)}</button>)}</div>:<div>—</div>}</div>
            <div><span className="text-white/30">Artefacto fuente</span><div className="break-all font-mono text-[10px] text-white/65">{selected.source_artifact?.artifact_id || '—'}</div></div>
            {selected.source_artifact && <button className="btn-red flex items-center gap-2" onClick={verify}><Fingerprint size={13}/>Verificar integridad</button>}
            {integrity && <div className="rounded-lg border border-white/10 bg-black/20 p-3"><div className="text-prime-gold">Integridad: {integrityText(integrity.status)}</div><div className="mt-1 break-all font-mono text-[10px]">esperado: {integrity.sha256_expected}</div>{integrity.sha256_actual&&<div className="break-all font-mono text-[10px]">actual: {integrity.sha256_actual}</div>}</div>}
            <details><summary className="cursor-pointer text-prime-gold">Campos técnicos de procedencia</summary><pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-black/30 p-3 text-[10px] text-white/45">{JSON.stringify(selected,null,2)}</pre></details>
          </div>}
        </div>
      </div>
    </div>
  </div>
}
