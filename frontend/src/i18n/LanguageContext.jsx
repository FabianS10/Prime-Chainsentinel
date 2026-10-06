import { createContext, useContext, useMemo } from 'react'

const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  // La versión de tesis utiliza una interfaz única en español para evitar
  // etiquetas mezcladas y mantener consistencia con la documentación.
  const value = useMemo(() => ({
    lang:'es',
    setLang:()=>{},
    t:(text)=>text,
  }), [])
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(){
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage debe utilizarse dentro de LanguageProvider')
  return ctx
}
