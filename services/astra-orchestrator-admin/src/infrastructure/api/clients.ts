import axios from 'axios';
import { TemplateDiscovered, SkeletonZone, ZoneMapUpdate } from './types';

// En producción, estas URLs vienen de variables de entorno
const INGEST_URL = '/services/ingest/v1';
const CONFIG_URL = '/services/config/v1';

export const IngestAPI = {
  getTemplates: (tenantId: string) => 
    axios.get<TemplateDiscovered[]>(`${INGEST_URL}/templates/${tenantId}`),
    
  getZones: (skeletonId: string) => 
    axios.get<SkeletonZone[]>(`${INGEST_URL}/skeletons/${skeletonId}/zones`),
};

export const ConfigAPI = {
  updateZoneMap: (tenantId: string, data: ZoneMapUpdate) => 
    axios.patch(`${CONFIG_URL}/config/${tenantId}`, data),
};
