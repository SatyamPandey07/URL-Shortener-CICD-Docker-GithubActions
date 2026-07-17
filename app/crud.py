from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Link
from app.shortener import generate_code

_MAX_RETRIES = 10


def get_link_by_code(db: Session, code: str) -> Link | None:
    """Fetch a Link by its short code, or None if not found."""
    return db.query(Link).filter(Link.code == code).first()


def create_link(db: Session, original_url: str) -> Link:
    """Create a new Link with a unique generated code.

    Retries up to _MAX_RETRIES times on the off-chance of a code collision.
    Raises RuntimeError if it can't find a unique code (practically impossible).
    """
    for _ in range(_MAX_RETRIES):
        code = generate_code()
        link = Link(code=code, original_url=original_url)
        db.add(link)
        try:
            db.commit()
            db.refresh(link)
            return link
        except IntegrityError:
            db.rollback()  # code collision — retry

    raise RuntimeError("Unable to generate a unique short code after multiple retries.")


def increment_click(db: Session, link: Link) -> None:
    """Atomically increment the click counter for a link."""
    link.click_count += 1
    db.commit()
