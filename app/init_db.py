"""Explicit setup command; the web application never creates tables on startup."""
from pathlib import Path
from app.database import get_conn


def main():
    schema = Path(__file__).resolve().parent.parent / "init.sql"
    with get_conn() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(schema.read_text(encoding="utf-8"))
            while cursor.nextset():
                pass
        finally:
            cursor.close()
    print("Azure SQL schema ready; four bridge sensors and 200 test sensors registered.")


if __name__ == "__main__":
    main()
