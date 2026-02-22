from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime

class TenantConfigBase(BaseModel):
    active_skeleton_id: Optional[str] = None
    style_map: Dict[str, str] = Field(default_factory=dict, description="Map client styles to ASTRA styles")
    zone_map: Dict[str, str] = Field(default_factory=dict, description="Map template UUIDs to Zone IDs")
    table_map: Dict[str, str] = Field(default_factory=dict, description="Map intent IDs to Table UUIDs")

class TenantConfigUpdate(TenantConfigBase):
    pass

class TenantConfigResponse(TenantConfigBase):
    tenant_id: str
    updated_at: datetime
    version: str

    class Config:
        from_attributes = True
