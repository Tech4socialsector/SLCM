# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

"""
SQL Server connection helper for the RFID SQL Agent.

Reads credentials from "RFID SQL Agent Settings" (single doctype) and
returns a live pyodbc connection. Callers are responsible for closing it.
"""

import os
import frappe

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

# Absolute path to the custom OpenSSL config that enables TLS 1.0.
# Required because SQL Server 2014 only supports TLS 1.0, which Ubuntu 22.04
# / OpenSSL 3 disables by default. We override OPENSSL_CONF at the process
# level before opening the pyodbc connection so only this code is affected.
_OPENSSL_CNF = os.path.join(_APP_ROOT, "mssql_openssl.cnf")

# Absolute path to the custom GnuTLS priority override that allows TLS 1.0/1.1.
# FreeTDS uses GnuTLS (not OpenSSL) for its encrypted-login handshake on this
# system, and GnuTLS also refuses TLS 1.0 by default — the OPENSSL_CONF
# override above has no effect on it, so it needs its own env var.
_GNUTLS_CNF = os.path.join(_APP_ROOT, "mssql_gnutls_override.conf")


def get_connection():
    """
    Return an open pyodbc connection to the SQL Server configured in
    RFID SQL Agent Settings. Raises frappe.ValidationError with a clear
    message if config is incomplete or the connection fails.
    """
    try:
        import pyodbc
    except ImportError:
        frappe.throw(
            "pyodbc is not installed. Run: bench pip install pyodbc",
            title="Missing Dependency"
        )

    cfg = frappe.get_single("RFID SQL Agent Settings")

    server   = (cfg.db_server   or "").strip()
    port     = int(cfg.db_port  or 1433)
    database = (cfg.db_database or "").strip()
    username = (cfg.db_login    or "").strip()
    password = cfg.get_password("db_password") or ""

    if not all([server, database, username]):
        frappe.throw(
            "SQL Server connection is not fully configured. "
            "Fill Server Host, Database, and Username in RFID SQL Agent Settings → SQL Server tab.",
            title="RFID SQL Agent — SQL Server Not Configured"
        )

    drivers = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "FreeTDS",
        "SQL Server",
    ]

    available = list(pyodbc.drivers())
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

    if chosen == "FreeTDS":
        conn_str += "TDS_Version=7.4;"

    _prev_openssl_conf = os.environ.get("OPENSSL_CONF")
    _prev_gnutls_prio  = os.environ.get("GNUTLS_SYSTEM_PRIORITY_FILE")
    _prev_gnutls_fail  = os.environ.get("GNUTLS_SYSTEM_PRIORITY_FAIL_ON_INVALID")

    if os.path.exists(_OPENSSL_CNF):
        os.environ["OPENSSL_CONF"] = _OPENSSL_CNF
    if os.path.exists(_GNUTLS_CNF):
        os.environ["GNUTLS_SYSTEM_PRIORITY_FILE"] = _GNUTLS_CNF
        os.environ["GNUTLS_SYSTEM_PRIORITY_FAIL_ON_INVALID"] = "0"

    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
    except Exception as e:
        frappe.throw(
            f"Could not connect to SQL Server ({server}:{port}/{database}): {e}",
            title="RFID SQL Agent — SQL Server Connection Failed"
        )
    finally:
        for var, prev in (
            ("OPENSSL_CONF", _prev_openssl_conf),
            ("GNUTLS_SYSTEM_PRIORITY_FILE", _prev_gnutls_prio),
            ("GNUTLS_SYSTEM_PRIORITY_FAIL_ON_INVALID", _prev_gnutls_fail),
        ):
            if prev is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = prev

    return conn
