from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Configuration Models (Input from DB) ---

class SourceConfig(BaseModel):
    fetch_interval_minutes: int = Field(default=60, ge=5) # Minimum 5 mins
    max_tweets: int = Field(default=20, le=100)           # Max 100 per run

class SocialTarget(BaseModel):
    id: Optional[str] = Field(alias="_id", default=None)
    username: str
    platform: str = "twitter"
    enabled: bool = True
    config: SourceConfig = Field(default_factory=SourceConfig)
    last_run_at: Optional[datetime] = None

    class Config:
        populate_by_name = True  # Allows using "_id" or "id"