from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict
from datetime import datetime

class URLShortenRequest(BaseModel):
    long_url: str = Field(..., description="The original long URL to shorten")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration timestamp")

    # Simple custom validation to check url prefix
    def validate_url(self):
        if not (self.long_url.startswith("http://") or self.long_url.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return self.long_url

class URLResponse(BaseModel):
    short_token: str
    short_url: str
    long_url: str
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True

class DailyClickCount(BaseModel):
    date: str
    clicks: int

class CountryClickCount(BaseModel):
    country: str
    clicks: int

class URLAnalyticsResponse(BaseModel):
    short_token: str
    long_url: str
    created_at: datetime
    expires_at: Optional[datetime]
    total_clicks: int
    clicks_over_time: List[DailyClickCount]
    geo_distribution: List[CountryClickCount]

class GlobalAnalyticsResponse(BaseModel):
    total_urls: int
    total_clicks: int
    clicks_over_time: List[DailyClickCount]
    geo_distribution: List[CountryClickCount]
