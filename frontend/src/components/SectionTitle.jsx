export default function SectionTitle({ title, subtitle, children }) {
  return <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
    <div>
      <div className="flex items-center gap-3"><div className="h-5 w-1 bg-prime-red"/><h2 className="font-display text-lg uppercase tracking-[.18em] text-prime-gold">{title}</h2></div>
      {subtitle && <p className="ml-4 mt-2 text-xs tracking-wide text-white/40">{subtitle}</p>}
    </div>
    {children}
  </div>
}
