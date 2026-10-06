import { useEffect, useState } from 'react'
import { api } from '../api/client'
import SectionTitle from '../components/SectionTitle'
import MetricCard from '../components/MetricCard'
import Badge from '../components/Badge'
import EvidenceRequired from '../components/EvidenceRequired'
import SourceBanner from '../components/SourceBanner'

const fmt = n => n >= 1e9 ? `${(n/1e9).toFixed(2)}B` : n >= 1e6 ? `${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `${(n/1e3).toFixed(1)}K` : Number(n).toFixed(3)
const labels = {
  algorithm: 'Algoritmo', transactions: 'Transacciones', hashes_per_transaction: 'Hashes por transacción', conservative_band_pct: 'Banda conservadora (%)',
  transaction_count: 'Cantidad de transacciones', model: 'Modelo', difficulty_bits: 'Bits de dificultad', seconds: 'Ventana (s)'
}

export default function BlockchainLab({ setPage }) {
  const [tab, setTab] = useState('merkle')
  const [summary, setSummary] = useState(null)
  useEffect(()=>{ api.summary().then(setSummary).catch(()=>setSummary({available:false})) },[])
  if (!summary) return <div><SectionTitle title="Laboratorio blockchain" subtitle="Verificando líneas base importadas..."/></div>
  if (!summary.available) return <div><SectionTitle title="Laboratorio blockchain" subtitle="Estimaciones y simulaciones fuera de línea derivadas de evidencia importada."/><EvidenceRequired setPage={setPage} detail="Importa una campaña compatible. Hash, Merkle y PoW ya no se ejecutan con líneas base embebidas cuando no existe evidencia incorporada."/></div>

  return <div>
    <SectionTitle title="Laboratorio blockchain" subtitle="Estimaciones y simulaciones fuera de línea con procedencia explícita."><Badge type="red">SOLO FUERA DE LÍNEA</Badge></SectionTitle>
    <SourceBanner source={summary.source} label="Campaña usada por los modelos"/>
    <div className="mb-4 flex flex-wrap gap-2">{[['hash','Hash'],['merkle','Merkle'],['pow','PoW']].map(([id,label])=><button className={tab===id?'btn':'btn-red'} key={id} onClick={()=>setTab(id)}>{label}</button>)}</div>
    {tab==='hash' && <HashSim setPage={setPage}/>}{tab==='merkle' && <MerkleSim setPage={setPage}/>}{tab==='pow' && <PowSim setPage={setPage}/>} 
  </div>
}

function ProvenanceResult({ out, setPage }){
  if(!out) return null
  return <div className="mt-4 rounded-xl border border-prime-gold/20 bg-black/20 p-4 text-xs leading-6 text-white/50">
    <div>Clase: <span className="text-prime-gold">{out.evidence_class}</span></div>
    <div>Resultado: <span className="font-mono text-white/65">{out.result_id}</span></div>
    <div>Derivado de: <span className="font-mono text-white/65">{(out.derived_from || []).join(', ') || '—'}</span></div>
    <button className="btn-red mt-3" onClick={()=>setPage?.('evidence')}>Ver procedencia</button>
  </div>
}

function HashSim({setPage}){
  const [form,setForm]=useState({algorithm:'sha256',transactions:1000000,hashes_per_transaction:1,conservative_band_pct:15})
  const [out,setOut]=useState(null)
  const [error,setError]=useState('')
  async function run(){ try{ setError(''); setOut(await api.hashWorkload(form)) }catch(e){setError(e.message)} }
  return <SimShell form={form} setForm={setForm} fields={[['algorithm','select'],['transactions','number'],['hashes_per_transaction','number'],['conservative_band_pct','number']]} run={run} error={error}>{out&&<><div className="grid gap-4 md:grid-cols-3"><MetricCard label="Tiempo estimado" value={fmt(out.estimated_seconds)} unit="s"/><MetricCard label="Operaciones" value={fmt(out.total_operations)}/><MetricCard label="Línea base" value={fmt(out.baseline_ops_sec)} unit="ops/s"/></div><ProvenanceResult out={out} setPage={setPage}/></>}</SimShell>
}
function MerkleSim({setPage}){
  const [form,setForm]=useState({algorithm:'sha256',transaction_count:100000,model:'overhead_adjusted'})
  const [out,setOut]=useState(null)
  const [error,setError]=useState('')
  async function run(){ try{ setError(''); setOut(await api.merkle(form)) }catch(e){setError(e.message)} }
  return <SimShell form={form} setForm={setForm} fields={[['algorithm','select'],['transaction_count','number'],['model','selectModel']]} run={run} error={error}>{out&&<><div className="grid gap-4 md:grid-cols-4"><MetricCard label="Tiempo seleccionado" value={out.selected_estimated_ms.toFixed(2)} unit="ms"/><MetricCard label="Profundidad" value={out.tree_depth}/><MetricCard label="Operaciones hash" value={fmt(out.total_hash_operations)}/><MetricCard label="Factor de sobrecosto" value={out.residual_overhead_factor.toFixed(2)} unit="×" tone="amber"/></div><ProvenanceResult out={out} setPage={setPage}/></>}</SimShell>
}
function PowSim({setPage}){
  const [form,setForm]=useState({difficulty_bits:20,seconds:1})
  const [out,setOut]=useState(null)
  const [error,setError]=useState('')
  async function run(){ try{ setError(''); setOut(await api.pow(form)) }catch(e){setError(e.message)} }
  return <SimShell form={form} setForm={setForm} fields={[['difficulty_bits','number'],['seconds','number']]} run={run} error={error}>{out&&<><div className="grid gap-4 md:grid-cols-3"><MetricCard label="Tiempo esperado" value={fmt(out.expected_seconds)} unit="s"/><MetricCard label="Intentos esperados" value={fmt(out.expected_trials)}/><MetricCard label="P(éxito)" value={(out.probability_success_by_window*100).toFixed(5)} unit="%" tone="green"/></div><ProvenanceResult out={out} setPage={setPage}/></>}</SimShell>
}
function SimShell({form,setForm,fields,run,children,error}){
  return <div className="panel p-5"><div className="grid gap-4 md:grid-cols-3">{fields.map(([k,type])=><label key={k} className="flex flex-col gap-2 text-xs uppercase tracking-[.16em] text-white/40">{labels[k] || k}{type==='select'?<select className="input" value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})}><option value="sha256">SHA-256</option><option value="sha3_256">SHA3-256</option><option value="blake3">BLAKE3</option></select>:type==='selectModel'?<select className="input" value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})}><option value="naive">Ingenuo</option><option value="corrected">Corregido</option><option value="overhead_adjusted">Ajustado por sobrecosto</option></select>:<input className="input" type="number" value={form[k]} onChange={e=>setForm({...form,[k]:Number(e.target.value)})}/>}</label>)}</div><button className="btn mt-4" onClick={run}>Ejecutar</button>{error&&<div className="mt-4 rounded-lg border border-prime-brightRed/30 bg-prime-brightRed/10 p-3 text-sm text-prime-brightRed">{error}</div>}<div className="mt-5">{children}</div></div>
}
