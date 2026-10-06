import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from 'recharts'
import { api } from '../api/client'
import SectionTitle from '../components/SectionTitle'
import ChartBox from '../components/ChartBox'
import Badge from '../components/Badge'
import EvidenceRequired from '../components/EvidenceRequired'
import SourceBanner from '../components/SourceBanner'

export default function MerkleLab({ setPage }) {
  const [data, setData] = useState(null)
  const [alg, setAlg] = useState('sha256')
  useEffect(()=>{ api.merkleBaselines().then(setData).catch(()=>setData({available:false})) }, [])
  if (!data) return <div><SectionTitle title="Laboratorio Merkle" subtitle="Cargando evidencia importada..."/></div>
  if (!data.available) return <div><SectionTitle title="Laboratorio Merkle" subtitle="Comparación entre mediciones y aproximaciones estructurales."/><EvidenceRequired setPage={setPage} detail="Importa una campaña que contenga merkle_benchmark.csv. La vista no utiliza valores Merkle embebidos cuando falta evidencia importada."/></div>

  const rows = data.algorithms?.[alg] || []
  return <div>
    <SectionTitle title="Laboratorio de modelos Merkle" subtitle="Medición frente a modelo ingenuo, corrección estructural y residuo observado."><Badge type="sim">MEDIDO + DERIVADO</Badge></SectionTitle>
    <SourceBanner source={data.source}/>
    <div className="mb-4 flex gap-2">{['sha256','sha3_256','blake3'].map(a=><button key={a} className={alg===a?'btn':'btn-red'} onClick={()=>setAlg(a)}>{a}</button>)}</div>
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartBox title="Tiempo medido frente a tiempo estimado"><ResponsiveContainer width="100%" height={320}><LineChart data={rows}><CartesianGrid stroke="#222"/><XAxis dataKey="leaves" tick={{fill:'#777',fontSize:10}}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}}/><Line dataKey="mean_ms" name="Medido" stroke="#22C55E" strokeWidth={2}/><Line dataKey="naive_ms" name="Ingenuo" stroke="#D72638" strokeWidth={2}/><Line dataKey="corr_ms" name="Corregido" stroke="#D4AF37" strokeWidth={2}/></LineChart></ResponsiveContainer></ChartBox>
      <ChartBox title="Error de estimación"><ResponsiveContainer width="100%" height={320}><BarChart data={rows}><CartesianGrid stroke="#222"/><XAxis dataKey="leaves" tick={{fill:'#777',fontSize:10}}/><YAxis tick={{fill:'#777',fontSize:10}}/><Tooltip contentStyle={{background:'#11131A',border:'1px solid #D4AF37'}}/><Bar dataKey="naive_err" name="Error ingenuo (%)" fill="#D72638"/><Bar dataKey="corr_err" name="Error corregido (%)" fill="#D4AF37"/></BarChart></ResponsiveContainer></ChartBox>
    </div>
  </div>
}
