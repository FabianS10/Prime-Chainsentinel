import { useEffect, useState } from 'react'
import { api } from '../api/client'
import SectionTitle from '../components/SectionTitle'
import MetricCard from '../components/MetricCard'
import EvidenceRequired from '../components/EvidenceRequired'
import SourceBanner from '../components/SourceBanner'

export default function Hardware({ setPage }) {
  const [data, setData] = useState(null)
  useEffect(()=>{ api.hardware().then(setData).catch(()=>setData({available:false})) }, [])
  if (!data) return <div><SectionTitle title="Perfil de hardware" subtitle="Cargando evidencia del entorno..."/></div>
  if (!data.available) return <div><SectionTitle title="Perfil de hardware" subtitle="El perfil se obtiene de la campaña incorporada al sistema."/><EvidenceRequired setPage={setPage} detail="Importa una campaña que contenga hardware_profile.json para consultar aquí el entorno en el que se generó la evidencia."/></div>

  const hw = data.hardware || {}
  const rows = [
    ['CPU', hw.cpu], ['Núcleos CPU', hw.cores], ['RAM', hw.ram_gb != null ? `${hw.ram_gb} GB` : null], ['GPU', hw.gpu],
    ['VRAM', hw.vram_gb != null ? `${hw.vram_gb} GB` : null], ['Backend', hw.backend], ['Dispositivos GPU', hw.devices],
    ['ROCm', hw.rocm], ['PyTorch', hw.pytorch], ['HIP', hw.hip], ['Commit', hw.git_commit], ['Capturado', hw.collected_at]
  ]
  return <div>
    <SectionTitle title="Perfil de hardware" subtitle="Metadatos preservados desde el archivo hardware_profile.json de la campaña activa." />
    <SourceBanner source={data.source}/>
    <div className="mb-6 grid gap-4 md:grid-cols-4">
      <MetricCard label="GPU" value={hw.gpu || '—'} sub={hw.backend || '—'} />
      <MetricCard label="VRAM" value={hw.vram_gb ?? '—'} unit="GB" />
      <MetricCard label="Núcleos CPU" value={hw.cores ?? '—'} />
      <MetricCard label="GPU disponible en campaña" value={hw.gpu_available ? 'SÍ' : 'NO'} tone={hw.gpu_available ? 'green' : 'red'} />
    </div>
    <div className="panel overflow-hidden p-5">
      <table className="w-full text-sm"><tbody>{rows.map(([k,v]) => <tr key={k} className="border-b border-white/5"><td className="py-3 text-white/35">{k}</td><td className="py-3 text-right text-prime-gold">{v || '—'}</td></tr>)}</tbody></table>
    </div>
  </div>
}
