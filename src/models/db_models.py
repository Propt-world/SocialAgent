# src/models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Data Models (Output to DB) ---

class TweetMetrics(BaseModel):
    likes: int = 0
    retweets: int = 0
    replies: int = 0

class SocialPost(BaseModel):
    id: str = Field(alias="_id") # Map "_id" to "id"
    platform: str = "twitter"
    source_username: str
    url: str
    content: str
    images: List[str] = []
    metrics: TweetMetrics
    published_at: datetime
    discovered_at: datetime
    
    class Config:
        populate_by_name = True