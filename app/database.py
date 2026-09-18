"""Azure SQL connections. Store datetime2 values in UTC and close every connection."""
import os
from contextlib import contextmanager
from datetime import timezone

import pyodbc


def connection_string():
    names = ("AZURE_SQL_SERVER", "AZURE_SQL_DATABASE", "AZURE_SQL_USER", "AZURE_SQL_PASSWORD")
    values = {name: os.getenv(name, "") for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise pyodbc.InterfaceError("Missing database settings: " + ", ".join(missing))
    # ODBC braces protect semicolons and escape closing braces in credentials.
    def quoted(value):
        return "{" + value.replace("}", "}}") + "}"
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={quoted('tcp:' + values['AZURE_SQL_SERVER'] + ',1433')};"
        f"DATABASE={quoted(values['AZURE_SQL_DATABASE'])};"
        f"UID={quoted(values['AZURE_SQL_USER'])};"
        f"PWD={quoted(values['AZURE_SQL_PASSWORD'])};"
        "Encrypt=yes;TrustServerCertificate=no;"
    )


@contextmanager
def get_conn():
    conn = pyodbc.connect(connection_string(), timeout=15, autocommit=False)
    conn.timeout = 30
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def timestamp_utc(value):
    """pyodbc returns datetime2 as naive datetime; explicitly label it UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat()
