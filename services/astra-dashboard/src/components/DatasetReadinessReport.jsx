import React from 'react';

export function DatasetReadinessReport({ metrics, onClose }) {
  const scoreColor = metrics.structural_coverage_pct > 80 ? 'text-[#22c55e]' : 'text-[#f59e0b]';

  // Fallbacks para evitar crashes si vienen nulos
  const totalPairs = metrics.aligned_pairs || metrics.total_aligned_pairs || 0;
  const staticCount = metrics.static_nodes || 0;
  const dynamicCount = metrics.dynamic_nodes || 0;
  const coverage = metrics.structural_coverage_pct || 0;

  return (
    // Z-Index 9999 para asegurar que tape todo el dashboard
    <div className="fixed inset-0 bg-black/95 backdrop-blur-sm z-[9999] flex items-center justify-center p-4 sm:p-8 animate-in">
      <div className="bg-[#0c0c18] border border-white/10 rounded-2xl w-full max-w-6xl h-[90vh] flex flex-col shadow-2xl overflow-hidden relative">
        
        {/* Header */}
        <div className="p-6 border-b border-white/10 flex justify-between items-center bg-[#1a1a2e]">
          <div>
            <h3 className="text-xl font-bold text-white flex items-center gap-3">
              <span className="text-[#00e5ff] text-2xl">🔍</span> 
              Reporte de Disponibilidad de Datos
            </h3>
            <p className="text-white/50 text-xs mt-1 font-mono uppercase tracking-wider">
              Validación Pre-Entrenamiento Completada
            </p>
          </div>
          <button 
            onClick={onClose} 
            className="px-6 py-2 bg-white/5 hover:bg-white/10 hover:text-white rounded-lg text-sm font-bold text-gray-300 transition-colors border border-white/5"
          >
            Cerrar Reporte
          </button>
        </div>

        {/* Metrics Dashboard */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-6 border-b border-white/10 bg-black/40">
          <MetricBox 
            label="Pares Alineados" 
            value={totalPairs} 
            icon="🔗"
            subLabel="Ejemplos listos"
          />
          <MetricBox 
            label="Cobertura Estructural" 
            value={`${coverage}%`} 
            color={scoreColor}
            icon="📊"
            subLabel="Calidad del XML"
          />
          <MetricBox 
            label="Nodos Estáticos" 
            value={staticCount} 
            icon="🔒"
            subLabel="Boilerplate detectado"
          />
          <MetricBox 
            label="Fragmentos Dinámicos" 
            value={dynamicCount} 
            icon="🧩"
            subLabel="Variables a entrenar"
          />
        </div>

        {/* Data Sample Explorer */}
        <div className="flex-1 overflow-y-auto p-6 bg-[#0c0c18]">
          <div className="flex justify-between items-end mb-6">
            <h4 className="text-sm font-bold text-white/60 uppercase tracking-widest flex items-center gap-2">
              <span className="w-2 h-2 bg-[#00e5ff] rounded-full"></span>
              Muestra de Alineación Semántica
            </h4>
            <span className="text-[10px] bg-white/5 px-3 py-1 rounded-full text-white/40 border border-white/5">
              Muestreo aleatorio del dataset generado
            </span>
          </div>
          
          <div className="space-y-4">
            {metrics.sample_pairs && metrics.sample_pairs.length > 0 ? (
              metrics.sample_pairs.map((row, i) => (
                <div key={i} className="group bg-[#13131f] border border-white/5 rounded-xl p-5 hover:border-[#00e5ff]/30 transition-all shadow-lg">
                  
                  {/* Metadata Row */}
                  <div className="flex justify-between mb-3 border-b border-white/5 pb-2">
                    <span className="font-mono text-[10px] text-[#00e5ff] bg-[#00e5ff]/10 px-2 py-0.5 rounded font-bold">
                      INPUT (TRANSCRIPCIÓN)
                    </span>
                    <span className="font-mono text-[10px] text-white/40">
                      Confianza: <span className="text-green-400 font-bold">{row.score?.toFixed(2) || 'N/A'}</span>
                    </span>
                  </div>
                  
                  {/* Input Text */}
                  <div className="text-gray-300 mb-5 font-mono text-sm leading-relaxed whitespace-pre-wrap break-words pl-2 border-l-2 border-[#00e5ff]/20">
                    {row.input}
                  </div>
                  
                  {/* Target Row */}
                  <div className="flex justify-between mb-2">
                    <span className="font-mono text-[10px] text-[#7c3aed] bg-[#7c3aed]/10 px-2 py-0.5 rounded font-bold">
                      TARGET (XML/DOCX)
                    </span>
                  </div>
                  
                  {/* Output Text */}
                  <div className="text-gray-400 font-mono text-xs leading-relaxed bg-black/50 p-4 rounded-lg border border-white/5 font-serif italic overflow-x-auto">
                    {row.output}
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-white/30 border-2 border-dashed border-white/5 rounded-xl bg-white/[0.01]">
                <span className="text-4xl mb-4">📭</span>
                <p>No se encontraron pares alineados para mostrar.</p>
                <p className="text-xs mt-2">Intenta procesar más documentos o revisar los umbrales de confianza.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricBox({ label, value, color = "text-white", icon, subLabel }) {
  return (
    <div className="bg-[#13131f] border border-white/5 rounded-xl p-4 flex flex-col items-center justify-center relative overflow-hidden group hover:bg-[#1a1a2e] transition-colors">
      <div className="absolute top-2 right-3 opacity-20 text-4xl grayscale group-hover:grayscale-0 group-hover:opacity-30 transition-all duration-500 transform group-hover:scale-110 pointer-events-none">{icon}</div>
      <span className={`text-4xl font-black ${color} tracking-tight z-10`}>{value}</span>
      <span className="text-[10px] uppercase tracking-widest text-white/50 font-bold mt-2 z-10">{label}</span>
      {subLabel && <span className="text-[9px] text-white/20 mt-1">{subLabel}</span>}
    </div>
  );
}