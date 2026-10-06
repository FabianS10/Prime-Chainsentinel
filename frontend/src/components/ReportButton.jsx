import { useState } from 'react'
import { api } from '../api/client'

export default function ReportButton({ label='Generar reporte PDF', payload, disabled=false }) {
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')

  async function download(){
    if(disabled || loading) return
    setLoading(true); setError('')
    try{
      const blob = await api.generateReport(payload || { title: 'Prime ChainSentinel — Reporte de evidencia y procedencia', include_blockchain: true })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'prime_chainsentinel_reporte.pdf'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    }catch(err){
      setError(err.message || 'No fue posible generar el reporte.')
    }finally{
      setLoading(false)
    }
  }

  return <div>
    <button className="btn" disabled={disabled || loading} onClick={download}>{loading?'Generando...':label}</button>
    {error&&<div className="mt-3 rounded-lg border border-prime-brightRed/30 bg-prime-brightRed/10 px-4 py-3 text-sm text-prime-brightRed">{error}</div>}
  </div>
}
