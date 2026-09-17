import os
from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# LOAD .env
# ============================================================

load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# DATABASE
# ============================================================

POSTGRES_DB = os.getenv("POSTGRES_DB", "bridge")
POSTGRES_USER = os.getenv("POSTGRES_USER", "bridge")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "bridgepass")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    (
        f"postgresql://{POSTGRES_USER}:"
        f"{POSTGRES_PASSWORD}"
        f"@localhost:5432/{POSTGRES_DB}"
    )
)
# ============================================================
# ARCHIVE POLICY
# ============================================================

# Any data older than 1 days is eligible for archiving.
ARCHIVE_AFTER_DAYS = 1

# Number of database rows processed at one time.
# This avoids loading millions of rows into RAM.
FETCH_SIZE = 100_000

# ============================================================
# ONEDRIVE
# ============================================================

def find_onedrive():
    """
    Find the user's OneDrive folder automatically.
    """

    candidates = [
        os.getenv("OneDrive"),
        os.getenv("OneDriveConsumer"),
        os.getenv("OneDriveCommercial"),
        Path.home() / "OneDrive",
        Path.home() / "OneDrive - Monash University",
    ]

    for candidate in candidates:
        if candidate:
            path = Path(candidate)

            if path.exists():
                return path

    raise FileNotFoundError(
        "OneDrive folder could not be found."
    )

ONEDRIVE_ROOT = find_onedrive()

ARCHIVE_ROOT = (
    ONEDRIVE_ROOT
    / "BridgeDigitalTwin"
    / "Archive"
)

ARCHIVE_ROOT.mkdir(
    parents=True,
    exist_ok=True
)