from pydantic import BaseModel
from typing import List, Optional, Any

# --- 1. GENERIC RESPONSES ---
# Standardize all your API responses
class GenericResponse(BaseModel):
    status: str  # "success" or "error"
    message: str
    data: Optional[Any] = None

# --- 2. QUEUE MONITORING ---
class QueueStatus(BaseModel):
    queue_name: str
    pending_jobs: int
    status: str  # "healthy", "busy", "backlogged"

# --- 3. JOB TRIGGER RESPONSE ---
class JobSubmissionResponse(BaseModel):
    status: str
    job_id: Optional[str] = None
    message: str
    target: str

# --- 4. HEALTH CHECK ---
class HealthResponse(BaseModel):
    service: str = "SocialAgent API"
    status: str
    database: str
    redis: str

# --- 5. ERROR RESPONSE ---
class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    code: Optional[str] = None
    details: Optional[Any] = None