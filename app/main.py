import os
from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.database import get_db, engine, Base
from app.models import Link
from app import crud, schemas

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

Base.metadata.create_all(bind=engine)  # creates tables if they don't exist

app = FastAPI(
    title="ShortLink",
    description="A minimal URL shortener built with FastAPI.",
    version="0.1.0",
)

templates = Jinja2Templates(directory="templates")

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Health check (used by deployment pipeline health probes)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["ops"])
def health_check():
    """Returns a simple OK status — used by CI/CD pipeline health checks."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, tags=["ui"])
def homepage(request: Request):
    """Render the homepage with an empty shorten form."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"short_url": None, "error": None, "original_url": None},
    )


# ---------------------------------------------------------------------------
# POST /shorten  (handles both API JSON and HTML form submissions)
# ---------------------------------------------------------------------------

@app.post("/shorten", tags=["api"])
def shorten_url(
    request: Request,
    url: str = Form(...),
    db: Session = Depends(get_db),
):
    """Accept a long URL, generate a short code, persist it, and return the result.

    Handles both:
    - HTML form submissions (returns rendered page)
    - JSON clients (returns ShortenResponse JSON)
    """
    # Validate via Pydantic schema
    try:
        validated = schemas.ShortenRequest(url=url)
    except (ValidationError, ValueError) as exc:
        error_msg = _extract_error(exc)
        # If the client accepts JSON, return JSON error
        if _wants_json(request):
            raise HTTPException(status_code=422, detail=error_msg)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": error_msg, "short_url": None, "original_url": url},
            status_code=422,
        )

    link = crud.create_link(db, validated.url)
    short_url = f"{BASE_URL}/{link.code}"

    if _wants_json(request):
        return schemas.ShortenResponse(
            short_url=short_url,
            code=link.code,
            original_url=link.original_url,
        )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "short_url": short_url,
            "code": link.code,
            "original_url": link.original_url,
            "error": None,
        },
    )


# ---------------------------------------------------------------------------
# GET /{code}  — redirect to original URL
# ---------------------------------------------------------------------------

@app.get("/{code}", tags=["redirect"])
def redirect_to_url(code: str, request: Request, db: Session = Depends(get_db)):
    """Look up the short code and 302-redirect to the original URL.

    Uses 302 (not 301) so browsers don't cache the redirect — important for
    accurate click counting.
    """
    link = crud.get_link_by_code(db, code)
    if link is None:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"code": code},
            status_code=404,
        )

    crud.increment_click(db, link)
    return RedirectResponse(url=link.original_url, status_code=302)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wants_json(request: Request) -> bool:
    """Return True if the client explicitly requests a JSON response."""
    accept = request.headers.get("accept", "")
    content_type = request.headers.get("content-type", "")
    return "application/json" in accept or "application/json" in content_type


def _extract_error(exc: Exception) -> str:
    """Pull a human-readable message out of a Pydantic ValidationError or ValueError."""
    if isinstance(exc, ValidationError):
        try:
            return exc.errors()[0]["msg"].replace("Value error, ", "")
        except (IndexError, KeyError):
            pass
    return str(exc)
