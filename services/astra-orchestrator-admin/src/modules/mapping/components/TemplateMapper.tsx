import React, { useState, useEffect } from 'react';
import { IngestAPI, ConfigAPI } from '../../../infrastructure/api/clients';
import { TemplateDiscovered, SkeletonZone } from '../../../infrastructure/api/types';

interface Props {
  tenantId: string;
  activeSkeletonId: string;
}

export const TemplateMapper: React.FC<Props> = ({ tenantId, activeSkeletonId }) => {
  const [templates, setTemplates] = useState<TemplateDiscovered[]>([]);
  const [zones, setZones] = useState<SkeletonZone[]>([]);
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    // Carga inicial coordinada
    Promise.all([
      IngestAPI.getTemplates(tenantId),
      IngestAPI.getZones(activeSkeletonId)
    ]).then(([tmplRes, zoneRes]) => {
      setTemplates(tmplRes.data);
      setZones(zoneRes.data);
    });
  }, [tenantId, activeSkeletonId]);

  const handleMapChange = (templateId: string, zoneId: string) => {
    setMappings(prev => ({ ...prev, [templateId]: zoneId }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await ConfigAPI.updateZoneMap(tenantId, { zone_map: mappings });
      alert("✅ Ruteo actualizado correctamente");
    } catch (err) {
      alert("❌ Error al persistir el mapeo");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <header className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Ruteo Semántico-Físico</h1>
          <p className="text-slate-500">Asocia plantillas detectadas con zonas del documento</p>
        </div>
        <button 
          onClick={handleSave}
          disabled={isSaving}
          className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {isSaving ? "Guardando..." : "Sincronizar Mapeos"}
        </button>
      </header>

      <div className="grid gap-4">
        {templates.map(tmpl => (
          <div key={tmpl.id} className="bg-white border rounded-xl p-4 flex items-center shadow-sm">
            <div className="flex-1">
              <span className="text-xs font-bold text-indigo-500 uppercase">Plantilla Detectada</span>
              <p className="text-sm font-mono text-slate-700 mt-1 truncate pr-4">
                {tmpl.preview_text}
              </p>
            </div>

            <div className="w-64">
              <select 
                className="w-full border-slate-200 rounded-md text-sm"
                value={mappings[tmpl.id] || ""}
                onChange={(e) => handleMapChange(tmpl.id, e.target.value)}
              >
                <option value="">-- Seleccionar Zona --</option>
                {zones.map(z => (
                  <option key={z.zone_id} value={z.zone_id}>
                    {z.label} ({z.type})
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
