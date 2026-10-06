import { useMemo, useState } from 'react'
import { ResponsiveContainer, CartesianGrid, Tooltip, XAxis, YAxis, BarChart, Bar, LineChart, Line, Legend } from 'recharts'
import { api } from '../api/client'
import SectionTitle from '../components/SectionTitle'
import MetricCard from '../components/MetricCard'
import ChartBox from '../components/ChartBox'
import Badge from '../components/Badge'

const fmtUsd = (x) => '$' + Math.round(x || 0).toLocaleString()

export default function ModelComparisonLab({ setPage, financialSession, setFinancialSession }){
  const market = financialSession?.market
  const monteCarlo = financialSession?.monteCarlo
  const previous = financialSession?.comparison
  const [form, setForm] = useState(previous?.request ? {
    rolling_window_months: previous.request.rolling_window_months,
    forecast_horizon_months: previous.request.forecast_horizon_months,
    trials: previous.request.trials,
  } : {
    rolling_window_months: 36,
    forecast_horizon_months: 12,
    trials: 3000,
  })
  const [out, setOut] = useState(previous?.result || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const summary = useMemo(() => (out?.summary || []).map((row) => ({
    model: row.model,
    coverage_error_pct: (row.coverage_error_90 || 0) * 100,
    average_interval_width_pct: (row.average_interval_width_pct || 0) * 100,
    quantile_loss: row.quantile_loss || 0,
    cvar_95_pct: (row.cvar_95_pct || 0) * 100,
  })), [out])

  const latestProjection = useMemo(() => out?.latest_projection || [], [out])
  const regime = useMemo(() => (out?.regime_coverage || []).map((row) => ({
    model: row.model,
    bull: (row.bull || 0) * 100,
    bear: (row.bear || 0) * 100,
    volatile: (row.volatile || 0) * 100,
    sideways: (row.sideways || 0) * 100,
  })), [out])

  async function run(){
    if(!market || !monteCarlo){
      setError('Primero consulta el mercado y ejecuta Monte Carlo para fijar el escenario financiero.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const request = {
        assets: market.assets,
        market_dataset_ids: market.dataset_ids || [],
        initial_capital: monteCarlo.request.initial_capital,
        monthly_contribution: monteCarlo.request.monthly_contribution,
        years: market.years,
        rolling_window_months: form.rolling_window_months,
        forecast_horizon_months: form.forecast_horizon_months,
        trials: form.trials,
        seed: 1337,
      }
      const result = await api.modelComparison(request)
      setOut(result)
      setFinancialSession?.(prev=>({ ...prev, comparison:{request,result} }))
    } catch (err) {
      setError(err.message || 'No fue posible comparar los modelos.')
    } finally {
      setLoading(false)
    }
  }

  if(!market || !monteCarlo){
    return <div>
      <SectionTitle title="Comparación temporal de modelos" subtitle="Comparación de motores sobre la misma cartera, periodo histórico y escenario utilizado por Monte Carlo."><Badge type="sim">EXPERIMENTAL</Badge></SectionTitle>
      <div className="panel p-6">
        <div className="text-lg font-display uppercase tracking-[.12em] text-prime-gold">Flujo financiero incompleto</div>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-white/50">La comparación no parte de valores predeterminados. Primero consulta las series en Mercado y luego ejecuta Monte Carlo para fijar la cartera y el escenario.</p>
        <div className="mt-4 flex gap-3">
          <button className="btn" onClick={()=>setPage?.('stocks')}>Ir a Mercado</button>
          {market&&<button className="btn" onClick={()=>setPage?.('montecarlo')}>Ir a Monte Carlo</button>}
        </div>
      </div>
    </div>
  }

  return <div>
    <SectionTitle title="Comparación temporal de modelos" subtitle="Diagnósticos sobre la misma evidencia histórica y el mismo escenario financiero utilizado en Monte Carlo.">
      <Badge type="sim">EXPERIMENTAL</Badge>
    </SectionTitle>

    <div className="glass mb-5 rounded-2xl p-4 text-xs leading-6 text-white/45">
      <div className="font-display uppercase tracking-[.14em] text-prime-gold">Contexto financiero heredado</div>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
        <span>Activos: {market.assets.map(a=>a.ticker).join(', ')}</span>
        <span>Historia: {market.years} años</span>
        <span>Capital inicial: {fmtUsd(monteCarlo.request.initial_capital)}</span>
        <span>Aporte mensual: {fmtUsd(monteCarlo.request.monthly_contribution)}</span>
      </div>
      <div className="mt-1">La semilla se conserva internamente como metadato de reproducibilidad y no se presenta como variable de análisis.</div>
    </div>

    <div className="panel mb-5 p-5">
      <div className="mb-4 grid gap-4 md:grid-cols-3">
        <label className="text-xs uppercase tracking-[.15em] text-white/40">Ventana de entrenamiento (meses)
          <input className="input mt-2 w-full" type="number" min="12" value={form.rolling_window_months} onChange={e => setForm({ ...form, rolling_window_months:Number(e.target.value) })}/>
        </label>
        <label className="text-xs uppercase tracking-[.15em] text-white/40">Horizonte de evaluación (meses)
          <input className="input mt-2 w-full" type="number" min="3" value={form.forecast_horizon_months} onChange={e => setForm({ ...form, forecast_horizon_months:Number(e.target.value) })}/>
        </label>
        <label className="text-xs uppercase tracking-[.15em] text-white/40">Trayectorias por evaluación
          <input className="input mt-2 w-full" type="number" min="500" value={form.trials} onChange={e => setForm({ ...form, trials:Number(e.target.value) })}/>
        </label>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button className="btn" onClick={run}>{loading ? 'Ejecutando...' : 'Ejecutar comparación'}</button>
        <div className="text-xs leading-6 text-white/40">Si la ventana y el horizonte requieren más observaciones de las disponibles, el sistema mostrará el motivo y no generará un resultado incompleto.</div>
      </div>
      {error && <div className="mt-4 rounded-lg border border-prime-brightRed/30 bg-prime-brightRed/10 px-4 py-3 text-sm text-prime-brightRed">{error}</div>}
    </div>

    {out && <>
      <div className="mb-5 grid gap-4 md:grid-cols-4">
        <MetricCard label="Ventanas evaluadas" value={out.evaluation_windows || 0} sub="orígenes temporales"/>
        <MetricCard label="Modelos comparados" value={(out.summary || []).length} tone="green"/>
        <MetricCard label="Ventana de entrenamiento" value={out.rolling_window_months || form.rolling_window_months} unit="meses" tone="amber"/>
        <MetricCard label="Horizonte de evaluación" value={out.forecast_horizon_months || form.forecast_horizon_months} unit="meses"/>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartBox title="Error de cobertura del intervalo del 90 % por modelo"><ResponsiveContainer width="100%" height={320}><BarChart data={summary}><CartesianGrid stroke="#222"/><XAxis dataKey="model" tick={{fill:'#777',fontSize:10}} angle={-8} textAnchor="end" height={60}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}} formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Error de cobertura']}/><Bar dataKey="coverage_error_pct" fill="#D72638"/></BarChart></ResponsiveContainer></ChartBox>
        <ChartBox title="Ancho medio del intervalo (% del valor terminal mediano)"><ResponsiveContainer width="100%" height={320}><BarChart data={summary}><CartesianGrid stroke="#222"/><XAxis dataKey="model" tick={{fill:'#777',fontSize:10}} angle={-8} textAnchor="end" height={60}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}} formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Ancho medio']}/><Bar dataKey="average_interval_width_pct" fill="#D4AF37"/></BarChart></ResponsiveContainer></ChartBox>
        <ChartBox title="Pérdida cuantílica por modelo"><ResponsiveContainer width="100%" height={320}><BarChart data={summary}><CartesianGrid stroke="#222"/><XAxis dataKey="model" tick={{fill:'#777',fontSize:10}} angle={-8} textAnchor="end" height={60}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}} formatter={(v) => [fmtUsd(v), 'Pérdida cuantílica']}/><Bar dataKey="quantile_loss" fill="#22C55E"/></BarChart></ResponsiveContainer></ChartBox>
        <ChartBox title="CVaR (presión media de la cola de pérdidas al 95 %)"><ResponsiveContainer width="100%" height={320}><BarChart data={summary}><CartesianGrid stroke="#222"/><XAxis dataKey="model" tick={{fill:'#777',fontSize:10}} angle={-8} textAnchor="end" height={60}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}} formatter={(v) => [`${Number(v).toFixed(2)}%`, 'CVaR']}/><Bar dataKey="cvar_95_pct" fill="#8B0000"/></BarChart></ResponsiveContainer></ChartBox>
        <ChartBox title="Cobertura por régimen de mercado"><ResponsiveContainer width="100%" height={360}><BarChart data={regime}><CartesianGrid stroke="#222"/><XAxis dataKey="model" tick={{fill:'#777',fontSize:10}} angle={-8} textAnchor="end" height={60}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}} formatter={(v) => [`${Number(v).toFixed(1)}%`, 'Cobertura']}/><Legend wrapperStyle={{fontSize:'11px'}}/><Bar dataKey="bull" name="Alcista" fill="#22C55E"/><Bar dataKey="bear" name="Bajista" fill="#D72638"/><Bar dataKey="volatile" name="Alta volatilidad" fill="#D4AF37"/><Bar dataKey="sideways" name="Lateral" fill="#7C3AED"/></BarChart></ResponsiveContainer></ChartBox>
        <ChartBox title="Última proyección: percentiles P10, P50 y P90"><ResponsiveContainer width="100%" height={360}><LineChart data={latestProjection}><CartesianGrid stroke="#222"/><XAxis dataKey="model" tick={{fill:'#777',fontSize:10}} angle={-8} textAnchor="end" height={60}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}} formatter={(v) => [fmtUsd(v), 'Valor terminal']}/><Legend wrapperStyle={{fontSize:'11px'}}/><Line type="monotone" dataKey="p10" stroke="#D72638" strokeWidth={2}/><Line type="monotone" dataKey="p50" stroke="#22C55E" strokeWidth={2}/><Line type="monotone" dataKey="p90" stroke="#D4AF37" strokeWidth={2}/></LineChart></ResponsiveContainer></ChartBox>
      </div>

      <div className="mt-5 rounded-xl border border-prime-amber/30 bg-prime-amber/5 p-4 text-xs leading-6 text-white/45">La comparación presenta diagnósticos complementarios de varios motores. No selecciona un ganador universal ni constituye una recomendación de inversión.</div>
    </>}
  </div>
}
