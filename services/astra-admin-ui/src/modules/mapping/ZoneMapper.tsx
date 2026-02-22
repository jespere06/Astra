import React, { useState, useEffect } from 'react';
import axios from 'axios';

// Tipos definidos según el DTO del backend
interface UnmappedTemplate {
  template_id: string;
  structure_hash: string;
  preview_text: string;
  variables: string[];
}

interface MappingPayload {
  template_id: string;
  zone_id: string;
}

const ZONES = [
  { id: 'ZONE_HEADER', label: 'Encabezado' },
  { id: 'ZONE_BODY', label: 'Cuerpo (Acta)' },
  { id: 'ZONE_FOOTER', label: 'Pie de Página' },
  { id: 'ZONE_ANNEX', label: 'Anexos' },
];

export const ZoneMapper: React.FC<{ tenantId: string }> = ({ tenantId }) => {
  const [templates, setTemplates] = useState<UnmappedTemplate[]>([]);
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Cargar templates al iniciar
  useEffect(() => {
    fetchTemplates();
  }, [tenantId]);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`/v1/config/${tenantId}/unmapped-templates`);
      setTemplates(res.data);
      // Limpiar selecciones previas
      setSelections({});
    } catch (err) {
      console.error("Error cargando templates:", err);
      alert("Error cargando templates. Ver consola.");
    } finally {
      setLoading(false);
    }
  };

  const handleZoneChange = (templateId: string, zoneId: string) => {
    setSelections(prev => ({
      ...prev,
      [templateId]: zoneId
    }));
  };

  const handleSave = async () => {
    const mappings: MappingPayload[] = Object.entries(selections).map(([tid, zid]) => ({
      template_id: tid,
      zone_id: zid
    }));

    if (mappings.length === 0) return;

    setSaving(true);
    try {
      await axios.put(`/v1/config/${tenantId}/mappings`, { mappings });
      alert("✅ Mapeos guardados exitosamente.");
      fetchTemplates(); // Recargar lista
    } catch (err) {
      console.error("Error guardando:", err);
      alert("❌ Error al guardar. Verifique los datos.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-10 text-center">Cargando inteligencia...</div>;

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Mapeo de Zonas (Human-in-the-loop)</h1>
        <button
          onClick={handleSave}
          disabled={Object.keys(selections).length === 0 || saving}
          className={`px-4 py-2 rounded font-bold text-white transition-colors ${
            Object.keys(selections).length === 0 || saving
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {saving ? 'Guardando...' : `Guardar (${Object.keys(selections).length}) Cambios`}
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-100">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Contenido Detectado (Preview)
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/4">
                Variables
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/5">
                Zona de Destino
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {templates.map((tmpl) => (
              <tr key={tmpl.template_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4">
                  <div className="text-sm text-gray-900 font-mono bg-gray-50 p-2 rounded border border-gray-100 max-h-32 overflow-y-auto">
                    {tmpl.preview_text}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">Hash: {tmpl.structure_hash.substring(0, 8)}</div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">
                  {tmpl.variables.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {tmpl.variables.map(v => (
                        <span key={v} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                          {v}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-gray-400 italic">Texto Estático (Boilerplate)</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <select
                    value={selections[tmpl.template_id] || ""}
                    onChange={(e) => handleZoneChange(tmpl.template_id, e.target.value)}
                    className={`block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md ${
                        selections[tmpl.template_id] ? 'bg-green-50 border-green-500 text-green-900' : 'bg-white'
                    }`}
                  >
                    <option value="" disabled>Seleccionar zona...</option>
                    {ZONES.map(z => (
                      <option key={z.id} value={z.id}>{z.label}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
            
            {templates.length === 0 && (
                <tr>
                    <td colSpan={3} className="px-6 py-10 text-center text-gray-500">
                        🎉 ¡Todo listo! No hay plantillas pendientes de revisión.
                    </td>
                </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
