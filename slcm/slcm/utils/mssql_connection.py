# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

"""
Utility: Microsoft SQL Server connection helper.

Reads credentials from Attendance Settings (single doctype) and returns
a live pyodbc connection.  Callers are responsible for closing the
connection after use.

Usage:
    from slcm.slcm.utils.mssql_connection import get_mssql_connection
    conn = get_mssql_connection()
    cursor = conn.cursor()
    ...
    conn.close()
"""

import os
import frappe

# Absolute path to the custom OpenSSL config that enables TLS 1.0.
# Required because SQL Server 2014 only supports TLS 1.0, which Ubuntu 22.04
# / OpenSSL 3 disables by default.  We override OPENSSL_CONF at the process
# level before opening the pyodbc connection so only this code is affected.
_OPENSSL_CNF = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    )))),
    "mssql_openssl.cnf"
)


def get_mssql_connection():
    """
    Return an open pyodbc connection to the configured SQL Server.
    Raises frappe.ValidationError with a clear message if config is
    incomplete or the connection fails.
    """
    try:
        import pyodbc
    except ImportError:
        frappe.throw(
            "pyodbc is not installed. Run: bench pip install pyodbc",
            title="Missing Dependency"
        )

    cfg = frappe.get_single("Attendance Settings")

    server   = (cfg.mssql_server   or "").strip()
    port     = int(cfg.mssql_port  or 1433)
    database = (cfg.mssql_database or "").strip()
    username = (cfg.mssql_username or "").strip()
    password = cfg.get_password("mssql_password") or ""

    if not all([server, database, username]):
        frappe.throw(
            "SQL Server connection is not fully configured. "
            "Fill Server Host, Database, and Username in Attendance Settings → SQL Server section.",
            title="RFID SQL Server Not Configured"
        )

    # Try ODBC Driver 18, fall back to 17, then the generic SQL Server driver.
    drivers = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ]

    available = [d for d in pyodbc.drivers()]
    chosen = next((d for d in drivers if d in available), None)

    if not chosen:
        frappe.throw(
            f"No compatible ODBC driver found. Install 'ODBC Driver 17 for SQL Server' on the server. "
            f"Drivers found: {available}",
            title="ODBC Driver Missing"
        )

    conn_str = (
        f"DRIVER={{{chosen}}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=10;"
    )

    # SQL Server 2014 only supports TLS 1.0.  Temporarily point OpenSSL at a
    # config that lowers the minimum protocol to TLSv1 for this connection.
    _prev_openssl_conf = os.environ.get("OPENSSL_CONF")
    if os.path.exists(_OPENSSL_CNF):
        os.environ["OPENSSL_CONF"] = _OPENSSL_CNF

    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
    except Exception as e:
        frappe.throw(
            f"Could not connect to SQL Server ({server}:{port}/{database}): {e}",
            title="RFID SQL Server Connection Failed"
        )
    finally:
        # Restore OPENSSL_CONF regardless of success or failure
        if _prev_openssl_conf is None:
            os.environ.pop("OPENSSL_CONF", None)
        else:
            os.environ["OPENSSL_CONF"] = _prev_openssl_conf

    return conn


@frappe.whitelist()
def test_mssql_connection():
    """
    Whitelisted API — called from Attendance Settings 'Test Connection' button.
    Returns a dict so the JS caller can show a success/failure message.
    """
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        conn.close()
        return {"success": True, "message": f"Connected. Server: {version[:80]}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
