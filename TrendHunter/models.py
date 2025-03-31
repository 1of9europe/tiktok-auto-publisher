from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Optional

class TrendMetadata(BaseModel):
    views: Optional[int] = 0
    videos: Optional[int] = 0
    description: Optional[str] = ""
    source: Optional[str] = "api"
    category: Optional[str] = None

class Trend(BaseModel):
    platform: str
    type: str
    name: str
    timestamp: datetime
    metadata: TrendMetadata

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 