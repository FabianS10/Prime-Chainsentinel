import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../api/client'
import SectionTitle from '../components/SectionTitle'
import ChartBox from '../components/ChartBox'
import Badge from '../components/Badge'
import EvidenceRequired from '../components/EvidenceRequired'
import SourceBanner from '../components/SourceBanner'

export default function HashLab({ setPage }) {
  const [data, setData] = useState(null)
  useEffect(()=>{ api.hash().then(setData).catch(()=>setData({available:false})) }, [])
  if (!data) return <div><SectionTitle title="Laboratorio de líneas base hash" subtitle="Cargando evidencia importada..."/></div>
  if (!data.available) return <div><SectionTitle title="Laboratorio de líneas base hash" subtitle="Mediciones criptográficas de CPU obtenidas durante la campaña."/><EvidenceRequired setPage={setPage} detail="Importa una campaña que contenga hash_benchmark.csv para habilitar las líneas base y las estimaciones que dependen de ellas."/></div>

  const algs = data.algorithms || {}
  const sha = algs.sha256 || []
  const rows = sha.map((r,i)=>({batch:r.batch, sha256:(r.peak||0)/1e6, sha3_256:(algs.sha3_256?.[i]?.peak||0)/1e6, blake3:(algs.blake3?.[i]?.peak||0)/1e6}))
  return <div>
    <SectionTitle title="Laboratorio de líneas base hash" subtitle="Tasa criptográfica real de CPU preservada desde la campaña importada."><Badge>MEDIDO</Badge></SectionTitle>
    <SourceBanner source={data.source}/>
    <ChartBox title="Tasa máxima por algoritmo">
      <ResponsiveContainer width="100%" height={360}><LineChart data={rows}><CartesianGrid stroke="#222"/><XAxis dataKey="batch" tick={{fill:'#777',fontSize:10}}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}}/><Line dataKey="sha256" name="SHA-256" stroke="#D4AF37" strokeWidth={2}/><Line dataKey="sha3_256" name="SHA3-256" stroke="#D72638" strokeWidth={2}/><Line dataKey="blake3" name="BLAKE3" stroke="#22C55E" strokeWidth={2}/></LineChart></ResponsiveContainer>
    </ChartBox>
  </div>
}
