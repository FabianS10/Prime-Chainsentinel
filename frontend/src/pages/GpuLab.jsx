import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from 'recharts'
import { api } from '../api/client'
import SectionTitle from '../components/SectionTitle'
import MetricCard from '../components/MetricCard'
import Badge from '../components/Badge'
import ChartBox from '../components/ChartBox'
import EvidenceRequired from '../components/EvidenceRequired'
import SourceBanner from '../components/SourceBanner'

const peak = rows => Math.max(...(rows || []).map(r=>Number(r.peak)||0), 0)
const fmtM = n => n ? `${(n/1e6).toFixed(1)}M` : '—'

export default function GpuLab({ setPage }) {
  const [data, setData] = useState(null)
  useEffect(()=>{ api.gpu().then(setData).catch(()=>setData({available:false})) }, [])
  if (!data) return <div><SectionTitle title="Laboratorio GPU" subtitle="Cargando evidencia importada..."/></div>
  if (!data.available) return <div><SectionTitle title="Laboratorio GPU" subtitle="Carga paralela de bytes clasificada como SUSTITUTO."/><EvidenceRequired setPage={setPage} detail="Importa una campaña que contenga gpu_synthetic_benchmark.csv. Las métricas GPU ya no se muestran desde constantes internas."/></div>

  const run1 = data.run1 || []
  const run2 = data.run2 || []
  const p1 = peak(run1)
  const p2 = peak(run2)
  const repeat = p1 && p2 ? Math.abs(p1-p2)/((p1+p2)/2)*100 : null
  const merged = run1.map((r,i)=>({ batch:r.batch, media:(r.mean||0)/1e6, pico:(r.peak||0)/1e6, pico2:(run2[i]?.peak||0)/1e6, memoria:r.mem_mb }))

  return <div>
    <SectionTitle title="Laboratorio GPU" subtitle="Carga sustituta paralela de bytes. No corresponde a hashing criptográfico nativo en GPU."><Badge type="surrogate">SUSTITUTO</Badge></SectionTitle>
    <SourceBanner source={data.source} label="Importación activa"/>
    <div className="mb-5 grid gap-4 md:grid-cols-3">
      <MetricCard label="Pico ejecución 1" value={fmtM(p1)} unit="ops/s"/>
      <MetricCard label="Pico ejecución 2" value={p2 ? fmtM(p2) : '—'} unit="ops/s"/>
      <MetricCard label="Diferencia entre ejecuciones" value={repeat != null ? repeat.toFixed(3) : '—'} unit="%" tone="green"/>
    </div>
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartBox title="Tamaño de lote frente a tasa de procesamiento">
        <ResponsiveContainer width="100%" height={300}><LineChart data={merged}><CartesianGrid stroke="#222"/><XAxis dataKey="batch" tick={{fill:'#777',fontSize:10}}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}}/><Line type="monotone" dataKey="pico" name="Pico ejecución 1" stroke="#D4AF37" strokeWidth={2}/>{run2.length>0&&<Line type="monotone" dataKey="pico2" name="Pico ejecución 2" stroke="#D72638" strokeWidth={2}/>}</LineChart></ResponsiveContainer>
      </ChartBox>
      <ChartBox title="Memoria utilizada por tamaño de lote">
        <ResponsiveContainer width="100%" height={300}><BarChart data={merged}><CartesianGrid stroke="#222"/><XAxis dataKey="batch" tick={{fill:'#777',fontSize:10}}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}}/><Bar dataKey="memoria" name="Memoria (MB)" fill="#8B0000"/></BarChart></ResponsiveContainer>
      </ChartBox>
    </div>
    <div className="mt-5 rounded-xl border border-prime-amber/30 bg-prime-amber/5 p-4 text-xs leading-6 text-white/45">Los valores de esta vista provienen exclusivamente de artefactos importados. La carga se conserva como evidencia <span className="text-prime-gold">SUSTITUTO</span> y no debe interpretarse como rendimiento nativo de SHA-256, SHA3-256 o BLAKE3 en GPU.</div>
  </div>
}
