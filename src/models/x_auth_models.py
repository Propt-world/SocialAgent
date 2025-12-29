# src/models/x_auth_models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class AccountResponse(BaseModel):
    username: str
    cookies: dict
    user_agent: str
    headers: dict
    proxy: str | None = None