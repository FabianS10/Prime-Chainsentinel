export default function Badge({ children, type = 'measured' }) {
  const cls = type === 'sim' ? 'badge badge-sim' : type === 'surrogate' ? 'badge badge-surr' : type === 'red' ? 'badge badge-red' : 'badge badge-measured'
  return <span className={cls}>{children}</span>
}
