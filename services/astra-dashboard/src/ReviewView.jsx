import { useState, useEffect, useRef } from 'react'
import { learningService } from './services/learningService'

export function ReviewView({ addToast }) {
  const [items, setItems] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const audioRef = useRef(null)

  // Load items on mount
  useEffect(() => {
     loadItems()
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e) => {
        // Prevent default if focusing input, but here we only have buttons
        if (e.key === 'Enter') handleDecision('APPROVE')
        if (e.key === 'Escape') handleDecision('REJECT')
        if (e.key === 'ArrowRight') setCurrentIndex(prev => Math.min(items.length - 1, prev + 1))
        if (e.key === 'ArrowLeft') setCurrentIndex(prev => Math.max(0, prev - 1))
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [currentIndex, items]) // Re-bind when items change to capture latest state

  // Auto-seek when current item changes
  useEffect(() => {
      if (audioRef.current && items[currentIndex]) {
          const start = items[currentIndex].data_json?.metadata?.start || 0
          // Set time. Note: browser might block auto-play if not interacted
          audioRef.current.currentTime = start
      }
  }, [currentIndex, items])

  const loadItems = async () => {
     setLoading(true)
     try {
         // Hardcoded tenant for now, ensuring we get pending items
         const pending = await learningService.getPendingReviews("tenant-default") 
         setItems(pending)
         setCurrentIndex(0)
     } catch (e) {
         console.error(e)
         addToast("Error al cargar revisiones", "error")
     } finally {
         setLoading(false)
     }
  }

  const handleDecision = async (decision) => {
      const currentItem = items[currentIndex]
      if (!currentItem) return

      try {
          await learningService.resolveReview(currentItem.id, decision)
          addToast(`Item ${decision === 'APPROVE' ? 'Aprobado' : 'Rechazado'}`, "success")
          
          // Optimistic remove
          const newItems = items.filter(i => i.id !== currentItem.id)
          setItems(newItems)
          
          // Adjust index if needed
          if (currentIndex >= newItems.length) {
              setCurrentIndex(Math.max(0, newItems.length - 1))
          }
      } catch (e) {
          console.error(e)
          addToast("Error al resolver revisión", "error")
      }
  }

  if (loading) return (
      <div className="flex items-center justify-center h-full text-white/50">
          <div className="animate-pulse">Cargando revisiones...</div>
      </div>
  )

  if (items.length === 0) return (
      <div className="flex flex-col items-center justify-center h-full p-12 text-center animate-in">
          <div className="text-6xl mb-6">🎉</div>
          <h2 className="text-3xl font-light text-white mb-2">Todo al día</h2>
          <p className="text-white/50 mb-8">No hay revisiones pendientes en la cola.</p>
          <button className="btn btn--secondary" onClick={loadItems}>Refrescar</button>
      </div>
  )

  const currentItem = items[currentIndex]
  const metadata = currentItem.data_json?.metadata || {}
  const inputData = currentItem.data_json?.input || ""
  const outputData = currentItem.data_json?.output || ""

  return (
      <div className="h-full flex flex-col p-6 animate-in text-white/90">
          {/* Header */}
          <header className="flex justify-between items-center mb-6">
              <div>
                  <h2 className="text-2xl font-light text-white flex items-center gap-3">
                      <span className="text-accent-amber">⚠</span> Validación Humana
                  </h2>
                  <p className="text-white/50 text-sm mt-1">{items.length} conflictos pendientes</p>
              </div>
              
              <div className="flex items-center gap-4 bg-white/5 p-2 rounded-lg border border-white/10">
                  <button className="btn btn--ghost btn--icon" onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}>←</button>
                  <span className="font-mono text-sm px-2">
                      {currentIndex + 1} <span className="text-white/30">/</span> {items.length}
                  </span>
                  <button className="btn btn--ghost btn--icon" onClick={() => setCurrentIndex(Math.min(items.length - 1, currentIndex + 1))}>→</button>
              </div>
          </header>

          {/* Split View */}
          <div className="flex-1 grid grid-cols-2 gap-6 min-h-0">
               {/* Left: Official Truth */}
               <div className="bg-white/5 rounded-xl border border-white/10 flex flex-col overflow-hidden">
                   <div className="bg-white/5 px-6 py-3 border-b border-white/5 flex justify-between items-center">
                       <span className="text-xs uppercase tracking-wider text-accent-cyan font-bold">Verdad Oficial (Acta)</span>
                       <span className="text-xs text-white/40 font-mono">TARGET</span>
                   </div>
                   <div className="flex-1 p-6 overflow-y-auto font-serif text-lg leading-relaxed whitespace-pre-wrap selection:bg-accent-cyan/30">
                       {outputData}
                   </div>
               </div>

               {/* Right: Evidence */}
               <div className="bg-white/5 rounded-xl border border-white/10 flex flex-col overflow-hidden relative">
                   <div className="bg-white/5 px-6 py-3 border-b border-white/5 flex justify-between items-center">
                       <span className="text-xs uppercase tracking-wider text-accent-amber font-bold">Evidencia (Audio)</span>
                       <span className="text-xs text-white/40 font-mono">
                           SOURCE • {metadata.start?.toFixed(1)}s - {metadata.end?.toFixed(1)}s
                       </span>
                   </div>
                   
                   <div className="flex-1 p-6 overflow-y-auto flex flex-col gap-4">
                       {/* AI Reasoning Box */}
                       {currentItem.validation_reasoning && (
                           <div className="bg-accent-amber/10 border border-accent-amber/20 rounded-lg p-4 text-sm text-accent-amber/90">
                               <div className="flex justify-between mb-1">
                                   <span className="font-bold text-xs uppercase opacity-70">IA Reasoning</span>
                                   <span className="font-mono text-xs opacity-70">Score: {currentItem.validation_score?.toFixed(2)}</span>
                               </div>
                               {currentItem.validation_reasoning}
                           </div>
                       )}

                       {/* Transcription */}
                       <div className="font-mono text-sm leading-relaxed text-white/70 bg-black/30 p-4 rounded-lg border border-white/5 whitespace-pre-wrap">
                           {inputData}
                       </div>
                   </div>

                   {/* Controls Footer */}
                   <div className="p-6 bg-black/40 border-t border-white/10">
                       {metadata.audio_url ? (
                           <audio 
                               ref={audioRef} 
                               controls 
                               className="w-full mb-6 invert-[.9]" 
                               src={metadata.audio_url} 
                           />
                       ) : (
                           <div className="text-red-400 text-xs mb-6 text-center border border-red-500/20 bg-red-500/10 p-2 rounded">
                               Audio no disponible (URL presignada faltante)
                           </div>
                       )}

                       <div className="grid grid-cols-2 gap-4">
                           <button 
                               className="h-12 rounded-lg font-bold text-sm bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30 transition-all flex items-center justify-center gap-2"
                               onClick={() => handleDecision('APPROVE')}
                               title="Presiona Enter"
                           >
                               <span>✓ APROBAR</span>
                               <span className="bg-black/20 px-2 py-0.5 rounded text-[10px] opacity-70">ENTER</span>
                           </button>
                           <button 
                               className="h-12 rounded-lg font-bold text-sm bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-all flex items-center justify-center gap-2"
                               onClick={() => handleDecision('REJECT')}
                               title="Presiona Esc"
                           >
                               <span>✕ RECHAZAR</span>
                               <span className="bg-black/20 px-2 py-0.5 rounded text-[10px] opacity-70">ESC</span>
                           </button>
                       </div>
                   </div>
               </div>
          </div>
      </div>
  )
}
