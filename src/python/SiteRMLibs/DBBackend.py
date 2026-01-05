#!/usr/bin/env python3
"""
DB Backend for communication with database.
"""

import os
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

from SiteRMLibs.DBModels import REGISTRY, Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext

# ==========================================================
#  Utilities
# ==========================================================


def getUTCnow() -> int:
    """Get UTC time as epoch seconds."""
    return int(datetime.now(timezone.utc).timestamp())


def loadEnvFile(filepath="/etc/environment"):
    """Load environment variables from a file (best effort)."""
    if not os.path.isfile(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as fd:
            for line in fd:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except Exception as ex:
        exc = traceback.format_exc()
        print(f"Failed loading env file {filepath}. Error: {ex}. Trace: {exc}")


def buildDatabaseURL() -> str:
    """
    Build SQLAlchemy DATABASE_URL for MariaDB/MySQL.

    Priority:
      1. DATABASE_URL env var
      2. Construct from MARIA_DB_* variables
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("MARIA_DB_USER", "root")
    password = os.getenv("MARIA_DB_PASSWORD", "")
    host = os.getenv("MARIA_DB_HOST", "localhost")
    port = os.getenv("MARIA_DB_PORT", "3306")
    database = os.getenv("MARIA_DB_DATABASE", "sitefe")
    charset = os.getenv("MARIA_DB_CHARSET", "utf8mb4")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset={charset}"


# ==========================================================
#  Database Backend
# ==========================================================
class DBBackend:
    """Database backend using SQLAlchemy ORM."""

    def __init__(self):
        loadEnvFile()

        self.database_url = buildDatabaseURL()
        self.autocommit = os.getenv("MARIA_DB_AUTOCOMMIT", "True") in ("True", "true", "1")
        self.engine = create_engine(self.database_url, pool_pre_ping=True, future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    @contextmanager
    def session(self):
        """Provide a transactional scope around a series of operations on the database."""
        session = self.Session()
        try:
            yield session
            if self.autocommit:
                session.commit()
        except Exception:
            print(f"Full traceback: {traceback.format_exc()}")
            session.rollback()
            raise
        finally:
            session.close()

    def createdb(self):
        """Create all tables from ORM metadata."""
        Base.metadata.create_all(self.engine)

    def upgradedb(self, directory):
        """Initialize Alembic if needed, then always upgrade DB to head."""
        loadEnvFile()
        cfg = Config("/etc/alembic.ini")
        cfg.set_main_option("sqlalchemy.url", self.database_url)
        cfg.set_main_option("script_location", str(directory))

        versionsDir = os.path.join(directory, "versions")

        try:
            if not os.path.isdir(versionsDir):
                print(f"Initializing Alembic in {directory}")
                command.init(cfg, directory)
            with self.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current = context.get_current_revision()
            if current is None:
                print("Database not stamped, stamping to base")
                command.stamp(cfg, "base")
            print(f"Upgrading database (current={current}) → head")
            command.upgrade(cfg, "head")
            return current
        except Exception:
            print("Database upgrade failed")
            print(traceback.format_exc())
            raise

    def executeRaw(self, sql):
        """
        Execute raw SQL directly on the engine.
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {})
            conn.commit()
            return result


    def cleandb(self):
        """Delete all rows from all tables."""
        with self.session() as session:
            for model in REGISTRY.values():
                session.query(model).delete()

    def cleandbtable(self, tablename):
        """Delete all rows from a specific table."""
        model = REGISTRY.get(tablename)
        if not model:
            raise ValueError(f"Unknown table: {tablename}")
        with self.session() as session:
            session.query(model).delete()


class dbinterface:
    """Database interface used by applications."""

    def __init__(self, serviceName="", config="", sitename=""):
        self.serviceName = serviceName
        self.config = config
        self.sitename = sitename
        self.db = DBBackend()

    def createdb(self):
        """Create all tables in the database."""
        self.db.createdb()

    def upgradedb(self, directory):
        """Upgrade the database schema to the latest Alembic revision."""
        self.db.upgradedb(directory)

    def isDBReady(self) -> bool:
        """Check if the database is ready to accept connections."""
        try:
            with self.db.session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def executeRaw(self, sql):
        """Execute raw SQL directly on the engine."""
        return self.db.executeRaw(sql)

    def get(self, calltype, limit=None, search=None, orderby=None, mapping=True):
        """Retrieve rows from a specific table."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        with self.db.session() as session:
            q = session.query(model)

            if search:
                for item in search:
                    if len(item) == 2:
                        q = q.filter(getattr(model, item[0]) == item[1])
                    elif len(item) == 3:
                        q = q.filter(getattr(model, item[0]).op(item[1])(item[2]))

            if orderby:
                col, direction = orderby
                q = q.order_by(getattr(model, col).desc() if direction.lower() == "desc" else getattr(model, col).asc())

            if limit:
                q = q.limit(limit)

            rows = q.all()

            if not mapping:
                return rows

            return [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in rows]

    def insert(self, calltype, values):
        """Insert rows into a specific table."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        last_id = None
        with self.db.session() as session:
            for val in values:
                obj = model(**val)
                session.add(obj)
                session.flush()
                last_id = getattr(obj, "id", None)

        return "OK", "", last_id

    def update(self, calltype, values):
        """Update rows in a specific table."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        with self.db.session() as session:
            for val in values:
                obj = session.get(model, val.get("id"))
                if not obj:
                    continue
                for key, value in val.items():
                    setattr(obj, key, value)

        return "OK", "", ""

    def delete(self, calltype, values):
        """Delete rows from a specific table."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        with self.db.session() as session:
            q = session.query(model)
            for col, val in values:
                q = q.filter(getattr(model, col) == val)
            q.delete(synchronize_session=False)

        return "OK", "", ""

    def _clean(self, _calltype, _values):
        """Clean the entire database."""
        self.db.cleandb()

    def _cleantable(self, calltype, _values):
        """Clean a specific table in the database."""
        self.db.cleandbtable(calltype)
