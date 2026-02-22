from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class SnapshotResponse(BaseModel):
    snapshot_id: str
    tenant_id: str
    root_hash: str
    signature: str
    artifact_url: str
    s3_version_id: str
    created_at: str
    status: str = "SEALED"

class VerificationResponse(BaseModel):
    is_valid: bool
    snapshot_id: str
    verification_timestamp: str
    audit_report: Dict[str, Any]
    
class IntegrityReport(BaseModel):
    calculated_hash: str
    stored_hash: str
    match: bool
    details: Optional[str] = None
