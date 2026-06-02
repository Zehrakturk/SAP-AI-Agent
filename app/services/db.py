"""
app/services/db.py

Merkezi MSSQL bağlantı yardımcısı.
Tüm servisler buradan import eder — bağlantı bilgileri tek yerde.
"""

import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()


def get_connection() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.getenv('DB_SERVER')};"
        f"DATABASE={os.getenv('DB_NAME')};"
        f"UID={os.getenv('DB_USER')};"
        f"PWD={os.getenv('DB_PASS')};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=yes;"
    )
    return pyodbc.connect(conn_str)


def rows_as_dicts(cursor: pyodbc.Cursor) -> list[dict]:
    """Cursor sonuçlarını dict listesine çevirir."""
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]
