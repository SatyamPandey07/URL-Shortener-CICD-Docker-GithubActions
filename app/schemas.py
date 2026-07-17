from pydantic import BaseModel, HttpUrl, field_validator
from datetime import datetime


class ShortenRequest(BaseModel):
    """Request body for POST /shorten."""

    url: str

    @field_validator("url")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty.")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class ShortenResponse(BaseModel):
    """Response returned after successful shortening."""

    short_url: str
    code: str
    original_url: str

    model_config = {"from_attributes": True}


class LinkInfo(BaseModel):
    """Public representation of a stored link."""

    code: str
    original_url: str
    created_at: datetime
    click_count: int

    model_config = {"from_attributes": True}
