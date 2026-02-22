export interface TemplateDiscovered {
  id: string;
  structure_hash: string;
  preview_text: string;
  variables: string[];
  tenant_id: string;
}

export interface SkeletonZone {
  zone_id: string; // El astra:id inyectado en el XML
  label: string;   // Nombre amigable (ej. "Apertura", "Debate")
  type: 'paragraph' | 'table';
}

export interface ZoneMapUpdate {
  zone_map: Record<string, string>; // template_id -> zone_id
}
