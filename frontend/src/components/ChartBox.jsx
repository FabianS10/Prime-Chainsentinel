export default function ChartBox({ title, children }) {
  return <div className="panel p-4">
    {title && <div className="mb-3 text-[10px] uppercase tracking-[.18em] text-white/40">{title}</div>}
    {children}
  </div>
}
