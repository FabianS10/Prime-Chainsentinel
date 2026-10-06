import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, Legend } from 'recharts'
import { api } from '../api/client'
import SectionTitle from '../components/SectionTitle'
import MetricCard from '../components/MetricCard'
import ChartBox from '../components/ChartBox'
import Badge from '../components/Badge'

const COLORS = ['#D4AF37','#7C3AED','#D72638','#1D9BF0','#22C55E','#F97316']
const pct = x => `${((x || 0)*100).toFixed(2)}%`
const evidenceText = value => ({MEASURED:'MEDIDO',SIMULATED:'SIMULADO',MIXED:'MIXTO',ESTIMATED:'ESTIMADO'}[value] || value || '—')
const providerText = value => ({yahoo:'Yahoo Finance',offline:'Sintético local',mixed:'Mixto'}[value] || value || '—')

function normalizeBasket(tickers, current){
  const currentMap = Object.fromEntries((current || []).map(a => [a.ticker.toUpperCase(), Number(a.weight) || 0]))
  const knownTotal = tickers.reduce((sum, t) => sum + (currentMap[t] || 0), 0)
  const raw = tickers.map(t => ({ ticker:t, weight: currentMap[t] || (knownTotal > 0 ? 0 : 1 / tickers.length), expected_return:null, volatility:null }))
  const total = raw.reduce((sum,a) => sum + a.weight, 0)
  return raw.map(a => ({ ...a, weight: total > 0 ? a.weight / total : 1 / Math.max(raw.length, 1) }))
}

export default function StockMarketLab({ setPage, portfolioAssets = [], setPortfolioAssets, financialSession, setFinancialSession }){
  const previous = financialSession?.market
  const [tickers,setTickers]=useState(previous?.tickers?.join(',') || portfolioAssets.map(a=>a.ticker).join(','))
  const [years,setYears]=useState(previous?.years || 7)
  const [metrics,setMetrics]=useState(previous?.metrics || [])
  const [comparisonHistory,setComparisonHistory]=useState(previous?.chartHistory || [])
  const [providerMeta,setProviderMeta]=useState(previous?.providerMeta || null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')

  const tickerList = useMemo(() => tickers.split(',').map(t=>t.trim().toUpperCase()).filter(Boolean), [tickers])
  const basket = useMemo(() => normalizeBasket(tickerList, portfolioAssets), [tickerList, portfolioAssets])

  async function fetchAll(forceRefresh=true){
    setLoading(true)
    setError('')
    try{
      if (!tickerList.length) throw new Error('Ingresa al menos un símbolo antes de consultar el mercado.')
      const activeAssets = normalizeBasket(tickerList, portfolioAssets)
      const p=await api.portfolioMetrics(tickerList,years,forceRefresh)
      const payloads = await Promise.all(tickerList.map(t => api.marketHistory(t, years, false)))
      const byDate = new Map()
      payloads.forEach((payload) => {
        const first = payload.history?.[0]?.adjusted_close || 1
        payload.history?.forEach((row) => {
          const item = byDate.get(row.date) || { date: row.date }
          item[payload.ticker] = (row.adjusted_close / first) * 100
          byDate.set(row.date, item)
        })
      })
      const chartHistory = Array.from(byDate.values()).sort((a,b)=>a.date.localeCompare(b.date))
      const datasetIds = (p.metrics || []).map(m=>m.dataset_id).filter(Boolean)
      const marketState = {
        tickers: tickerList,
        assets: activeAssets,
        years,
        metrics: p.metrics || [],
        provider: p.provider,
        providers: p.providers || [],
        providerMeta: p,
        price_series_label: p.price_series_label,
        metric_label: p.metric_label,
        warnings: p.warnings || [],
        dataset_ids: datasetIds,
        chartHistory,
      }
      setMetrics(p.metrics || [])
      setProviderMeta(p)
      setComparisonHistory(chartHistory)
      setPortfolioAssets?.(activeAssets)
      // Una nueva consulta invalida cualquier simulación/comparación anterior.
      setFinancialSession?.({ market: marketState, monteCarlo:null, comparison:null })
    } catch (err) {
      setError(err.message || 'No fue posible recuperar los datos de mercado.')
    } finally { setLoading(false) }
  }

  function updateWeight(ticker, weight){
    const list = basket.map(a => a.ticker === ticker ? { ...a, weight: Number(weight) || 0 } : a)
    const total = list.reduce((sum,a)=>sum+a.weight,0)
    const normalized = list.map(a=>({...a,weight: total>0 ? a.weight/total : 1/list.length}))
    setPortfolioAssets?.(normalized)
    if(financialSession?.market){
      setFinancialSession?.(prev=>({
        ...prev,
        market:{...prev.market,assets:normalized},
        monteCarlo:null,
        comparison:null,
      }))
    }
  }

  function changeTickers(value){
    setTickers(value)
    setMetrics([])
    setProviderMeta(null)
    setComparisonHistory([])
    setFinancialSession?.({market:null,monteCarlo:null,comparison:null})
  }

  function changeYears(value){
    setYears(value)
    setMetrics([])
    setProviderMeta(null)
    setComparisonHistory([])
    setFinancialSession?.({market:null,monteCarlo:null,comparison:null})
  }

  const marketReady = Boolean(financialSession?.market?.dataset_ids?.length)

  return <div>
    <SectionTitle title="Laboratorio de mercado" subtitle="Primero consulta las series históricas y define la cartera. Esta consulta alimenta Monte Carlo, la comparación de modelos y el reporte.">
      <Badge type={providerMeta?.provider === 'yahoo' ? 'measured' : 'sim'}>{providerMeta?.provider === 'yahoo' ? 'Yahoo Finance' : marketReady ? 'Fuente registrada' : 'Sin consulta'}</Badge>
    </SectionTitle>

    <div className="panel mb-5 p-5">
      <div className="grid gap-4 md:grid-cols-4">
        <label className="md:col-span-2 text-xs uppercase tracking-[.16em] text-white/40">Símbolos
          <input className="input mt-2 w-full" value={tickers} onChange={e=>changeTickers(e.target.value)} placeholder="Ej. VTI, QQQ, PLTR, LMT"/>
        </label>
        <label className="text-xs uppercase tracking-[.16em] text-white/40">Años de historia
          <input className="input mt-2 w-full" type="number" min="2" max="30" value={years} onChange={e=>changeYears(Number(e.target.value))}/>
        </label>
        <button className="btn self-end" onClick={()=>fetchAll(true)}>{loading?'Consultando...':'Consultar mercado'}</button>
      </div>

      {tickerList.length>0 && <div className="mt-5 grid gap-3 md:grid-cols-4">
        {basket.map((asset) => <label key={asset.ticker} className="rounded-xl border border-white/10 bg-prime-panel2 p-3 text-xs uppercase tracking-[.14em] text-white/40">{asset.ticker} · peso
          <input className="input mt-2 w-full" type="number" min="0" max="1" step="0.01" value={asset.weight.toFixed(2)} onChange={e=>updateWeight(asset.ticker,e.target.value)}/>
        </label>)}
      </div>}

      {marketReady && <div className="mt-4 flex flex-wrap gap-3">
        <button className="btn" onClick={()=>setPage?.('montecarlo')}>Continuar a Monte Carlo</button>
        <span className="self-center text-xs text-white/40">La comparación de modelos se habilita después de ejecutar Monte Carlo con esta misma consulta.</span>
      </div>}
      {error && <div className="mt-4 rounded-lg border border-prime-brightRed/30 bg-prime-brightRed/10 px-4 py-3 text-sm text-prime-brightRed">{error}</div>}
    </div>

    {!marketReady && <div className="mb-5 rounded-xl border border-prime-amber/30 bg-prime-amber/5 p-4 text-sm leading-6 text-white/50">
      No hay una consulta financiera activa. Monte Carlo, comparación de modelos y las secciones financieras del reporte permanecen vacías hasta consultar el mercado.
    </div>}

    {providerMeta && <div className="glass mb-5 rounded-2xl p-4 text-xs leading-6 text-white/45">
      <div className="flex flex-wrap items-center gap-2">
        <Badge type={providerMeta.provider === 'yahoo' ? 'measured' : 'surrogate'}>{evidenceText(providerMeta.price_series_label) || 'SIN CLASIFICAR'} · serie de precios</Badge>
        <Badge type="sim">MÉTRICAS ESTIMADAS</Badge>
        <span>Proveedor: <span className="text-prime-gold">{providerText(providerMeta.provider)}</span></span>
        <span>· Periodo solicitado: {years} años</span>
      </div>
      {(providerMeta.warnings || []).length > 0 && <div className="mt-2 text-prime-amber">{providerMeta.warnings.join(' ')}</div>}
      <div className="mt-2">Las series consultadas quedan registradas como la fuente del flujo financiero activo. Los laboratorios siguientes utilizan esta misma cartera y periodo.</div>
    </div>}

    {metrics.length>0&&<>
      <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">{metrics.map(m=><MetricCard key={m.ticker} label={m.ticker} value={pct(m.cagr)} unit="CAGR" sub={`${pct(m.annualized_volatility)} volatilidad · ${pct(m.max_drawdown)} caída máx. · ${providerText(m.provider)}`} tone={m.cagr<0?'red':m.annualized_volatility>.35?'amber':'green'}/>)}</div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartBox title="Comparación de cierre ajustado (base = 100)">
          <ResponsiveContainer width="100%" height={340}><LineChart data={comparisonHistory}><CartesianGrid stroke="#222"/><XAxis dataKey="date" hide/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}}/><Legend wrapperStyle={{fontSize:'11px'}}/>{metrics.map((m,i)=><Line key={m.ticker} dataKey={m.ticker} stroke={COLORS[i%COLORS.length]} dot={false} connectNulls strokeWidth={2}/>)}</LineChart></ResponsiveContainer>
        </ChartBox>
        <ChartBox title="Volatilidad y caída máxima absoluta">
          <ResponsiveContainer width="100%" height={340}><BarChart data={metrics.map(m=>({...m,abs_drawdown:Math.abs(m.max_drawdown)}))}><CartesianGrid stroke="#222"/><XAxis dataKey="ticker" tick={{fill:'#777',fontSize:10}}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}} formatter={(v)=>pct(v)}/><Legend wrapperStyle={{fontSize:'11px'}}/><Bar dataKey="annualized_volatility" name="Volatilidad anualizada" fill="#D4AF37"/><Bar dataKey="abs_drawdown" name="Caída máxima absoluta" fill="#D72638"/></BarChart></ResponsiveContainer>
        </ChartBox>
      </div>
    </>}
    <div className="mt-5 rounded-xl border border-prime-amber/30 bg-prime-amber/5 p-4 text-xs leading-6 text-white/45">Regla de evidencia: las observaciones históricas provenientes de la fuente externa se conservan como evidencia observada; CAGR, volatilidad, caída máxima y correlaciones se presentan como <span className="text-purple-300">ESTIMADO</span>. Las trayectorias futuras producidas por modelos se clasifican como <span className="text-purple-300">SIMULADO</span>.</div>
  </div>
}
