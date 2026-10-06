export default function MetricCard({ label, value, unit, sub, tone = 'gold' }) {
  const cls = tone === 'red' ? 'metric-red' : tone === 'green' ? 'metric-green' : tone === 'amber' ? 'metric-amber' : 'metric'
  const val = tone === 'red' ? 'text-prime-brightRed' : tone === 'green' ? 'text-prime-green' : tone === 'amber' ? 'text-prime-amber' : 'text-prime-gold'
  return <div className={cls}>
    <div className="label">{label}</div>
    <div className={`font-display text-2xl font-bold ${val}`}>{value}<span className="ml-1 font-mono text-xs text-white/50">{unit}</span></div>
    {sub && <div className="mt-1 text-xs text-white/35">{sub}</div>}
  </div>
}
