"""Configuration. All secrets come from environment variables at runtime.

Nothing secret is committed. The TMDB read token lives in the Secure Vault
as custom.tmdb and is exported as TMDB_READ_TOKEN when a command runs.
"""

import os

TMDB_READ_TOKEN = os.environ.get("TMDB_READ_TOKEN", "")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
SEATGEEK_CLIENT_ID = os.environ.get("SEATGEEK_CLIENT_ID", "")
DB_PATH = os.environ.get("BOXOFFICE_DB", "boxoffice.db")
DEFAULT_REGION = os.environ.get("BOXOFFICE_REGION", "US")
DEFAULT_LANGUAGE = os.environ.get("BOXOFFICE_LANGUAGE", "en-US")


def tmdb_image_url(poster_path: str | None, size: str = "w342") -> str:
    """Full poster URL for a TMDB poster path. Empty string when unknown."""
    if not poster_path:
        return ""
    return f"https://image.tmdb.org/t/p/{size}{poster_path}"


def require_tmdb_token() -> str:
    """Return the TMDB read token or raise a clear error."""
    if not TMDB_READ_TOKEN:
        raise RuntimeError(
            "TMDB_READ_TOKEN is not set. Add your TMDB API read access token "
            "to the Secure Vault as custom.tmdb and export it as TMDB_READ_TOKEN "
            "before running. See README for setup."
        )
    return TMDB_READ_TOKEN
