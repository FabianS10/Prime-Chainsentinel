import { useState } from 'react'
import SectionTitle from '../components/SectionTitle'
import Badge from '../components/Badge'
import ReportButton from '../components/ReportButton'

export default function Reports({ financialSession }){
  const market = financialSession?.market
  const monteCarlo = financialSession?.monteCarlo
  const comparison = financialSession?.comparison
  const [notes,setNotes]=useState('Reporte generado desde Prime ChainSentinel. Los resultados deben interpretarse junto con su clase de evidencia, fuente y dominio de validez.')

  const marketSnapshot = market ? {
    assets: market.assets,
    years: market.years,
    metrics: market.metrics,
    provider: market.provider,
    providers: market.providers,
    price_series_label: market.price_series_label,
    metric_label: market.metric_label,
    warnings: market.warnings,
    dataset_ids: market.dataset_ids,
  } : null

  const payload={
    title:'Prime ChainSentinel — Reporte de evidencia y procedencia',
    include_blockchain:true,
    market_snapshot:marketSnapshot,
    monte_carlo_result_id:monteCarlo?.result?.result_id || null,
    model_comparison_result_id:comparison?.result?.result_id || null,
    notes,
  }

  return <div>
    <SectionTitle title="Generación de reportes" subtitle="Exporta únicamente la evidencia y los resultados que ya fueron obtenidos. Generar el PDF no ejecuta nuevas simulaciones ni consultas de mercado.">
      <Badge type="measured">PDF + procedencia</Badge>
    </SectionTitle>

    <div className="grid gap-4 lg:grid-cols-3 mb-5">
      <div className={`panel p-4 ${market?'border-prime-green/25':''}`}>
        <div className="text-xs uppercase tracking-[.14em] text-white/35">Mercado</div>
        <div className="mt-2 font-display text-lg text-prime-gold">{market?'EJECUTADO':'NO EJECUTADO'}</div>
        <div className="mt-2 text-xs leading-5 text-white/40">{market ? `${market.tickers.join(', ')} · ${market.years} años · ${market.provider}` : 'No se incluirán métricas financieras de mercado.'}</div>
      </div>
      <div className={`panel p-4 ${monteCarlo?'border-prime-green/25':''}`}>
        <div className="text-xs uppercase tracking-[.14em] text-white/35">Monte Carlo</div>
        <div className="mt-2 font-display text-lg text-prime-gold">{monteCarlo?'EJECUTADO':'NO EJECUTADO'}</div>
        <div className="mt-2 break-all text-xs leading-5 text-white/40">{monteCarlo?.result?.result_id || 'El reporte no generará una simulación automáticamente.'}</div>
      </div>
      <div className={`panel p-4 ${comparison?'border-prime-green/25':''}`}>
        <div className="text-xs uppercase tracking-[.14em] text-white/35">Comparación de modelos</div>
        <div className="mt-2 font-display text-lg text-prime-gold">{comparison?'EJECUTADA':'NO EJECUTADA'}</div>
        <div className="mt-2 break-all text-xs leading-5 text-white/40">{comparison?.result?.result_id || 'El reporte no ejecutará la comparación automáticamente.'}</div>
      </div>
    </div>

    <div className="panel p-5">
      <p className="mb-4 text-sm leading-7 text-white/50">El documento conserva el estado real de la sesión. Si una etapa financiera no fue ejecutada, aparecerá como <strong className="text-white/70">NO EJECUTADA</strong> en lugar de calcularse silenciosamente durante la exportación.</p>
      <label className="text-xs uppercase tracking-[.16em] text-white/40">Notas del reporte<textarea className="input mt-2 h-32 w-full" value={notes} onChange={e=>setNotes(e.target.value)}/></label>
      <div className="mt-4"><ReportButton payload={payload} label="Generar reporte PDF"/></div>
    </div>
  </div>
}
