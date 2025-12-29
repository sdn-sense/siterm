#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
Date                    : 2025/01/05

SQLite Backend for SiteRM Registration Database.
Main Purpose:
  - Store any agent/client registration requests
  - Required admin approval
  - Isolated from MySQL backend
"""
import os
import sqlite3
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

create_registrations = """CREATE TABLE IF NOT EXISTS registrations (
                            reg_id TEXT PRIMARY KEY,
                            ipaddress TEXT NOT NULL,
                            site TEXT NOT NULL,
                            agent_info TEXT,
                            public_key TEXT,
                            status TEXT CHECK(status IN ('pending','approved','rejected')) NOT NULL,
                            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            approved_at TIMESTAMP,
                            approved_by TEXT)"""

insert_registrations = """INSERT INTO registrations (reg_id, ipaddress, site, agent_info, public_key, status, requested_at, approved_at, approved_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
get_registrations = """SELECT * FROM registrations WHERE reg_id = ?"""
delete_registrations = """DELETE FROM registrations WHERE reg_id = ?"""
update_registrations = """UPDATE registrations SET status = ?, approved_at = ?, approved_by = ? WHERE reg_id = ?"""

def getUTCnow():
    """Return current UTC timestamp (ISO format)."""
    return datetime.now(timezone.utc).isoformat()


class SQLiteBackend:
    """SQLite backend for registration database."""

    def __init__(self, config):
        if not config or not config["MAIN"].get("privatedir"):
            raise ValueError("SQLite DB file path must be provided")
        self.dbfile = os.path.join(config["MAIN"]["privatedir"], "registrations.db")
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Context-managed SQLite connection."""
        conn = None
        try:
            conn = sqlite3.connect(self.dbfile, timeout=10)
            conn.row_factory = sqlite3.Row
            yield conn, conn.cursor()
            conn.commit()
        except Exception as ex:
            if conn:
                conn.rollback()
            exc = traceback.format_exc()
            raise RuntimeError(
                f"SQLite operation failed: {ex}\nTrace:\n{exc}"
            ) from ex
        finally:
            if conn:
                conn.close()

    def _init_db(self):
        """Initialize registration tables."""
        with self.get_connection() as (_conn, cursor):
            cursor.execute(create_registrations)

    def insert_registration(
        self, reg_id, ipaddress, site, agent_info, public_key,
        status="pending", approved_at=None, approved_by=None):
        """Insert a new registration request."""
        values = (reg_id, ipaddress, site, agent_info, public_key, status, getUTCnow(), approved_at, approved_by)
        with self.get_connection() as (_conn, cursor):
            cursor.execute(insert_registrations, values)

    def get_registration(self, reg_id):
        """Get a registration by reg_id."""
        with self.get_connection() as (_conn, cursor):
            cursor.execute(get_registrations, (reg_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_registration(self, reg_id):
        """Delete a registration by reg_id."""
        with self.get_connection() as (_conn, cursor):
            cursor.execute(delete_registrations, (reg_id,))

    def approve_registration(self, reg_id, approved_by):
        """Approve a registration."""
        values = ("approved", getUTCnow(), approved_by, reg_id)
        with self.get_connection() as (_conn, cursor):
            cursor.execute(update_registrations, values)

    def reject_registration(self, reg_id, approved_by):
        """Reject a registration."""
        values = ("rejected", getUTCnow(), approved_by, reg_id)
        with self.get_connection() as (_conn, cursor):
            cursor.execute(update_registrations, values)
