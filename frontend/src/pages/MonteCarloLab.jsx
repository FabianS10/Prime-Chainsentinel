import { useMemo, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from 'recharts'
import { api } from '../api/client'
import SectionTitle from '../components/SectionTitle'
import MetricCard from '../components/MetricCard'
import ChartBox from '../components/ChartBox'
import Badge from '../components/Badge'

const usd = n => '$' + Math.round(n||0).toLocaleString()
const fieldLabels = {
  initial_capital:'Capital inicial',
  monthly_contribution:'Aporte mensual',
  horizon_years:'Horizonte (años)',
  trials:'Trayectorias',
  target_value:'Valor objetivo',
}

export default function MonteCarloLab({ setPage, financialSession, setFinancialSession }){
  const market = financialSession?.market
  const previous = financialSession?.monteCarlo
  const [form,setForm]=useState(previous?.request ? {
    initial_capital: previous.request.initial_capital,
    monthly_contribution: previous.request.monthly_contribution,
    horizon_years: previous.request.horizon_years,
    trials: previous.request.trials,
    target_value: previous.request.target_value,
    use_student_t: previous.request.use_student_t,
  } : {initial_capital:1000,monthly_contribution:300,horizon_years:20,trials:5000,target_value:250000,use_student_t:false})
  const [out,setOut]=useState(previous?.result || null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')

  const assets = market?.assets || []
  const marketYears = market?.years

  async function run(){
    if(!market){
      setError('Primero realiza una consulta en el Laboratorio de mercado.')
      return
    }
    setLoading(true); setError('')
    try{
      const request = {
        ...form,
        market_years: marketYears,
        market_dataset_ids: market.dataset_ids || [],
        seed:1337,
        assets,
      }
      const result = await api.monteCarlo(request)
      setOut(result)
      setFinancialSession?.(prev=>({ ...prev, monteCarlo:{request,result}, comparison:null }))
    }
    catch(err){ setError(err.message || 'No fue posible ejecutar la simulación.') }
    finally{ setLoading(false) }
  }

  const cone = out ? out.percentiles.p50.map((_,i)=>({month:i,p10:out.percentiles.p10[i],p25:out.percentiles.p25[i],p50:out.percentiles.p50[i],p75:out.percentiles.p75[i],p90:out.percentiles.p90[i]})) : []
  const hist = out ? Object.entries(out.final_value_distribution).filter(([k])=>k.startsWith('p')).map(([k,v])=>({percentile:k,value:v})) : []

  if(!market){
    return <div>
      <SectionTitle title="Simulación Monte Carlo" subtitle="Generación de escenarios probabilísticos a partir de una consulta de mercado registrada."><Badge type="sim">SIMULADO</Badge></SectionTitle>
      <div className="panel p-6">
        <div className="text-lg font-display uppercase tracking-[.12em] text-prime-gold">Falta la fuente de mercado</div>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-white/50">Monte Carlo no utiliza una cartera ni un periodo escritos directamente en el código. Primero consulta los activos y el periodo histórico en el Laboratorio de mercado.</p>
        <button className="btn mt-4" onClick={()=>setPage?.('stocks')}>Ir al Laboratorio de mercado</button>
      </div>
    </div>
  }

  return <div>
    <SectionTitle title="Simulación Monte Carlo" subtitle="Generación de escenarios probabilísticos a partir de la consulta financiera activa.">
      <div className="flex items-center gap-2"><Badge type="sim">SIMULADO</Badge>{out&&<button className="btn" onClick={() => setPage?.('modelcompare')}>Continuar a comparación</button>}</div>
    </SectionTitle>

    <div className="glass mb-5 rounded-2xl p-4 text-xs leading-6 text-white/45">
      <div className="font-display uppercase tracking-[.14em] text-prime-gold">Fuente financiera activa</div>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
        <span>Activos: {assets.map(a=>a.ticker).join(', ')}</span>
        <span>Periodo: {marketYears} años</span>
        <span>Proveedor: {market.provider}</span>
      </div>
      <div className="mt-1">Resultados fuente: {(market.dataset_ids || []).join(', ') || '—'}</div>
    </div>

    <div className="panel mb-5 p-5">
      <div className="grid gap-4 md:grid-cols-5">
        {Object.entries(form).filter(([k])=>k!=='use_student_t').map(([k,v])=><label key={k} className="text-xs uppercase tracking-[.15em] text-white/40">{fieldLabels[k] || k}<input className="input mt-2 w-full" type="number" value={v||0} onChange={e=>setForm({...form,[k]:Number(e.target.value)})}/></label>)}
        <label className="flex items-end gap-2 text-xs uppercase tracking-[.15em] text-white/40"><input type="checkbox" checked={form.use_student_t} onChange={e=>setForm({...form,use_student_t:e.target.checked})}/>Usar colas pesadas (Student-t)</label>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-4">{assets.map((asset,idx)=><div key={`${asset.ticker}-${idx}`} className="rounded-xl border border-white/10 bg-prime-panel2 p-3"><div className="text-prime-gold">{asset.ticker}</div><div className="mt-2 text-xs uppercase tracking-[.15em] text-white/40">Peso</div><div className="mt-1 text-sm text-white/70">{(asset.weight*100).toFixed(1)}%</div></div>)}</div>
      <div className="mt-3 text-xs leading-6 text-white/35">La semilla pseudoaleatoria se fija internamente y se conserva únicamente como metadato técnico de reproducibilidad.</div>
      <button className="btn mt-4" onClick={run}>{loading?'Ejecutando...':'Ejecutar Monte Carlo'}</button>
      {error&&<div className="mt-4 rounded-lg border border-prime-brightRed/30 bg-prime-brightRed/10 p-3 text-sm text-prime-brightRed">{error}</div>}
    </div>

    {out&&<>
      <div className="mb-5 grid gap-4 md:grid-cols-4">
        <MetricCard label="Mediana terminal" value={usd(out.final_value_distribution.median)}/>
        <MetricCard label="Percentil 10" value={usd(out.final_value_distribution.p10)} tone="red"/>
        <MetricCard label="Percentil 90" value={usd(out.final_value_distribution.p90)} tone="green"/>
        <MetricCard label="Puntuación de riesgo" value={out.risk.risk_score.toFixed(1)} unit="/100" tone={out.risk.risk_score>60?'red':'amber'} sub={out.risk.risk_label || '—'}/>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartBox title="Cono de incertidumbre"><ResponsiveContainer width="100%" height={350}><AreaChart data={cone}><CartesianGrid stroke="#222"/><XAxis dataKey="month" name="Mes" tick={{fill:'#777',fontSize:10}}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}}/><Area dataKey="p90" stroke="#D4AF37" fill="#D4AF3720"/><Area dataKey="p75" stroke="#F3D77A" fill="#F3D77A20"/><Area dataKey="p50" stroke="#22C55E" fill="#22C55E10"/><Area dataKey="p25" stroke="#D72638" fill="#D7263810"/><Area dataKey="p10" stroke="#8B0000" fill="#8B000015"/></AreaChart></ResponsiveContainer></ChartBox>
        <ChartBox title="Distribución de percentiles del valor terminal"><ResponsiveContainer width="100%" height={350}><BarChart data={hist}><CartesianGrid stroke="#222"/><XAxis dataKey="percentile" tick={{fill:'#777',fontSize:10}}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}}/><Bar dataKey="value" name="Valor terminal" fill="#D4AF37"/></BarChart></ResponsiveContainer></ChartBox>
      </div>
      <div className="mt-5 rounded-xl border border-prime-amber/30 bg-prime-amber/5 p-4 text-xs leading-6 text-white/45">Resultado registrado como <span className="text-purple-300">SIMULADO</span> y derivado de las series de mercado de la consulta activa. No representa una predicción garantizada ni una recomendación de inversión.</div>
    </>}
  </div>
}
