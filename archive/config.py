import os
from pathlib import Path

# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bridge:bridgepass@localhost:5432/bridge"
)

# ============================================================
# ARCHIVE POLICY
# ============================================================

# Any data older than 30 days is eligible for archiving.
ARCHIVE_AFTER_DAYS = 30

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