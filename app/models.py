from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class Link(Base):
    """Maps a short code to its original URL and tracks usage."""

    __tablename__ = "links"

    code = Column(String(6), primary_key=True, index=True)
    original_url = Column(String(2048), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    click_count = Column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<Link code={self.code!r} url={self.original_url!r} clicks={self.click_count}>"
